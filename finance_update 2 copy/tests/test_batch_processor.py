"""Tests for the BatchProcessor."""

import pytest
import asyncio
from typing import List, Dict, Any
import logging

from services.batch_processor import BatchProcessor, BatchConfig, BatchProgress
from services.summarizer_service import SummaryConfig
from utils.exceptions import ProcessingError, ValidationError, SummaryError
from tests.helpers import (
    create_test_context,
    create_summary_config,
    create_test_report,
    run_async_test,
    assert_error_details
)

@pytest.fixture
def batch_config() -> BatchConfig:
    """Create test batch configuration."""
    return BatchConfig(
        max_concurrent=3,
        retry_attempts=2,
        retry_delay=0.1,
        progress_interval=0.1
    )

@pytest.fixture
def batch_processor(service_context, batch_config) -> BatchProcessor:
    """Create BatchProcessor instance with mock dependencies."""
    return BatchProcessor(
        validation_service=service_context.validation_service,
        summarizer_service=service_context.summarizer_service,
        config=batch_config
    )

@pytest.mark.asyncio
async def test_process_reports_success(batch_processor, test_context):
    """Test successful processing of multiple reports."""
    # Arrange
    reports = [
        create_test_report(f"report_{i}.pdf")
        for i in range(5)
    ]
    config = create_summary_config()
    
    # Act
    summaries = await batch_processor.process_reports(
        reports=reports,
        summary_config=config
    )
    
    # Assert
    assert len(summaries) == len(reports)
    assert all(s['summary'] for s in summaries)
    
    # Verify concurrent processing
    call_history = test_context.openai_client.get_call_history()
    concurrent_calls = set()
    for call in call_history:
        concurrent_calls.add(call['model'])
    assert len(concurrent_calls) <= batch_processor.config.max_concurrent

@pytest.mark.asyncio
async def test_process_reports_with_failures(batch_processor, test_context):
    """Test processing with some failing reports."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(3)]
    config = create_summary_config()
    
    # Set one report to fail
    test_context.openai_client.set_response('initial_summary', 'error', None)
    
    # Act
    summaries = await batch_processor.process_reports(
        reports=reports,
        summary_config=config
    )
    
    # Assert
    assert len(summaries) < len(reports)
    assert all(s['summary'] for s in summaries)

@pytest.mark.asyncio
async def test_retry_mechanism(batch_processor, test_context, caplog):
    """Test retry mechanism for failed processing."""
    # Arrange
    report = create_test_report()
    config = create_summary_config()
    
    # Set up to fail first attempt, succeed on retry
    test_context.openai_client.set_response('initial_summary', 'error', None)
    
    def on_second_try(*args, **kwargs):
        test_context.openai_client.set_response(
            'initial_summary',
            'success',
            'Success on retry'
        )
    
    # Schedule response change after first attempt
    asyncio.get_event_loop().call_later(0.1, on_second_try)
    
    # Act
    with caplog.at_level(logging.INFO):
        summaries = await batch_processor.process_reports(
            reports=[report],
            summary_config=config
        )
    
    # Assert
    assert len(summaries) == 1
    assert "retry" in caplog.text.lower()
    
    # Verify multiple attempts were made
    call_history = test_context.openai_client.get_call_history()
    assert len(call_history) > 1

@pytest.mark.asyncio
async def test_progress_tracking(batch_processor, test_context, caplog):
    """Test progress tracking and reporting."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(5)]
    config = create_summary_config()
    
    # Act
    with caplog.at_level(logging.INFO):
        summaries = await batch_processor.process_reports(
            reports=reports,
            summary_config=config
        )
    
    # Assert
    progress_logs = [
        log for log in caplog.records
        if "progress" in log.message.lower()
    ]
    assert len(progress_logs) > 0
    
    # Verify progress reporting
    final_log = progress_logs[-1]
    assert str(len(reports)) in final_log.message
    assert "100%" in final_log.message or "success rate" in final_log.message.lower()

@pytest.mark.asyncio
async def test_concurrent_processing_limits(batch_processor, test_context):
    """Test enforcement of concurrent processing limits."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(10)]
    config = create_summary_config()
    max_concurrent = batch_processor.config.max_concurrent
    
    # Add delay to processing to ensure concurrent execution
    async def delayed_processing(*args, **kwargs):
        await asyncio.sleep(0.1)
        return "Delayed summary"
    
    test_context.openai_client.generate_summary = delayed_processing
    
    # Act
    summaries = await batch_processor.process_reports(
        reports=reports,
        summary_config=config
    )
    
    # Assert
    assert len(summaries) == len(reports)
    
    # Verify concurrent processing limits
    call_times = []
    for call in test_context.openai_client.get_call_history():
        call_times.append(call.get('timestamp', 0))
    
    # Check that no more than max_concurrent calls were active at once
    concurrent_calls = 0
    for i in range(len(call_times)):
        active = sum(
            1 for t in call_times[i+1:]
            if t - call_times[i] < 0.1  # Within processing window
        )
        concurrent_calls = max(concurrent_calls, active)
    
    assert concurrent_calls <= max_concurrent

@pytest.mark.asyncio
async def test_error_handling_and_reporting(batch_processor, test_context, caplog):
    """Test error handling and reporting during batch processing."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(3)]
    config = create_summary_config()
    
    # Set up different error scenarios
    test_context.openai_client.set_response('initial_summary', 'empty', '')
    
    # Act
    with caplog.at_level(logging.ERROR):
        summaries = await batch_processor.process_reports(
            reports=reports,
            summary_config=config
        )
    
    # Assert
    assert len(summaries) < len(reports)
    
    # Verify error logging
    error_logs = [
        log for log in caplog.records
        if log.levelno >= logging.ERROR
    ]
    assert len(error_logs) > 0
    assert any("error" in log.message.lower() for log in error_logs)
    
    # Verify error details were logged
    assert any(
        "details" in log.message.lower() and "recovery" in log.message.lower()
        for log in error_logs
    )

@pytest.mark.asyncio
async def test_batch_progress_tracking(batch_processor):
    """Test BatchProgress tracking functionality."""
    # Arrange
    progress = BatchProgress(total=5)
    
    # Act & Assert
    assert progress.success_rate == 0
    
    progress.completed = 2
    progress.failed = 1
    assert progress.success_rate == (2/3) * 100
    
    progress_dict = progress.to_dict()
    assert progress_dict['total'] == 5
    assert progress_dict['completed'] == 2
    assert progress_dict['failed'] == 1
    assert progress_dict['remaining'] == 2

@pytest.mark.asyncio
async def test_process_topics_success(batch_processor, test_context):
    """Test successful processing of topic summaries."""
    # Arrange
    topic_texts = {
        'topic1': "Content for topic 1",
        'topic2': "Content for topic 2",
        'topic3': "Content for topic 3"
    }
    config = create_summary_config()
    
    # Act
    summaries = await batch_processor.process_topics(
        topic_texts=topic_texts,
        summary_config=config
    )
    
    # Assert
    assert len(summaries) == len(topic_texts)
    assert all(topic in summaries for topic in topic_texts)
    assert all(summaries[topic] for topic in summaries)

@pytest.mark.asyncio
async def test_cancellation_handling(batch_processor, test_context):
    """Test handling of cancelled tasks."""
    # Arrange
    reports = [create_test_report(f"report_{i}.pdf") for i in range(5)]
    config = create_summary_config()
    
    # Create a task and cancel it after a delay
    async def cancel_after_delay(task):
        await asyncio.sleep(0.1)
        task.cancel()
    
    # Act
    process_task = asyncio.create_task(
        batch_processor.process_reports(
            reports=reports,
            summary_config=config
        )
    )
    asyncio.create_task(cancel_after_delay(process_task))
    
    # Assert
    with pytest.raises(asyncio.CancelledError):
        await process_task
