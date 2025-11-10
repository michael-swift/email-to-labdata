import pytest
import json
from unittest.mock import Mock, patch
from tests.fixtures.nanodrop_samples import NANODROP_SAMPLES


class MockLLMExtractor:
    """Mock LLM extractor for testing."""
    
    def __init__(self, response_mapping=None):
        self.response_mapping = response_mapping or {}
        self.call_count = 0
        self.last_image_bytes = None
    
    def extract_nanodrop_data(self, image_bytes: bytes) -> dict:
        """Mock extraction that returns predetermined responses."""
        self.call_count += 1
        self.last_image_bytes = image_bytes
        
        # Return mapped response based on image characteristics
        # In real tests, you might hash the image to map responses
        if len(image_bytes) < 10000:
            return {"error": "Image too small"}
        
        # Default to returning high quality DNA sample
        return NANODROP_SAMPLES["high_quality_dna"]


class TestMockLLMExtraction:
    """Test LLM extraction with mocks."""
    
    @pytest.fixture
    def mock_extractor(self):
        """Create mock LLM extractor."""
        return MockLLMExtractor()
    
    @pytest.mark.unit
    def test_mock_extraction_basic(self, mock_extractor, sample_image_bytes):
        """Test basic mock extraction."""
        result = mock_extractor.extract_nanodrop_data(sample_image_bytes)
        
        assert isinstance(result, dict)
        assert "sample_id" in result
        assert "concentration" in result
        assert mock_extractor.call_count == 1
    
    @pytest.mark.unit
    def test_mock_extraction_error_handling(self, mock_extractor):
        """Test mock extraction with invalid input."""
        # Small image should trigger error
        small_image = b"tiny"
        result = mock_extractor.extract_nanodrop_data(small_image)
        
        assert "error" in result
        assert result["error"] == "Image too small"
    
    @pytest.mark.unit
    def test_llm_response_parsing(self):
        """Test parsing various LLM response formats."""
        def parse_llm_response(response_text: str) -> dict:
            # Handle different response formats
            
            # Try to extract JSON from markdown code blocks
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text
            
            # Clean up the string
            json_str = json_str.strip()
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Try to extract key-value pairs manually
                result = {}
                lines = json_str.split('\n')
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().strip('"')
                        value = value.strip().strip(',').strip('"')
                        try:
                            # Try to convert to number
                            if '.' in value:
                                result[key] = float(value)
                            else:
                                result[key] = int(value)
                        except ValueError:
                            result[key] = value
                return result
        
        # Test various response formats
        test_responses = [
            # Clean JSON
            '{"sample_id": "TEST001", "concentration": 1234.5}',
            
            # JSON in markdown
            '```json\n{"sample_id": "TEST002", "concentration": 2345.6}\n```',
            
            # JSON with extra text
            'Here is the extracted data:\n```\n{"sample_id": "TEST003", "concentration": 3456.7}\n```',
            
            # Malformed but parseable
            '{\n  sample_id: "TEST004",\n  concentration: 4567.8\n}',
        ]
        
        for response in test_responses:
            result = parse_llm_response(response)
            assert isinstance(result, dict)
            assert "sample_id" in result or "concentration" in result
    
    @pytest.mark.unit
    def test_llm_retry_logic(self, mock_extractor):
        """Test retry logic for LLM failures."""
        class FlakeyExtractor:
            def __init__(self):
                self.attempts = 0
            
            def extract_nanodrop_data(self, image_bytes):
                self.attempts += 1
                if self.attempts < 3:
                    raise Exception("Temporary failure")
                return {"sample_id": "SUCCESS", "concentration": 123.4}
        
        extractor = FlakeyExtractor()
        
        # Simulate retry logic
        max_retries = 3
        for i in range(max_retries):
            try:
                result = extractor.extract_nanodrop_data(b"test")
                break
            except Exception as e:
                if i == max_retries - 1:
                    raise
                continue
        
        assert result["sample_id"] == "SUCCESS"
        assert extractor.attempts == 3
    
    @pytest.mark.unit
    def test_llm_response_validation(self):
        """Test validating LLM responses."""
        def validate_extraction_result(result: dict) -> tuple[bool, list[str]]:
            errors = []
            
            # Check required fields
            required_fields = ["concentration", "a260", "a280"]
            for field in required_fields:
                if field not in result:
                    errors.append(f"Missing required field: {field}")
            
            # Validate concentration
            if "concentration" in result:
                conc = result["concentration"]
                if not isinstance(conc, (int, float)):
                    errors.append("Concentration must be a number")
                elif conc < 0:
                    errors.append("Concentration cannot be negative")
                elif conc > 50000:
                    errors.append("Concentration unrealistically high")
            
            # Validate ratios
            if "ratio_260_280" in result:
                ratio = result["ratio_260_280"]
                if not isinstance(ratio, (int, float)):
                    errors.append("260/280 ratio must be a number")
                elif not 0 < ratio < 3:
                    errors.append("260/280 ratio out of valid range")
            
            return len(errors) == 0, errors
        
        # Test valid result
        valid_result = {
            "concentration": 1234.5,
            "a260": 24.69,
            "a280": 13.26,
            "ratio_260_280": 1.86
        }
        is_valid, errors = validate_extraction_result(valid_result)
        assert is_valid
        assert len(errors) == 0
        
        # Test invalid results
        invalid_results = [
            ({}, ["Missing required field: concentration", 
                  "Missing required field: a260", 
                  "Missing required field: a280"]),
            ({"concentration": -100, "a260": 1, "a280": 1}, 
             ["Concentration cannot be negative"]),
            ({"concentration": "not a number", "a260": 1, "a280": 1}, 
             ["Concentration must be a number"]),
            ({"concentration": 100, "a260": 1, "a280": 1, "ratio_260_280": 5}, 
             ["260/280 ratio out of valid range"]),
        ]
        
        for result, expected_errors in invalid_results:
            is_valid, errors = validate_extraction_result(result)
            assert not is_valid
            for expected_error in expected_errors:
                assert any(expected_error in error for error in errors)
    
    @pytest.mark.unit
    def test_mock_different_nanodrop_models(self, mock_extractor, sample_image_bytes):
        """Test extraction from different Nanodrop models."""
        # Different models might have different screen layouts
        model_responses = {
            "nanodrop_one": {
                "model": "NanoDrop One",
                "concentration": 1856.3,
                "unit": "ng/μL"
            },
            "nanodrop_2000": {
                "model": "NanoDrop 2000",
                "concentration": 1856.3,
                "unit": "ng/μL"
            },
            "nanodrop_eight": {
                "model": "NanoDrop Eight",
                "concentration": 1856.3,
                "unit": "ng/μL"
            }
        }

        for model, expected_response in model_responses.items():
            # In real implementation, different images would trigger different responses
            result = mock_extractor.extract_nanodrop_data(sample_image_bytes)
            assert "concentration" in result