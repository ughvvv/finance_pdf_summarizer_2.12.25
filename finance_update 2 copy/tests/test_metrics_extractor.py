"""Tests for the MetricsExtractor."""

import pytest
from typing import Dict, Any
import re

from services.metrics_extractor import MetricsExtractor
from utils.exceptions import MetricsError
from tests.helpers import (
    create_test_report,
    assert_error_details
)

@pytest.fixture
def metrics_extractor() -> MetricsExtractor:
    """Create MetricsExtractor instance."""
    return MetricsExtractor()

@pytest.fixture
def sample_text() -> str:
    """Create sample text with various metrics."""
    return (
        "Financial Report Q3 2023\n\n"
        "Key Performance Metrics:\n"
        "- Revenue: $1,234,567.89\n"
        "- Growth Rate: +15.7%\n"
        "- Profit Margin: 23.4%\n"
        "- Market Share: 12.5%\n"
        "- Operating Costs: $789,012.34\n"
        "- ROI: 18.9%\n\n"
        "Year-over-Year Comparison:\n"
        "- 2022 Revenue: $1,000,000\n"
        "- 2023 Revenue: $1,234,567.89\n"
        "- YoY Growth: 23.4%\n\n"
        "Market Analysis:\n"
        "The company saw a significant increase from $1.0M to $1.2M in revenue."
    )

@pytest.fixture
def complex_metrics() -> str:
    """Create text with complex metric formats."""
    return (
        "Detailed Metrics:\n"
        "- Revenue Range: $1.2M - $1.5M\n"
        "- Growth: 15.7% to 18.3%\n"
        "- Costs: $500k-$750k\n"
        "- Market Cap: $2.5B\n"
        "- Share Price: $123.45\n"
        "- Volume: 1.2M shares\n"
        "- P/E Ratio: 15.7x\n"
        "- Debt/Equity: 0.8x\n"
        "- Beta: 1.15\n"
        "- 52-week range: $98.76 - $142.53"
    )

def test_extract_metrics_basic(metrics_extractor, sample_text):
    """Test basic metric extraction."""
    # Act
    metrics = metrics_extractor.extract_metrics(sample_text)
    
    # Assert
    assert metrics is not None
    assert len(metrics) > 0
    assert metrics['revenue'] == 1234567.89
    assert metrics['growth_rate'] == 15.7
    assert metrics['profit_margin'] == 23.4
    assert metrics['market_share'] == 12.5

def test_extract_metrics_empty(metrics_extractor):
    """Test handling of empty text."""
    # Act & Assert
    with pytest.raises(MetricsError) as exc_info:
        metrics_extractor.extract_metrics("")
    
    error = exc_info.value
    assert "empty text" in str(error).lower()
    assert error.details['source'] == 'empty_input'

def test_extract_metrics_no_numbers(metrics_extractor):
    """Test handling of text without metrics."""
    # Arrange
    text = "This text contains no numerical metrics or data."
    
    # Act & Assert
    with pytest.raises(MetricsError) as exc_info:
        metrics_extractor.extract_metrics(text)
    
    error = exc_info.value
    assert "no metrics found" in str(error).lower()
    assert error.details['source'] == 'no_metrics'

def test_extract_complex_metrics(metrics_extractor, complex_metrics):
    """Test extraction of complex metric formats."""
    # Act
    metrics = metrics_extractor.extract_metrics(complex_metrics)
    
    # Assert
    assert metrics['revenue_min'] == 1200000  # $1.2M
    assert metrics['revenue_max'] == 1500000  # $1.5M
    assert metrics['market_cap'] == 2500000000  # $2.5B
    assert metrics['share_price'] == 123.45
    assert metrics['pe_ratio'] == 15.7
    assert metrics['beta'] == 1.15

def test_extract_metrics_with_ranges(metrics_extractor):
    """Test extraction of metric ranges."""
    # Arrange
    text = (
        "Revenue range: $100k - $150k\n"
        "Growth forecast: 5% to 7%\n"
        "Market share target: 10-15%"
    )
    
    # Act
    metrics = metrics_extractor.extract_metrics(text)
    
    # Assert
    assert metrics['revenue_min'] == 100000
    assert metrics['revenue_max'] == 150000
    assert metrics['growth_min'] == 5
    assert metrics['growth_max'] == 7
    assert metrics['market_share_min'] == 10
    assert metrics['market_share_max'] == 15

def test_extract_historical_metrics(metrics_extractor, sample_text):
    """Test extraction of historical metrics."""
    # Act
    metrics = metrics_extractor.extract_historical_metrics(sample_text)
    
    # Assert
    assert len(metrics) >= 2  # At least two time periods
    assert metrics['2022']['revenue'] == 1000000
    assert metrics['2023']['revenue'] == 1234567.89
    assert metrics['yoy_growth'] == 23.4

def test_analyze_trends(metrics_extractor):
    """Test trend analysis."""
    # Arrange
    historical_data = {
        '2021': {'revenue': 800000, 'growth': 10},
        '2022': {'revenue': 1000000, 'growth': 25},
        '2023': {'revenue': 1234567.89, 'growth': 23.4}
    }
    
    # Act
    trends = metrics_extractor.analyze_trends(historical_data)
    
    # Assert
    assert 'revenue_trend' in trends
    assert 'growth_trend' in trends
    assert trends['revenue_trend'] == 'increasing'
    assert isinstance(trends['cagr'], float)

def test_validate_metrics(metrics_extractor):
    """Test metric validation."""
    # Arrange
    metrics = {
        'revenue': 1000000,
        'growth': -150,  # Invalid growth rate
        'margin': 200,   # Invalid percentage
        'share_price': -50  # Invalid negative price
    }
    
    # Act & Assert
    with pytest.raises(MetricsError) as exc_info:
        metrics_extractor.validate_metrics(metrics)
    
    error = exc_info.value
    assert "invalid metrics" in str(error).lower()
    assert len(error.details['invalid_metrics']) > 0

def test_normalize_metrics(metrics_extractor):
    """Test metric normalization."""
    # Arrange
    raw_metrics = {
        'Revenue': '$1.2M',
        'Growth Rate': '15.7%',
        'Market_Share': '12.5 percent',
        'share price': '$123.45'
    }
    
    # Act
    normalized = metrics_extractor.normalize_metrics(raw_metrics)
    
    # Assert
    assert normalized['revenue'] == 1200000
    assert normalized['growth_rate'] == 15.7
    assert normalized['market_share'] == 12.5
    assert normalized['share_price'] == 123.45

def test_extract_metrics_with_context(metrics_extractor):
    """Test metric extraction with contextual information."""
    # Arrange
    text = (
        "In Q3 2023, revenue increased by 15% to $1.2M.\n"
        "This follows the Q2 revenue of $1.0M.\n"
        "Year-to-date growth stands at 25%."
    )
    
    # Act
    metrics = metrics_extractor.extract_metrics_with_context(text)
    
    # Assert
    assert metrics['q3_2023']['revenue'] == 1200000
    assert metrics['q2_2023']['revenue'] == 1000000
    assert metrics['q3_2023']['growth'] == 15
    assert metrics['ytd']['growth'] == 25

def test_extract_metrics_edge_cases(metrics_extractor):
    """Test metric extraction edge cases."""
    edge_cases = {
        'scientific': "Revenue: 1.23e6 dollars",
        'fractions': "Market share: 12 1/2 percent",
        'mixed': "Growth of twelve point five percent",
        'unicode': "Revenue: €1.5M",
        'formatted': "Revenue: $1,234,567.89",
        'abbreviated': "Rev: $1.2M, Gr: 15%, MS: 12.5%"
    }
    
    for case, text in edge_cases.items():
        # Act
        metrics = metrics_extractor.extract_metrics(text)
        
        # Assert
        assert len(metrics) > 0, f"Failed to extract metrics from {case}"
        assert all(isinstance(v, (int, float)) for v in metrics.values())

def test_extract_metrics_with_report(metrics_extractor):
    """Test metric extraction with test report data."""
    # Arrange
    report = create_test_report()
    
    # Act
    metrics = metrics_extractor.extract_metrics(report['text'])
    
    # Assert
    assert metrics is not None
    assert 'revenue' in metrics
    assert metrics['revenue'] == 1000000
    assert metrics['growth'] == 15
