"""Shared pytest fixtures."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import logging
from pathlib import Path
from typing import Dict, Any, Generator
from _pytest.logging import caplog as _caplog
from dataclasses import dataclass

from services.chunk_manager import ChunkManager
from services.prompt_manager import PromptManager
from services.validation_service import ValidationService
from services.metrics_extractor import MetricsExtractor
from tests.mocks.openai_client import MockOpenAIClient
from tests.helpers import (
    create_test_context,
    create_summary_config,
    setup_test_environment,
    cleanup_test_environment,
    create_sample_text
)

@pytest.fixture
def sample_text() -> str:
    """Create sample text for testing."""
    return create_sample_text()

# Configure logging for tests
@pytest.fixture
def caplog(_caplog):
    """Configure logging for test capture."""
    class PropagatingHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = _caplog.handler.name
    logger = logging.getLogger()
    
    # Add propagating handler
    handler = PropagatingHandler()
    handler.name = handler_id
    logger.addHandler(handler)
    
    # Set level to DEBUG for tests
    logger.setLevel(logging.DEBUG)
    
    yield _caplog
    
    # Cleanup
    logger.removeHandler(handler)

@pytest.fixture(scope="session", autouse=True)
def test_environment():
    """Set up and tear down test environment."""
    setup_test_environment()
    yield
    cleanup_test_environment()

@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Get path to test data directory."""
    return Path(__file__).parent / 'fixtures'

@pytest.fixture(scope="session")
def responses_path(test_data_dir) -> str:
    """Get path to test responses file."""
    return str(test_data_dir / 'responses.json')

@pytest.fixture
def mock_openai_client(responses_path) -> MockOpenAIClient:
    """Create mock OpenAI client."""
    return MockOpenAIClient(responses_path)

@pytest.fixture
def chunk_manager() -> ChunkManager:
    """Create ChunkManager instance."""
    return ChunkManager()

@pytest.fixture
def prompt_manager() -> PromptManager:
    """Create PromptManager instance."""
    return PromptManager()

@pytest.fixture
def validation_service() -> ValidationService:
    """Create ValidationService instance."""
    return ValidationService()

@pytest.fixture
def metrics_extractor() -> MetricsExtractor:
    """Create MetricsExtractor instance."""
    return MetricsExtractor()

@pytest.fixture
def test_context(responses_path) -> Generator:
    """Create test context with mock clients."""
    context = create_test_context(responses_path)
    yield context
    context.cleanup()

@pytest.fixture
def summary_config() -> Dict[str, Any]:
    """Create test summary configuration."""
    return create_summary_config()

@pytest.fixture
def temp_output_dir(tmp_path) -> Path:
    """Create temporary directory for test outputs."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir(exist_ok=True)
    return output_dir

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables."""
    env_vars = {
        'OPENAI_API_KEY': 'test-key',
        'DROPBOX_REFRESH_TOKEN': 'test-token',
        'DROPBOX_APP_KEY': 'test-app-key',
        'DROPBOX_APP_SECRET': 'test-app-secret'
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars

@pytest.fixture
def error_details() -> Dict[str, Any]:
    """Create test error details."""
    return {
        'model': 'gpt-4o',
        'token_count': 1000,
        'max_tokens': 2000,
        'text_preview': 'Test text...',
        'recovery_action': 'Retry with different parameters'
    }

@dataclass
class ServiceContext:
    """Container for service instances used in tests."""
    openai_client: MockOpenAIClient
    chunk_manager: ChunkManager
    prompt_manager: PromptManager
    validation_service: ValidationService
    metrics_extractor: MetricsExtractor

@pytest.fixture
def service_context(
    mock_openai_client,
    chunk_manager,
    prompt_manager,
    validation_service,
    metrics_extractor
) -> ServiceContext:
    """Create context with all service instances."""
    return ServiceContext(
        openai_client=mock_openai_client,
        chunk_manager=chunk_manager,
        prompt_manager=prompt_manager,
        validation_service=validation_service,
        metrics_extractor=metrics_extractor
    )

# Custom markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )

# Skip slow tests by default
def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow tests"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on options."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
