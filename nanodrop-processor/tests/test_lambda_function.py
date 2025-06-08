"""
Real integration tests for nanodrop lambda function.
Tests actual LLM extraction against real images for numerical accuracy.
"""

import pytest
import json
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the path so we can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lambda_function import (
    extract_nanodrop_data, 
    merge_nanodrop_results, 
    generate_csv,
    assess_quality,
    extract_images_from_email
)
from tests.ground_truth_data import (
    LAMBDA_GROUND_TRUTH, 
    MULTI_IMAGE_SCENARIOS,
    validate_sample_data_exact_match,
    validate_sample_data_with_tolerance,
    validate_commentary_flexible,
    EXPECTED_CSV_FORMAT
)


class TestRealNanodropExtraction:
    """Test real LLM extraction against actual images."""
    
    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Ensure OpenAI API key is available for real testing."""
        if not os.environ.get('OPENAI_API_KEY'):
            pytest.skip("OPENAI_API_KEY not set - skipping real LLM tests")
    
    def load_image_bytes(self, image_name):
        """Load actual image bytes for testing."""
        image_path = project_root / "images" / image_name
        if not image_path.exists():
            pytest.skip(f"Image {image_name} not found at {image_path}")
        
        with open(image_path, 'rb') as f:
            return f.read()
    
    @pytest.mark.parametrize("image_name", list(LAMBDA_GROUND_TRUTH.keys()))
    def test_real_extraction_numerical_accuracy(self, image_name):
        """Test real LLM extraction against actual images for numerical accuracy."""
            
        ground_truth = LAMBDA_GROUND_TRUTH[image_name]["expected_output"]
        image_bytes = self.load_image_bytes(image_name)
        
        # Real LLM extraction
        result = extract_nanodrop_data(image_bytes)
        
        print(f"\n=== Testing {image_name} ===")
        print(f"Expected samples: {len(ground_truth['samples'])}")
        print(f"Extracted samples: {len(result.get('samples', []))}")
        print(f"Expected assay: {ground_truth['assay_type']}")
        print(f"Extracted assay: {result.get('assay_type')}")
        print(f"Commentary: {result.get('commentary', 'None')[:100]}...")
        
        # Validate structure
        assert "assay_type" in result
        assert "commentary" in result  
        assert "samples" in result
        assert isinstance(result["samples"], list)
        
        # Validate sample count
        expected_count = len(ground_truth["samples"])
        actual_count = len(result["samples"])
        assert actual_count == expected_count, f"Sample count mismatch: expected {expected_count}, got {actual_count}"
        
        # Validate numerical accuracy (with some tolerance for LLM precision)
        tolerance = 0.05  # 5% tolerance for concentration, 0.05 for ratios
        is_match, message = validate_sample_data_with_tolerance(
            result["samples"], 
            ground_truth["samples"],
            tolerance
        )
        
        if not is_match:
            print(f"\nDetailed comparison for {image_name}:")
            print(f"Expected: {ground_truth['samples']}")
            print(f"Actual: {result['samples']}")
        
        assert is_match, f"Numerical accuracy failed for {image_name}: {message}"
        
        # Validate commentary exists and is reasonable
        is_valid, message = validate_commentary_flexible(result.get("commentary"))
        assert is_valid, f"Commentary validation failed for {image_name}: {message}"


class TestMultiImageProcessing:
    """Test multi-image processing and merging functionality."""
    
    def test_merge_single_image(self):
        """Test that single image merge returns the original result."""
        single_result = {
            "assay_type": "DNA",
            "commentary": "Single image test",
            "samples": [{"sample_number": 1, "concentration": 50.0, "a260_a280": 1.85, "a260_a230": 2.0}]
        }
        
        merged = merge_nanodrop_results([single_result])
        assert merged == single_result


class TestCSVGeneration:
    """Test CSV output generation."""
    
    def test_csv_format_structure(self):
        """Test that CSV has the correct headers and format."""
        test_data = {
            "assay_type": "RNA",
            "commentary": "Test data",
            "samples": [
                {"sample_number": 1, "concentration": 87.3, "a260_a280": 1.94, "a260_a230": 2.07},
                {"sample_number": 5, "concentration": -2.1, "a260_a280": 2.85, "a260_a230": -2.55}
            ]
        }
        
        csv_content = generate_csv(test_data)
        lines = csv_content.strip().split('\n')
        
        # Check header
        expected_headers = EXPECTED_CSV_FORMAT["headers"]
        actual_headers = [h.strip() for h in lines[0].split(',')]
        assert actual_headers == expected_headers
        
        # Check data rows
        assert len(lines) == 3  # Header + 2 data rows
        
        # Check first data row
        row1 = [cell.strip() for cell in lines[1].split(',')]
        assert row1[0] == "1"  # Sample number
        assert row1[1] == "87.3"  # Concentration
        assert row1[5] == "RNA"  # Assay type
        
        # Check negative value handling
        row2 = [cell.strip() for cell in lines[2].split(',')]
        assert row2[0] == "5"
        assert row2[1] == "-2.1"
        assert "Invalid negative" in row2[4]  # Quality assessment should flag this
    
    @pytest.mark.parametrize("image_name", ["IMG_3163.jpg", "IMG_3180.jpg"])
    def test_csv_content_accuracy(self, image_name):
        """Test CSV content accuracy for specific images."""
        ground_truth = LAMBDA_GROUND_TRUTH[image_name]["expected_output"]
        csv_content = generate_csv(ground_truth)
        
        lines = csv_content.strip().split('\n')
        expected_rows = LAMBDA_GROUND_TRUTH[image_name]["expected_csv_rows"]
        
        # Should have header + expected number of data rows
        assert len(lines) == expected_rows + 1
        
        # Validate each data row has correct number of columns
        for i in range(1, len(lines)):
            row = lines[i].split(',')
            assert len(row) == len(EXPECTED_CSV_FORMAT["headers"])


class TestQualityAssessment:
    """Test quality assessment functionality."""
    
    def test_quality_assessment_good_samples(self):
        """Test quality assessment for good samples."""
        quality = assess_quality(1.85, 2.05, 50.0)
        assert quality == "Good quality"
    
    def test_quality_assessment_negative_concentration(self):
        """Test quality assessment for negative concentration."""
        quality = assess_quality(1.85, 2.05, -2.1)
        assert "Invalid negative concentration" in quality
    
    def test_quality_assessment_contamination(self):
        """Test quality assessment for contaminated samples."""
        # Protein contamination (low 260/280)
        quality = assess_quality(1.5, 2.0, 50.0)
        assert "protein contamination" in quality.lower()
        
        # Organic contamination (low 260/230)
        quality = assess_quality(1.85, 1.4, 50.0)
        assert "organic contamination" in quality.lower()
    
    def test_quality_assessment_multiple_issues(self):
        """Test quality assessment with multiple issues."""
        quality = assess_quality(1.4, 1.3, 3.0)
        issues = quality.lower()
        assert "protein contamination" in issues
        assert "organic contamination" in issues
        assert "very low concentration" in issues




if __name__ == "__main__":
    pytest.main([__file__, "-v"])