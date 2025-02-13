"""Service for handling text validation and quality checks."""

import re
import logging
from typing import Dict, List, NamedTuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Results of a validation check."""
    is_valid: bool
    issues: List[str]
    metrics: Dict[str, List[str]]

class ValidationMetrics(NamedTuple):
    """Metrics extracted during validation."""
    total_words: int
    avg_sentence_length: float
    special_char_ratio: float
    numerical_density: float

class ValidationService:
    """Handles validation of text content and summaries."""

    def __init__(self):
        self.required_patterns = [
            r'\$\d+(?:\.\d+)?(?:k|m|b|bn|t|tn)?',  # Currency amounts
            r'\d+(?:\.\d+)?%',  # Percentages
            r'\d+(?:\.\d+)?x',  # Multiples
            r'\d+(?:\.\d+)?\s*(?:million|billion|trillion)',  # Large numbers
            r'\d+\s*(?:bps|basis\s+points?)',  # Basis points
        ]
        
        self.key_metrics = [
            'revenue',
            'earnings',
            'profit margin',
            'market share',
            'growth rate',
            'valuation',
            'price target',
            'trading volume',
            'volatility',
            'dividend yield'
        ]

    def validate_extracted_text(self, text: str) -> ValidationResult:
        """
        Validate extracted text quality.
        
        Args:
            text: Text to validate
            
        Returns:
            ValidationResult with validation status and issues
        """
        if not text or not text.strip():
            return ValidationResult(False, ["Empty or whitespace-only text"], {})

        issues = []
        metrics = self._extract_metrics(text)
        
        # Calculate text metrics
        text_metrics = self._calculate_metrics(text)
        
        # Check minimum content
        if text_metrics.total_words < 50:
            issues.append("Text too short (minimum 50 words required)")
            
        # Check special character ratio
        if text_metrics.special_char_ratio > 0.3:
            issues.append("Too many special characters (maximum 30% allowed)")
            
        # Check sentence structure
        if text_metrics.avg_sentence_length < 5:
            issues.append("Sentences too short (minimum average 5 words)")
            
        # Check numerical content
        if text_metrics.numerical_density < 0.01:
            issues.append("Insufficient numerical data (minimum 1% required)")
            
        # Check for substantial lines
        lines = text.strip().split('\n')
        if not any(len(line.strip()) > 20 for line in lines):
            issues.append("No substantial lines found (minimum 20 characters)")
            
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            metrics=metrics
        )

    def validate_summary(self, summary: str, original_metrics: Dict[str, List[str]]) -> ValidationResult:
        """
        Validate summary quality and data preservation.
        
        Args:
            summary: Summary to validate
            original_metrics: Metrics from original text
            
        Returns:
            ValidationResult with validation status and issues
        """
        if not summary or not summary.strip():
            return ValidationResult(False, ["Empty or whitespace-only summary"], {})
            
        issues = []
        preserved_metrics = self._extract_metrics(summary)
        
        # Check data preservation
        if original_metrics:
            preserved_count = sum(
                1 for metric, values in original_metrics.items()
                for value in values
                if metric in preserved_metrics and any(
                    self._similar_value(value, pv) 
                    for pv in preserved_metrics[metric]
                )
            )
            total_metrics = sum(len(values) for values in original_metrics.values())
            
            if total_metrics > 0 and preserved_count < total_metrics * 0.7:
                issues.append(
                    f"Insufficient data preservation ({preserved_count}/{total_metrics} metrics preserved)"
                )
        
        # Check summary structure
        text_metrics = self._calculate_metrics(summary)
        
        if text_metrics.total_words < 100:
            issues.append("Summary too short (minimum 100 words required)")
            
        if text_metrics.avg_sentence_length < 10:
            issues.append("Sentences too short (minimum average 10 words)")
            
        if text_metrics.numerical_density < 0.02:
            issues.append("Insufficient numerical data in summary (minimum 2% required)")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            metrics=preserved_metrics
        )

    def _calculate_metrics(self, text: str) -> ValidationMetrics:
        """Calculate various metrics for text quality assessment."""
        # Clean text
        clean_text = text.strip()
        
        # Count words
        words = clean_text.split()
        total_words = len(words)
        
        # Calculate sentence length
        sentences = re.split(r'[.!?]+', clean_text)
        valid_sentences = [s.strip() for s in sentences if s.strip()]
        avg_sentence_length = (
            sum(len(s.split()) for s in valid_sentences) / len(valid_sentences)
            if valid_sentences else 0
        )
        
        # Calculate special character ratio
        special_chars = sum(1 for c in clean_text if not c.isalnum() and not c.isspace())
        special_char_ratio = special_chars / len(clean_text) if clean_text else 0
        
        # Calculate numerical density
        numerical_chars = sum(1 for c in clean_text if c.isdigit())
        numerical_density = numerical_chars / len(clean_text) if clean_text else 0
        
        return ValidationMetrics(
            total_words=total_words,
            avg_sentence_length=avg_sentence_length,
            special_char_ratio=special_char_ratio,
            numerical_density=numerical_density
        )

    def _extract_metrics(self, text: str) -> Dict[str, List[str]]:
        """Extract key financial metrics from text."""
        metrics = {}
        
        # Extract metrics using patterns
        for metric in self.key_metrics:
            pattern = fr'(?i)(?:{metric})\s*(?::|of|at|is|was|=)?\s*([^.]*)'
            matches = re.finditer(pattern, text)
            values = []
            
            for match in matches:
                value = match.group(1).strip()
                # Verify value contains a number
                if re.search(r'\d', value):
                    values.append(value)
                    
            if values:
                metrics[metric] = values
                
        # Extract standalone numerical data
        for pattern in self.required_patterns:
            matches = re.finditer(pattern, text)
            values = [match.group(0) for match in matches]
            if values:
                metrics[f'raw_{pattern}'] = values
                
        return metrics

    def _similar_value(self, val1: str, val2: str) -> bool:
        """Check if two metric values are similar (accounting for formatting differences)."""
        # Clean and normalize values
        val1 = re.sub(r'[^\d.%$kmbt]', '', val1.lower())
        val2 = re.sub(r'[^\d.%$kmbt]', '', val2.lower())
        
        # Extract numbers
        num1 = re.findall(r'\d+(?:\.\d+)?', val1)
        num2 = re.findall(r'\d+(?:\.\d+)?', val2)
        
        if not num1 or not num2:
            return False
            
        # Compare numbers with tolerance
        try:
            return abs(float(num1[0]) - float(num2[0])) < 0.01
        except ValueError:
            return False
