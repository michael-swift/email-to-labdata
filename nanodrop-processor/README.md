# Nanodrop Testing Framework

A comprehensive testing framework for the Nanodrop email processing system. This framework provides tools for testing image processing, LLM extraction, and data validation components.

## Quick Start

```bash
# Install dependencies
make install

# Run all tests
make test

# Run specific test types
./run_tests.sh -t unit         # Unit tests only
./run_tests.sh -t image        # Image processing tests
./run_tests.sh -t llm          # LLM mock tests
./run_tests.sh -t validation   # Data validation tests

# Run with coverage
./run_tests.sh -c

# Run with verbose output
./run_tests.sh -v
```

## Project Structure

```
nanodrop-processor/
├── src/                      # Source code (to be implemented)
├── tests/
│   ├── conftest.py          # Pytest configuration and fixtures
│   ├── test_base.py         # Basic setup tests
│   ├── unit/
│   │   ├── test_image_processing.py
│   │   ├── test_mock_llm.py
│   │   └── test_data_validation.py
│   ├── integration/         # Integration tests (future)
│   └── fixtures/
│       ├── nanodrop_samples.py    # Sample data
│       └── image_generator.py     # Mock image generator
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Project configuration
├── Makefile                # Build commands
└── run_tests.sh           # Test runner script
```

## Key Features

### 1. Mock Image Generation
- Generates realistic Nanodrop screen images
- Supports various quality levels (perfect, blurry, rotated)
- Different Nanodrop models (One, 2000, Eight)
- Customizable sample data

### 2. LLM Mock Testing
- Mock LLM responses for testing
- Response validation
- Retry logic testing
- Multiple response format handling

### 3. Data Validation
- Comprehensive validation rules
- Quality assessment
- Contamination detection
- Cross-validation of measurements

### 4. Test Fixtures
- Pre-defined sample data
- Mock services (email, Redis, LLM)
- Reusable test utilities

## Running Tests

### Using Make

```bash
# Install dependencies
make install

# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
make test-file FILE=tests/unit/test_image_processing.py

# Lint code
make lint

# Format code
make format
```

### Using the Test Runner

```bash
# Run all tests
./run_tests.sh

# Run specific test type
./run_tests.sh -t unit

# Run with options
./run_tests.sh -t image -v -c  # Image tests, verbose, with coverage

# Get help
./run_tests.sh -h
```

### Direct Pytest Commands

```bash
# Run all tests
pytest

# Run with markers
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only

# Run specific file
pytest tests/unit/test_image_processing.py -v

# Run with coverage
pytest --cov=src --cov-report=html
```

## Test Categories

### Unit Tests
- `test_image_processing.py`: Image generation and validation
- `test_mock_llm.py`: LLM response mocking and parsing
- `test_data_validation.py`: Data validation and quality assessment

### Integration Tests
- Future: End-to-end email processing
- Future: Real LLM API testing
- Future: Database operations

## Writing New Tests

### Example Test Structure

```python
import pytest
from tests.fixtures.nanodrop_samples import NANODROP_SAMPLES

class TestNewFeature:
    @pytest.fixture
    def setup_data(self):
        # Setup test data
        return {"test": "data"}
    
    @pytest.mark.unit
    def test_feature_works(self, setup_data, mock_llm_client):
        # Test implementation
        result = process_data(setup_data)
        assert result is not None
```

### Using Fixtures

```python
def test_with_fixtures(mock_nanodrop_data, mock_email_payload, sample_image_bytes):
    # mock_nanodrop_data: Sample Nanodrop measurements
    # mock_email_payload: Sample email webhook data
    # sample_image_bytes: Sample image in bytes
    pass
```

## CI/CD Integration

The project includes GitHub Actions workflow for continuous testing:

- Tests on Python 3.9, 3.10, 3.11
- Linting and type checking
- Coverage reporting
- Automatic test runs on push/PR

## Next Steps

1. **Implement Source Code**: Create the actual processing logic in `src/`
2. **Add Integration Tests**: Test the complete email-to-CSV pipeline
3. **Real Image Testing**: Add actual Nanodrop photos to test fixtures
4. **Performance Testing**: Add benchmarks for image processing
5. **Load Testing**: Test system under high email volume

## Contributing

1. Write tests for new features
2. Ensure all tests pass
3. Maintain >80% code coverage
4. Follow the existing code style
5. Update documentation as needed