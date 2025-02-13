"""Tests for the ValidationService."""

import pytest
import logging
from typing import Dict, Any

from services.validation_service import ValidationService
from utils.exceptions import ValidationError
from tests.helpers import (
    create_test_report,
    assert_error_details
)

@pytest.fixture
def validation_service() -> ValidationService:
    """Create ValidationService instance."""
    return ValidationService()

@pytest.fixture
def valid_text() -> str:
    """Create valid test text."""
    return (
        "This is a valid financial report with key metrics.\n\n"
        "Revenue: $1,000,000\n"
        "Growth: 15%\n"
        "Market Share: 25%\n\n"
        "Analysis shows positive trends in Q3 2023."
    )

@pytest.fixture
def invalid_texts() -> Dict[str, str]:
    """Create various invalid test texts."""
    return {
        'empty': '',
        'whitespace_only': '   \n   \t   ',
        'too_short': 'Brief.',
        'no_metrics': 'This text has no numerical data or metrics.',
        'corrupted': '\x00\x01Invalid binary content\x02',
        'repeated': 'The same text. ' * 50,  # Highly repetitive
        'malformed': (
            'Bad formatting:\n'
            '$$123,45.67\n'  # Invalid number format
            'Date: 13/13/2023'  # Invalid date
        )
    }

def test_validate_extracted_text_success(validation_service, valid_text):
    """Test successful text validation."""
    # Act
    result = validation_service.validate_extracted_text(valid_text)
    
    # Assert
    assert result is True

def test_validate_extracted_text_empty(validation_service, invalid_texts):
    """Test validation of empty text."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(invalid_texts['empty'])
    
    error = exc_info.value
    assert "Empty text" in str(error)
    assert error.details['text_preview'] == ''
    assert 'empty_text' in error.details['failed_rules']

def test_validate_extracted_text_whitespace(validation_service, invalid_texts):
    """Test validation of whitespace-only text."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(invalid_texts['whitespace_only'])
    
    error = exc_info.value
    assert "whitespace" in str(error).lower()
    assert error.details['text_preview'].isspace()
    assert 'whitespace_only' in error.details['failed_rules']

def test_validate_extracted_text_too_short(validation_service, invalid_texts):
    """Test validation of too short text."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(invalid_texts['too_short'])
    
    error = exc_info.value
    assert "length" in str(error).lower()
    assert error.details['text_preview'] == invalid_texts['too_short']
    assert 'minimum_length' in error.details['failed_rules']

def test_validate_extracted_text_no_metrics(validation_service, invalid_texts):
    """Test validation of text without metrics."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(invalid_texts['no_metrics'])
    
    error = exc_info.value
    assert "metrics" in str(error).lower()
    assert error.details['text_preview'] == invalid_texts['no_metrics']
    assert 'contains_metrics' in error.details['failed_rules']

def test_validate_extracted_text_corrupted(validation_service, invalid_texts):
    """Test validation of corrupted text."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(invalid_texts['corrupted'])
    
    error = exc_info.value
    assert "invalid" in str(error).lower()
    assert 'invalid_characters' in error.details['failed_rules']

def test_validate_extracted_text_repeated(validation_service, invalid_texts):
    """Test validation of highly repetitive text."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(invalid_texts['repeated'])
    
    error = exc_info.value
    assert "repetitive" in str(error).lower()
    assert 'repetitive_content' in error.details['failed_rules']

def test_validate_extracted_text_malformed(validation_service, invalid_texts):
    """Test validation of malformed text."""
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(invalid_texts['malformed'])
    
    error = exc_info.value
    assert "malformed" in str(error).lower()
    assert 'malformed_content' in error.details['failed_rules']

def test_validate_multiple_issues(validation_service):
    """Test validation of text with multiple issues."""
    # Arrange
    problematic_text = '   \nBad.\n' * 10
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        validation_service.validate_extracted_text(problematic_text)
    
    error = exc_info.value
    assert len(error.details['failed_rules']) > 1
    assert error.details['text_preview'] == problematic_text[:100]

def test_validate_extracted_text_recovery_suggestions(validation_service, invalid_texts):
    """Test recovery suggestions for validation failures."""
    # Act & Assert
    for case, text in invalid_texts.items():
        with pytest.raises(ValidationError) as exc_info:
            validation_service.validate_extracted_text(text)
        
        error = exc_info.value
        assert error.recovery_action is not None
        assert len(error.recovery_action) > 0

def test_validate_extracted_text_with_report(validation_service):
    """Test validation with test report data."""
    # Arrange
    report = create_test_report()
    
    # Act
    result = validation_service.validate_extracted_text(report['text'])
    
    # Assert
    assert result is True

def test_validation_logging(validation_service, invalid_texts, caplog):
    """Test logging of validation failures."""
    # Act
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ValidationError):
            validation_service.validate_extracted_text(invalid_texts['empty'])
    
    # Assert
    assert any(
        "validation" in record.message.lower()
        for record in caplog.records
    )
    assert any(
        "failed" in record.message.lower()
        for record in caplog.records
    )

def test_validation_rules_configuration(validation_service):
    """Test configuration of validation rules."""
    # Arrange
    custom_rules = {
        'minimum_length': 50,  # Increase minimum length
        'max_repetition': 0.3  # Decrease repetition threshold
    }
    
    # Create service with custom rules
    service = ValidationService(rules=custom_rules)
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        service.validate_extracted_text("Short text")  # Should fail with new minimum
    
    error = exc_info.value
    assert 'minimum_length' in error.details['failed_rules']

def test_validation_performance(validation_service, valid_text):
    """Test validation performance with large text."""
    # Arrange
    large_text = valid_text * 1000  # Create very large text
    
    # Act
    start_time = time.time()
    result = validation_service.validate_extracted_text(large_text)
    end_time = time.time()
    
    # Assert
    assert result is True
    assert end_time - start_time < 1.0  # Should complete within 1 second

def test_validation_edge_cases(validation_service):
    """Test validation edge cases."""
    edge_cases = {
        'unicode': "Unicode text: 🚀📈💹",
        'special_chars': "Special chars: &lt;&gt;&amp;",
        'line_endings': "Mixed\nline\r\nendings",
        'tabs_spaces': "\tIndented\t  text  ",
        'html_content': "<p>HTML content</p>",
        'urls': "Contains https://example.com links",
        'emails': "Contact user@example.com"
    }
    
    # Test each edge case
    for case, text in edge_cases.items():
        # Combine with valid content to meet other validation requirements
        combined_text = f"{text}\n\nRevenue: $1,000,000\nGrowth: 15%"
        result = validation_service.validate_extracted_text(combined_text)
        assert result is True, f"Failed to validate {case}"
