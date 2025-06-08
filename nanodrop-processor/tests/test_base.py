import pytest
from pathlib import Path


class TestProjectSetup:
    """Test basic project setup and configuration."""
    
    @pytest.mark.unit
    def test_project_structure_exists(self):
        """Test that the basic project structure is in place."""
        project_root = Path(__file__).parent.parent
        
        # Check main directories
        assert (project_root / "tests").exists()
        assert (project_root / "images").exists()
        assert (project_root / "extracted_data").exists()
        
        # Check main files
        assert (project_root / "lambda_function.py").exists()
        assert (project_root / "llm_extractor.py").exists()
        
        # Check test subdirectories
        test_dirs = ["unit", "fixtures"]
        for dir_name in test_dirs:
            assert (project_root / "tests" / dir_name).exists()
    
    @pytest.mark.unit
    def test_configuration_files_exist(self):
        """Test that necessary configuration files exist."""
        project_root = Path(__file__).parent.parent
        
        assert (project_root / "requirements.txt").exists()
        assert (project_root / "pyproject.toml").exists()
        assert (project_root / ".env.test").exists()
    
    @pytest.mark.unit
    def test_fixtures_loaded(self, mock_nanodrop_data, mock_email_payload):
        """Test that pytest fixtures are properly loaded."""
        assert mock_nanodrop_data is not None
        assert "sample_id" in mock_nanodrop_data
        assert "concentration" in mock_nanodrop_data
        
        assert mock_email_payload is not None
        assert "to" in mock_email_payload
        assert "from" in mock_email_payload
        assert "attachments" in mock_email_payload
    
    @pytest.mark.unit
    def test_mock_services(self, mock_llm_client, mock_email_service, mock_redis_client):
        """Test that mock services are properly configured."""
        assert mock_llm_client is not None
        assert hasattr(mock_llm_client.chat.completions, "create")
        
        assert mock_email_service is not None
        assert hasattr(mock_email_service, "send_success_email")
        
        assert mock_redis_client is not None
        assert hasattr(mock_redis_client, "get")