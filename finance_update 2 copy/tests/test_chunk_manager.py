"""Tests for the ChunkManager."""

import pytest
from typing import List, Dict, Any
from unittest.mock import patch

from services.chunk_manager import ChunkManager, CHUNK_PROCESSING_TIME, CHUNK_OPERATIONS
from utils.exceptions import ChunkError
from utils.text_processor import get_token_count
from tests.helpers import (
    create_test_report,
    assert_error_details
)

# Mock metrics for testing
@pytest.fixture
def mock_metrics():
    """Mock Prometheus metrics."""
    with patch('prometheus_client.Histogram.observe') as mock_hist, \
         patch('prometheus_client.Counter.inc') as mock_counter:
        yield {
            'histogram': mock_hist,
            'counter': mock_counter
        }

@pytest.fixture
def chunk_manager() -> ChunkManager:
    """Create ChunkManager instance."""
    try:
        return ChunkManager()
    except ChunkError as e:
        pytest.fail(f"Failed to create ChunkManager: {str(e)}")

@pytest.fixture
def sample_text() -> str:
    """Create sample text for chunking."""
    return (
        "First paragraph with important information.\n\n"
        "Second paragraph contains key metrics:\n"
        "- Revenue: $1,000,000\n"
        "- Growth: 15%\n"
        "- Market Share: 25%\n\n"
        "Third paragraph discusses trends.\n\n"
        "Fourth paragraph has conclusions.\n\n"
        "Fifth paragraph with recommendations."
    )

@pytest.fixture
def large_text() -> str:
    """Create large text for testing chunking limits."""
    paragraphs = []
    for i in range(50):
        paragraphs.append(
            f"Paragraph {i+1} with metrics:\n"
            f"- Value {i}: ${i*1000:,}\n"
            f"- Growth {i}: {i*5}%\n"
            f"- Share {i}: {i*2}%\n"
        )
    return "\n\n".join(paragraphs)

def test_chunk_manager_init_invalid():
    """Test ChunkManager initialization with invalid parameters."""
    with pytest.raises(ChunkError) as exc_info:
        ChunkManager(max_chunk_size=-1)
    
    error = exc_info.value
    assert "Invalid max_chunk_size" in str(error)
    assert error.details['chunk_size'] == -1
    assert "Set max_chunk_size to a positive integer" in error.recovery_action

def test_chunk_text_empty(chunk_manager, mock_metrics):
    """Test chunking empty text."""
    # Act & Assert
    with pytest.raises(ChunkError) as exc_info:
        chunk_manager.chunk_text("")
    
    error = exc_info.value
    assert "Empty text provided" in str(error)
    assert error.details['text_length'] == 0
    assert "Provide non-empty text for chunking" in error.recovery_action
    
    # Verify metrics
    mock_metrics['histogram'].assert_called_with(
        'chunk_processing_seconds',
        {'operation': 'chunk_text', 'status': 'failure'}
    )
    mock_metrics['counter'].assert_called_with(
        'chunk_operations_total',
        {'operation': 'chunk_text', 'status': 'failure'}
    )

def test_chunk_text_basic(chunk_manager, sample_text, mock_metrics):
    """Test basic text chunking."""
    # Act
    chunks = chunk_manager.chunk_text(text=sample_text, max_tokens=100)
    
    # Assert
    assert len(chunks) > 1
    for text, meta in chunks:
        assert len(text) > 0
        assert meta.token_count <= 100
    
    # Verify content preservation
    combined = " ".join(text for text, _ in chunks)
    assert "Revenue: $1,000,000" in combined
    assert "Growth: 15%" in combined
    assert "Market Share: 25%" in combined
    
    # Verify metrics
    mock_metrics['histogram'].assert_called_with(
        'chunk_processing_seconds',
        {'operation': 'chunk_text', 'status': 'success'}
    )
    mock_metrics['counter'].assert_called_with(
        'chunk_operations_total',
        {'operation': 'chunk_text', 'status': 'success'}
    )

def test_chunk_text_invalid_max_tokens(chunk_manager, sample_text):
    """Test chunking with invalid max_tokens."""
    with pytest.raises(ChunkError) as exc_info:
        chunk_manager.chunk_text(text=sample_text, max_tokens=-1)
    
    error = exc_info.value
    assert "Invalid max_tokens value" in str(error)
    assert error.details['chunk_size'] == -1
    assert "Set max_tokens to a positive integer" in error.recovery_action

def test_chunk_text_small(chunk_manager, mock_metrics):
    """Test chunking text smaller than chunk size."""
    # Arrange
    small_text = "Small text that fits in one chunk."
    
    # Act
    chunks = chunk_manager.chunk_text(text=small_text, max_tokens=1000)
    
    # Assert
    assert len(chunks) == 1
    text, meta = chunks[0]
    assert text == small_text
    assert meta.token_count <= 1000
    
    # Verify metrics
    mock_metrics['histogram'].assert_called_with(
        'chunk_processing_seconds',
        {'operation': 'chunk_text', 'status': 'success'}
    )

def test_chunk_text_large(chunk_manager, large_text, mock_metrics):
    """Test chunking large text."""
    # Act
    chunks = chunk_manager.chunk_text(text=large_text, max_tokens=500)
    
    # Assert
    assert len(chunks) > 1
    for text, meta in chunks:
        assert meta.token_count <= 500
    
    # Verify no content loss
    combined = " ".join(text for text, _ in chunks)
    assert all(f"Paragraph {i+1}" in combined for i in range(50))
    
    # Verify metrics
    mock_metrics['counter'].assert_called_with(
        'chunk_operations_total',
        {'operation': 'split_paragraphs', 'status': 'success'}
    )

def test_chunk_text_preserve_metrics(chunk_manager, sample_text):
    """Test preservation of metrics during chunking."""
    # Act
    chunks = chunk_manager.chunk_text(text=sample_text, max_tokens=50)
    
    # Assert
    metrics_found = False
    for text, _ in chunks:
        if "Revenue: $1,000,000" in text:
            metrics_found = True
            # Check that related metrics stay together
            assert "Growth: 15%" in text
            assert "Market Share: 25%" in text
    assert metrics_found

def test_chunk_text_preserve_sentences(chunk_manager):
    """Test preservation of sentence boundaries."""
    # Arrange
    text = (
        "First complete sentence. Second complete sentence. "
        "Third sentence with numbers 12.34. "
        "Fourth sentence ends here."
    )
    
    # Act
    chunks = chunk_manager.chunk_text(text=text, max_tokens=50)
    
    # Assert
    for text, _ in chunks:
        # Verify chunks end with sentence boundaries
        assert text.strip().endswith(('.', '!', '?'))
        # Verify numbers aren't split
        if "12" in text:
            assert "12.34" in text

def test_chunk_text_edge_cases(chunk_manager, mock_metrics):
    """Test chunking edge cases."""
    edge_cases = {
        'unicode': "Unicode text: 🚀📈💹\n" * 10,
        'special_chars': "Special chars: &lt;&gt;&amp;\n" * 10,
        'line_endings': "Mixed\nline\r\nendings\n" * 10,
        'long_word': "Supercalifragilisticexpialidocious " * 10,
        'urls': "https://very.long.domain.example.com/path " * 10,
        'no_spaces': "NoSpacesInThisTextAtAllJustOneLongString" * 10
    }
    
    for case, text in edge_cases.items():
        # Act
        chunks = chunk_manager.chunk_text(text=text, max_tokens=100)
        
        # Assert
        assert len(chunks) > 0, f"Failed to chunk {case}"
        for chunk_text, meta in chunks:
            assert len(chunk_text) > 0
            assert meta.token_count <= 100
    
    # Verify metrics were recorded for each case
    assert mock_metrics['counter'].call_count >= len(edge_cases)

def test_chunk_text_with_report(chunk_manager):
    """Test chunking with test report data."""
    # Arrange
    report = create_test_report()
    
    # Act
    chunks = chunk_manager.chunk_text(text=report['text'], max_tokens=100)
    
    # Assert
    assert len(chunks) > 0
    # Verify key metrics are preserved in chunks
    found_metrics = False
    for text, _ in chunks:
        if "Revenue: $1,000,000" in text:
            found_metrics = True
            break
    assert found_metrics

def test_chunk_text_error_recovery(chunk_manager, mock_metrics):
    """Test error recovery suggestions."""
    # Test with various error conditions
    error_cases = [
        ("", "Provide non-empty text for chunking"),
        ("Some text", -1, "Set max_tokens to a positive integer"),
    ]
    
    for args in error_cases:
        with pytest.raises(ChunkError) as exc_info:
            if len(args) == 2:
                text, expected_action = args
                chunk_manager.chunk_text(text=text)
            else:
                text, max_tokens, expected_action = args
                chunk_manager.chunk_text(text=text, max_tokens=max_tokens)
        
        error = exc_info.value
        assert error.recovery_action == expected_action
        
        # Verify failure metrics were recorded
        mock_metrics['counter'].assert_called_with(
            'chunk_operations_total',
            {'operation': 'chunk_text', 'status': 'failure'}
        )
