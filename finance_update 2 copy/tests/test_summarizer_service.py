"""Tests for the SummarizerService."""

import pytest
from typing import Dict, Any

from services.summarizer_service import SummarizerService
from services.chunk_manager import ChunkManager
from services.prompt_manager import PromptManager
from utils.exceptions import SummaryError, ChunkError, PromptError
from tests.helpers import (
    create_test_context,
    create_summary_config,
    create_test_report,
    compare_summaries,
    run_async_test,
    assert_error_details
)

@pytest.fixture
def test_context():
    """Create test context with mock clients."""
    context = create_test_context()
    yield context
    context.cleanup()

@pytest.fixture
def summarizer_service(test_context):
    """Create SummarizerService instance with mock dependencies."""
    return SummarizerService(
        openai_client=test_context.openai_client,
        chunk_manager=ChunkManager(),
        prompt_manager=PromptManager()
    )

@pytest.mark.asyncio
async def test_summarize_batch_success(summarizer_service, test_context):
    """Test successful batch summarization."""
    # Arrange
    test_text = test_context.test_data['test_cases']['large_text']['input']
    expected_summary = test_context.test_data['summaries']['initial_summary']['success']
    
    # Act
    summary, variant_id = await summarizer_service.summarize_batch(
        batch_text=test_text,
        model='gpt-4o',
        max_tokens=1000,
        enable_variants=True
    )
    
    # Assert
    assert summary is not None
    assert compare_summaries(summary, expected_summary)
    assert variant_id is not None
    
    # Verify client calls
    call_history = test_context.openai_client.get_call_history()
    assert len(call_history) == 1
    assert call_history[0]['model'] == 'gpt-4o'
    assert call_history[0]['max_tokens'] == 1000

@pytest.mark.asyncio
async def test_summarize_batch_empty_response(summarizer_service, test_context):
    """Test handling of empty summary response."""
    # Arrange
    test_text = test_context.test_data['test_cases']['large_text']['input']
    test_context.openai_client.set_response('initial_summary', 'empty', '')
    
    # Act & Assert
    with pytest.raises(SummaryError) as exc_info:
        await summarizer_service.summarize_batch(
            batch_text=test_text,
            model='gpt-4o',
            max_tokens=1000
        )
    
    assert "Generated summary is empty" in str(exc_info.value)
    assert exc_info.value.details['model'] == 'gpt-4o'

@pytest.mark.asyncio
async def test_consolidate_chunks_success(summarizer_service, test_context):
    """Test successful chunk consolidation."""
    # Arrange
    chunks = [
        "First chunk of text with key information.",
        "Second chunk with additional insights.",
        "Third chunk with final points."
    ]
    expected_summary = test_context.test_data['summaries']['consolidate_chunks']['success']
    
    # Act
    consolidated, variant_id = await summarizer_service.consolidate_chunks(
        chunks=chunks,
        model='gpt-4o',
        max_tokens=1000,
        enable_variants=True
    )
    
    # Assert
    assert consolidated is not None
    assert compare_summaries(consolidated, expected_summary)
    
    # Verify client calls
    call_history = test_context.openai_client.get_call_history()
    assert len(call_history) == 1
    assert 'combining these summaries' in call_history[0]['prompt']

@pytest.mark.asyncio
async def test_process_report_text_success(summarizer_service, test_context):
    """Test successful report text processing."""
    # Arrange
    config = create_summary_config()
    report = create_test_report()
    
    # Act
    summary = await summarizer_service.process_report_text(
        text=report['text'],
        config=config,
        name=report['file_name']
    )
    
    # Assert
    assert summary is not None
    assert len(summary) > 0
    
    # Verify client calls
    call_history = test_context.openai_client.get_call_history()
    assert len(call_history) > 0
    assert all(call['model'] == config.model for call in call_history)

@pytest.mark.asyncio
async def test_process_report_text_empty_input(summarizer_service, test_context):
    """Test handling of empty input text."""
    # Arrange
    config = create_summary_config()
    
    # Act & Assert
    with pytest.raises(ChunkError) as exc_info:
        await summarizer_service.process_report_text(
            text="",
            config=config,
            name="empty_report"
        )
    
    assert "Failed to split text into chunks" in str(exc_info.value)
    assert exc_info.value.details['text_length'] == 0

@pytest.mark.asyncio
async def test_process_report_text_invalid_model(summarizer_service, test_context):
    """Test handling of invalid model configuration."""
    # Arrange
    config = create_summary_config('invalid-model')
    report = create_test_report()
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await summarizer_service.process_report_text(
            text=report['text'],
            config=config,
            name=report['file_name']
        )
    
    assert "Unknown model" in str(exc_info.value)

@pytest.mark.asyncio
async def test_process_report_text_token_limit(summarizer_service, test_context):
    """Test handling of token limit exceeded."""
    # Arrange
    config = create_summary_config()
    config.max_output_tokens = 5  # Set very low token limit
    report = create_test_report()
    
    # Act
    summary = await summarizer_service.process_report_text(
        text=report['text'],
        config=config,
        name=report['file_name']
    )
    
    # Assert
    assert summary is not None  # Service should handle token limits gracefully
    
    # Verify warning was logged (would need to add log capture fixture for this)
    # assert "Token limit exceeded" in captured_logs

@pytest.mark.asyncio
async def test_prompt_variant_tracking(summarizer_service, test_context):
    """Test tracking of prompt variants."""
    # Arrange
    test_text = test_context.test_data['test_cases']['large_text']['input']
    
    # Act
    summary, variant_id = await summarizer_service.summarize_batch(
        batch_text=test_text,
        model='gpt-4o',
        max_tokens=1000,
        enable_variants=True
    )
    
    # Assert
    assert variant_id is not None
    # Verify variant was recorded (would need to add PromptManager tracking for this)
    # assert variant_id in prompt_manager.get_variant_stats('initial_summary')

@pytest.mark.asyncio
async def test_error_recovery_attempts(summarizer_service, test_context):
    """Test error recovery attempts during processing."""
    # Arrange
    config = create_summary_config()
    report = create_test_report()
    test_context.openai_client.set_response('initial_summary', 'error', None)
    
    # Act
    summary = await summarizer_service.process_report_text(
        text=report['text'],
        config=config,
        name=report['file_name']
    )
    
    # Assert
    assert summary is None
    
    # Verify multiple attempts were made
    call_history = test_context.openai_client.get_call_history()
    assert len(call_history) > 1  # Should have retried at least once
