"""Integration tests for the full processing pipeline."""

import pytest
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from services.summarizer_service import SummarizerService, SummaryConfig
from services.batch_processor import BatchProcessor, BatchConfig
from services.validation_service import ValidationService
from services.metrics_extractor import MetricsExtractor
from services.chunk_manager import ChunkManager
from services.prompt_manager import PromptManager
from utils.exceptions import (
    ProcessingError,
    ValidationError,
    SummaryError,
    MetricsError
)
from tests.helpers import (
    create_test_context,
    create_test_report,
    create_summary_config,
    assert_error_details
)

@pytest.fixture
def service_pipeline(service_context):
    """Create pipeline with all services."""
    return {
        'summarizer': SummarizerService(
            openai_client=service_context.openai_client,
            chunk_manager=service_context.chunk_manager,
            prompt_manager=service_context.prompt_manager
        ),
        'batch_processor': BatchProcessor(
            validation_service=service_context.validation_service,
            summarizer_service=None,  # Will be set after creation
            config=BatchConfig(
                max_concurrent=3,
                retry_attempts=2,
                retry_delay=0.1,
                progress_interval=0.1
            )
        ),
        'validation': service_context.validation_service,
        'metrics': service_context.metrics_extractor,
        'chunks': service_context.chunk_manager,
        'prompts': service_context.prompt_manager
    }

@pytest.fixture(autouse=True)
def setup_pipeline(service_pipeline):
    """Set up service dependencies."""
    # Set up circular dependencies
    service_pipeline['batch_processor'].summarizer_service = service_pipeline['summarizer']
    yield service_pipeline

@pytest.mark.integration
async def test_full_pipeline_success(service_pipeline, test_context):
    """Test successful processing through full pipeline."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(3)]
    config = create_summary_config()
    
    # Act
    summaries = await service_pipeline['batch_processor'].process_reports(
        reports=reports,
        summary_config=config
    )
    
    # Assert
    assert len(summaries) == len(reports)
    assert all(s['summary'] for s in summaries)
    
    # Verify metrics were extracted
    for summary in summaries:
        metrics = service_pipeline['metrics'].extract_metrics(summary['summary'])
        assert metrics is not None
        assert len(metrics) > 0

@pytest.mark.integration
async def test_service_interaction_flow(service_pipeline, sample_text):
    """Test interaction flow between services."""
    # 1. Validation
    assert service_pipeline['validation'].validate_extracted_text(sample_text)
    
    # 2. Chunking
    chunks = service_pipeline['chunks'].chunk_text(
        text=sample_text,
        max_chunk_size=100
    )
    assert len(chunks) > 0
    
    # 3. Summarization
    config = create_summary_config()
    summary = await service_pipeline['summarizer'].process_report_text(
        text=sample_text,
        config=config,
        name="test_report"
    )
    assert summary is not None
    
    # 4. Metrics Extraction
    metrics = service_pipeline['metrics'].extract_metrics(summary)
    assert metrics is not None
    assert len(metrics) > 0

@pytest.mark.integration
async def test_error_propagation(service_pipeline, test_context):
    """Test error propagation through services."""
    # Arrange
    invalid_report = create_test_report()
    invalid_report['text'] = ""  # Empty text should trigger validation error
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        await service_pipeline['batch_processor'].process_reports(
            reports=[invalid_report],
            summary_config=create_summary_config()
        )
    
    error = exc_info.value
    assert "empty text" in str(error).lower()

@pytest.mark.integration
@pytest.mark.slow
async def test_pipeline_performance(service_pipeline, test_context):
    """Test pipeline performance under load."""
    # Arrange
    num_reports = 10
    reports = [create_test_report(f"report_{i}.pdf") for i in range(num_reports)]
    config = create_summary_config()
    
    # Act
    start_time = time.time()
    summaries = await service_pipeline['batch_processor'].process_reports(
        reports=reports,
        summary_config=config
    )
    end_time = time.time()
    
    # Assert
    duration = end_time - start_time
    assert len(summaries) == num_reports
    assert duration < 30.0  # Should complete within reasonable time

@pytest.mark.integration
async def test_prompt_variant_optimization(service_pipeline, test_context):
    """Test prompt variant optimization through pipeline."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(5)]
    config = create_summary_config()
    
    # Act
    summaries = await service_pipeline['batch_processor'].process_reports(
        reports=reports,
        summary_config=config
    )
    
    # Assert
    variant_stats = service_pipeline['prompts'].get_variant_stats("initial_summary")
    assert len(variant_stats) > 0
    assert any(stat['uses'] > 0 for stat in variant_stats)

@pytest.mark.integration
async def test_chunk_optimization(service_pipeline, large_text):
    """Test chunk optimization through pipeline."""
    # Arrange
    config = create_summary_config()
    
    # Act
    summary = await service_pipeline['summarizer'].process_report_text(
        text=large_text,
        config=config,
        name="large_report"
    )
    
    # Assert
    assert summary is not None
    # Verify key metrics were preserved
    metrics = service_pipeline['metrics'].extract_metrics(summary)
    assert metrics is not None
    assert len(metrics) > 0

@pytest.mark.integration
async def test_concurrent_processing(service_pipeline, test_context):
    """Test concurrent processing through pipeline."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(5)]
    config = create_summary_config()
    
    # Create multiple concurrent tasks
    tasks = [
        service_pipeline['batch_processor'].process_reports(
            reports=reports,
            summary_config=config
        )
        for _ in range(3)
    ]
    
    # Act
    results = await asyncio.gather(*tasks)
    
    # Assert
    assert len(results) == 3
    assert all(len(summaries) == len(reports) for summaries in results)

@pytest.mark.integration
async def test_recovery_strategies(service_pipeline, test_context):
    """Test recovery strategies in pipeline."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(3)]
    config = create_summary_config()
    
    # Set up to fail first attempt
    test_context.openai_client.set_response('initial_summary', 'error', None)
    
    def on_retry(*args, **kwargs):
        test_context.openai_client.set_response(
            'initial_summary',
            'success',
            'Success on retry'
        )
    
    # Schedule response change after first attempt
    asyncio.get_event_loop().call_later(0.1, on_retry)
    
    # Act
    summaries = await service_pipeline['batch_processor'].process_reports(
        reports=reports,
        summary_config=config
    )
    
    # Assert
    assert len(summaries) == len(reports)
    call_history = test_context.openai_client.get_call_history()
    assert len(call_history) > len(reports)  # Should show retry attempts

@pytest.mark.integration
async def test_metrics_validation_flow(service_pipeline, sample_text):
    """Test metrics validation flow through pipeline."""
    # Act
    # 1. Generate summary
    config = create_summary_config()
    summary = await service_pipeline['summarizer'].process_report_text(
        text=sample_text,
        config=config,
        name="test_report"
    )
    
    # 2. Extract and validate metrics
    metrics = service_pipeline['metrics'].extract_metrics(summary)
    
    # Assert
    assert metrics is not None
    # Verify metrics are within valid ranges
    assert 0 <= metrics.get('growth_rate', 0) <= 100
    assert metrics.get('revenue', 0) > 0
