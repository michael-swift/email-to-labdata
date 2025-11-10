import pytest
import asyncio
import os
import sys
from pathlib import Path
from typing import Generator, Dict, Any
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock
from faker import Faker

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set test environment
os.environ["ENVIRONMENT"] = "test"

fake = Faker()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_nanodrop_data():
    """Generate mock Nanodrop data."""
    return {
        "sample_id": f"Sample_{fake.random_int(1, 1000)}",
        "concentration": round(fake.random.uniform(10.0, 5000.0), 1),
        "unit": "ng/μL",
        "a260": round(fake.random.uniform(0.1, 50.0), 3),
        "a280": round(fake.random.uniform(0.1, 30.0), 3),
        "a230": round(fake.random.uniform(0.1, 25.0), 3),
        "ratio_260_280": round(fake.random.uniform(1.7, 2.1), 2),
        "ratio_260_230": round(fake.random.uniform(1.8, 2.3), 2),
        "measurement_date": fake.date_time_this_year().isoformat(),
    }


@pytest.fixture
def mock_email_payload():
    """Generate mock email webhook payload."""
    return {
        "to": "data@test.nanodrop-capture.com",
        "from": fake.email(),
        "subject": "Nanodrop Reading - " + fake.word(),
        "text": "Please process this nanodrop image",
        "attachments": 1,
        "attachment1": {
            "filename": "nanodrop_image.jpg",
            "type": "image/jpeg",
            "content": "base64_encoded_test_content"
        }
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = Mock()
    
    # Mock successful response
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content='{"sample_id": "TEST001", "concentration": 1234.5}'))
    ]
    
    client.chat.completions.create = Mock(return_value=mock_response)
    return client


@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    service = Mock()
    service.send_success_email = AsyncMock()
    service.send_error_email = AsyncMock()
    return service


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = Mock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    return client


@pytest.fixture
def sample_image_bytes():
    """Generate a simple test image."""
    from PIL import Image, ImageDraw
    import io

    # Create a simple test image with some content (to ensure size > 10KB for tests)
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    # Add some visual content to increase file size
    for i in range(0, 800, 20):
        draw.line([(i, 0), (i, 600)], fill='lightgray', width=1)
    for i in range(0, 600, 20):
        draw.line([(0, i), (800, i)], fill='lightgray', width=1)

    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG', quality=95)
    return img_bytes.getvalue()


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "environment": "test",
        "debug": True,
        "database_url": "sqlite:///./test.db",
        "redis_url": "redis://localhost:6379/1",
        "temp_storage_path": "/tmp/nanodrop_test",
        "max_image_size_mb": 10,
        "processing_timeout_seconds": 30,
        "llm_model": "gpt-4-vision-preview",
        "from_email": "test@nanodrop-capture.com",
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    test_env = {
        "ENVIRONMENT": "test",
        "DEBUG": "True",
        "DATABASE_URL": "sqlite:///./test.db",
        "REDIS_URL": "redis://localhost:6379/1",
        "TEMP_STORAGE_PATH": "/tmp/nanodrop_test",
    }
    
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow"
    )
    config.addinivalue_line(
        "markers", "llm: mark test as requiring LLM API"
    )