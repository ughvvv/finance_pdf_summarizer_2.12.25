"""Helper functions and fixtures for testing."""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass

from services.summarizer_service import SummaryConfig
from tests.mocks.openai_client import MockOpenAIClient

@dataclass
class TestContext:
    """Context manager for test setup and cleanup."""
    openai_client: MockOpenAIClient
    test_data: Dict[str, Any]
    temp_files: List[str] = None
    
    def __post_init__(self):
        self.temp_files = []
    
    def cleanup(self):
        """Clean up temporary files."""
        for file_path in self.temp_files:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception as e:
                print(f"Warning: Failed to delete {file_path}: {e}")

def load_test_data(filename: str = 'responses.json') -> Dict[str, Any]:
    """
    Load test data from JSON file in fixtures directory.
    
    Args:
        filename: Name of JSON file in fixtures directory
        
    Returns:
        Dictionary containing test data
    """
    fixtures_dir = Path(__file__).parent / 'fixtures'
    file_path = fixtures_dir / filename
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load test data from {file_path}: {e}")

def create_test_pdf(content: str, output_dir: Optional[str] = None) -> str:
    """
    Create a test PDF file with given content.
    
    Args:
        content: Text content for PDF
        output_dir: Optional directory to save PDF (defaults to fixtures directory)
        
    Returns:
        Path to created PDF file
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / 'fixtures'
    else:
        output_dir = Path(output_dir)
        
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'test.pdf'
    
    # Create PDF using reportlab
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    c = canvas.Canvas(str(output_path), pagesize=letter)
    text_object = c.beginText(40, 750)  # Start 40 points in, 750 up
    text_object.setFont('Helvetica', 12)
    
    # Split content into lines
    for line in content.split('\n'):
        text_object.textLine(line)
    
    c.drawText(text_object)
    c.save()
    
    return str(output_path)

def create_test_config() -> Dict[str, Any]:
    """Create test configuration dictionary."""
    return {
        'openai_key': 'test-key',
        'dropbox_refresh_token': 'test-token',
        'dropbox_app_key': 'test-app-key',
        'dropbox_app_secret': 'test-app-secret',
        'email_sender': 'test@example.com',
        'email_recipients': ['recipient@example.com'],
        'smtp_host': 'smtp.example.com',
        'smtp_port': 587,
        'smtp_username': 'test-user',
        'smtp_password': 'test-pass'
    }

def setup_test_environment():
    """Set up test environment variables."""
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['DROPBOX_REFRESH_TOKEN'] = 'test-token'
    os.environ['DROPBOX_APP_KEY'] = 'test-app-key'
    os.environ['DROPBOX_APP_SECRET'] = 'test-app-secret'

def cleanup_test_environment():
    """Clean up test environment variables."""
    test_vars = [
        'OPENAI_API_KEY',
        'DROPBOX_REFRESH_TOKEN',
        'DROPBOX_APP_KEY',
        'DROPBOX_APP_SECRET'
    ]
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]

def create_test_report(name: str = 'test_report.pdf') -> Dict[str, Any]:
    """Create test report dictionary."""
    return {
        'file_name': name,
        'text': (
            "This is a test report containing sample financial data.\n\n"
            "Key metrics:\n"
            "- Revenue: $1,000,000\n"
            "- Profit: $250,000\n"
            "- Growth: 15%\n\n"
            "Analysis shows positive trends in all major categories."
        )
    }

def compare_summaries(actual: str, expected: str) -> bool:
    """
    Compare actual and expected summaries, ignoring whitespace differences.
    
    Args:
        actual: Actual summary text
        expected: Expected summary text
        
    Returns:
        True if summaries match, False otherwise
    """
    def normalize(text: str) -> str:
        """Normalize text for comparison."""
        return ' '.join(text.split())
    
    return normalize(actual) == normalize(expected)

def create_test_context(responses_path: Optional[str] = None) -> TestContext:
    """
    Create test context with mock clients and test data.
    
    Args:
        responses_path: Optional path to custom responses file
        
    Returns:
        TestContext object
    """
    openai_client = MockOpenAIClient(responses_path)
    test_data = load_test_data()
    return TestContext(openai_client=openai_client, test_data=test_data)

def create_summary_config(model: str = 'gpt-4o') -> SummaryConfig:
    """
    Create test summary configuration.
    
    Args:
        model: Model name to use
        
    Returns:
        SummaryConfig object
    """
    test_data = load_test_data()
    model_config = test_data['models'][model]
    return SummaryConfig(
        model=model,
        context_window=model_config['context_window'],
        max_output_tokens=model_config['max_output_tokens'],
        min_output_tokens=model_config['min_output_tokens']
    )

async def run_async_test(coro):
    """
    Run async test coroutine.
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Test result
    """
    return await asyncio.get_event_loop().create_task(coro)

def assert_error_details(error: Exception, expected_details: Dict[str, Any]):
    """
    Assert error details match expected values.
    
    Args:
        error: Exception to check
        expected_details: Dictionary of expected error details
    """
    for key, value in expected_details.items():
        assert hasattr(error, key), f"Error missing expected attribute: {key}"
        assert getattr(error, key) == value, (
            f"Error {key} mismatch: expected {value}, got {getattr(error, key)}"
        )

def create_sample_text() -> str:
    """Create sample financial text for testing."""
    return """
Q4 2024 Financial Performance Overview

Revenue and Growth:
- Total revenue: $2.85 billion (up 18% YoY)
- Subscription revenue: $1.95 billion (up 22%)
- Professional services: $900 million (up 15%)

Profitability Metrics:
- Gross margin: 72% (up from 68% in Q4 2023)
- Operating margin: 15% (up from 12%)
- EBITDA margin: 25% (up from 22%)

Key Performance Indicators:
- Active enterprise customers: 15,000 (+25% YoY)
- Net revenue retention rate: 125%
- Average contract value: $185,000 (+15% YoY)
- International revenue: 35% of total

Market Analysis:
- Market share increased to 28% in enterprise segment
- Competitive position strengthened in APAC region
- Supply chain costs decreased 12% QoQ
- Raw material prices stabilized after Q3 volatility

Forward-Looking Guidance:
- FY2025 revenue growth target: 20-22%
- Planned expansion into emerging markets
- R&D investments to increase by 25%
- Target operating margin of 18% by Q4 2025

Risk Factors:
- Geopolitical tensions affecting EMEA operations
- Currency fluctuations impact on international revenue
- Regulatory changes in data privacy landscape
- Increased competition in core markets

Strategic Initiatives:
1. Accelerate APAC market penetration
2. Implement new currency hedging strategies
3. Enhance data privacy compliance tools
4. Explore strategic partnerships
"""
