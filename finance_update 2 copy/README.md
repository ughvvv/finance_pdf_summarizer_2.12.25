# Finance Update Project

[![Test](../../actions/workflows/test.yml/badge.svg)](../../actions/workflows/test.yml)
[![Coverage](./coverage.svg)](./coverage_html/index.html)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Financial report processing and analysis pipeline with automated summarization and metrics extraction.

## Features

- PDF report processing and text extraction
- Intelligent text summarization using OpenAI models
- Financial metrics extraction and analysis
- Parallel batch processing with retry mechanisms
- Comprehensive validation and error handling
- A/B testing support for prompt optimization
- Detailed progress tracking and reporting

## Installation

1. Install Poetry (package manager):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

## Development Setup

1. Install development dependencies:
```bash
poetry install --with dev
```

2. Set up pre-commit hooks:
```bash
poetry run pre-commit install
```

3. Install NLTK data:
```bash
poetry run python setup_nltk.py
```

## Testing

The project uses pytest for testing with comprehensive coverage requirements.

### Running Tests

Basic test run:
```bash
./scripts/run_tests.sh
```

With options:
```bash
# Run with parallel execution
./scripts/run_tests.sh --parallel

# Include slow tests
./scripts/run_tests.sh --with-slow

# Include integration tests
./scripts/run_tests.sh --with-integration

# Run all test types in parallel
./scripts/run_tests.sh --parallel --with-slow --with-integration
```

### Test Structure

- `tests/`: Unit tests for individual components
- `tests/integration/`: Integration tests for service interactions
- `tests/fixtures/`: Shared test data and fixtures
- `tests/mocks/`: Mock implementations for testing

### Coverage Requirements

- Minimum coverage: 90%
- Branch coverage enabled
- Coverage reports:
  - Terminal summary
  - HTML report (`coverage_html/index.html`)
  - XML report for CI integration
  - Coverage badge (auto-updated)

## Load Testing

The project includes comprehensive load testing infrastructure using Locust.

### Running Load Tests

Basic load test:
```bash
./scripts/run_load_tests.sh
```

With options:
```bash
# Run specific scenario
./scripts/run_load_tests.sh --scenario single

# Configure test parameters
./scripts/run_load_tests.sh \
    --duration 600 \
    --users 20 \
    --spawn-rate 2 \
    --workers 4
```

### Test Scenarios

1. **Single Report Processing**
   ```bash
   ./scripts/run_load_tests.sh --scenario single
   ```
   Tests processing of individual reports with varying sizes.

2. **Batch Processing**
   ```bash
   ./scripts/run_load_tests.sh --scenario batch
   ```
   Tests concurrent batch processing with different batch sizes.

3. **Long-Running Operations**
   ```bash
   ./scripts/run_load_tests.sh --scenario long-running
   ```
   Tests processing of large reports with extended durations.

4. **Mixed Workload**
   ```bash
   ./scripts/run_load_tests.sh --scenario mixed
   ```
   Tests combination of different operation types.

### Test Results

Load test results are saved in the `load_test_results` directory:

```
load_test_results/
├── reports/
│   ├── single_stats.csv
│   ├── batch_stats.csv
│   ├── long-running_stats.csv
│   └── mixed_stats.csv
├── metrics/
│   └── system_metrics.csv
└── combined_report.json
```

Key metrics include:
- Requests per second
- Response times (average, p95, p99)
- Error rates
- System resource usage (CPU, memory, I/O)

### Performance Monitoring

The load testing infrastructure includes real-time monitoring of:

1. **System Metrics**
   - CPU usage
   - Memory utilization
   - Disk I/O
   - Network traffic

2. **Application Metrics**
   - Request throughput
   - Response times
   - Error rates
   - Queue lengths

3. **Resource Usage**
   - Process memory
   - Thread count
   - File descriptors
   - Network connections

### Interpreting Results

The combined report (`combined_report.json`) provides:

1. **Scenario Performance**
   - Success rates
   - Response times
   - Throughput rates
   - Error patterns

2. **System Performance**
   - Resource utilization
   - Bottleneck identification
   - Scaling indicators
   - Performance trends

3. **Recommendations**
   - Resource allocation
   - Concurrency settings
   - Batch size optimization
   - Error handling improvements

## Project Structure

```
.
├── services/           # Core service implementations
├── utils/             # Utility functions and helpers
├── clients/           # External API clients
├── tests/             # Test suite
│   ├── integration/   # Integration tests
│   ├── fixtures/      # Test fixtures
│   └── mocks/         # Mock implementations
├── scripts/           # Development and CI scripts
└── memlog/           # Project documentation and logs
```

## Service Architecture

1. **Core Services**
   - `SummarizerService`: Text summarization with token management
   - `BatchProcessor`: Parallel processing with progress tracking
   - `PromptManager`: Prompt template management and A/B testing
   - `ValidationService`: Text validation and error handling
   - `MetricsExtractor`: Financial metrics extraction
   - `ChunkManager`: Text chunking and optimization

2. **Support Services**
   - `TextProcessor`: Text manipulation utilities
   - `PDFProcessor`: PDF parsing and text extraction
   - `EmailHandler`: Email notification system

## CI/CD Pipeline

GitHub Actions workflow includes:

1. **Test Job**
   - Runs on Python 3.9 and 3.10
   - Linting with Black, isort, and pylint
   - Type checking with mypy
   - Unit tests with coverage
   - Coverage report upload

2. **Integration Test Job**
   - Runs integration test suite
   - Executes after main test job

3. **Slow Test Job**
   - Runs performance-intensive tests
   - Only executes on main branch

4. **Coverage Badge Update**
   - Updates coverage badge on main branch
   - Generates HTML coverage report

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and ensure coverage
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
