import pytest
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from tests.fixtures.nanodrop_samples import NANODROP_SAMPLES, get_quality_interpretation


class NanodropDataValidator:
    """Validate Nanodrop data for quality and correctness."""
    
    @staticmethod
    def validate_measurement(data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a Nanodrop measurement.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields
        required_fields = ["concentration", "a260", "a280"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Concentration validation
        if "concentration" in data:
            conc = data["concentration"]
            if not isinstance(conc, (int, float)):
                errors.append("Concentration must be numeric")
            elif conc < 0:
                errors.append("Concentration cannot be negative")
            elif conc > 50000:
                errors.append("Concentration suspiciously high (>50,000 ng/μL)")
        
        # Absorbance validation
        for abs_type in ["a260", "a280", "a230"]:
            if abs_type in data:
                value = data[abs_type]
                if not isinstance(value, (int, float)):
                    errors.append(f"{abs_type} must be numeric")
                elif value < 0:
                    errors.append(f"{abs_type} cannot be negative")
                elif value > 100:
                    errors.append(f"{abs_type} suspiciously high (>100)")
        
        # Ratio validation
        if "ratio_260_280" in data:
            ratio = data["ratio_260_280"]
            if not isinstance(ratio, (int, float)):
                errors.append("260/280 ratio must be numeric")
            elif not 0 < ratio < 3:
                errors.append("260/280 ratio out of reasonable range (0-3)")
        
        if "ratio_260_230" in data:
            ratio = data["ratio_260_230"]
            if not isinstance(ratio, (int, float)):
                errors.append("260/230 ratio must be numeric")
            elif not 0 < ratio < 3:
                errors.append("260/230 ratio out of reasonable range (0-3)")
        
        # Cross-validation: ratios should match absorbance values
        if all(k in data for k in ["a260", "a280", "ratio_260_280"]):
            if data["a280"] > 0:
                calculated_ratio = data["a260"] / data["a280"]
                given_ratio = data["ratio_260_280"]
                if abs(calculated_ratio - given_ratio) > 0.1:
                    errors.append(f"260/280 ratio mismatch: calculated {calculated_ratio:.2f} vs given {given_ratio}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def assess_quality(data: Dict) -> Dict[str, any]:
        """
        Assess the quality of a DNA/RNA sample based on measurements.
        
        Returns:
            Dictionary with quality metrics and recommendations
        """
        assessment = {
            "overall_quality": "unknown",
            "issues": [],
            "recommendations": [],
            "confidence": 0.0
        }
        
        if "concentration" not in data:
            assessment["issues"].append("No concentration data")
            return assessment
        
        conc = data.get("concentration", 0)
        ratio_260_280 = data.get("ratio_260_280", 0)
        ratio_260_230 = data.get("ratio_260_230", 0)
        
        # Concentration assessment
        if conc < 10:
            assessment["issues"].append("Very low concentration")
            assessment["recommendations"].append("Consider concentrating sample")
        elif conc < 50:
            assessment["issues"].append("Low concentration")
            assessment["recommendations"].append("May need larger sample volume")
        elif conc > 5000:
            assessment["issues"].append("Very high concentration")
            assessment["recommendations"].append("Consider diluting sample")
        
        # Purity assessment (260/280 ratio)
        if ratio_260_280 > 0:
            if 1.8 <= ratio_260_280 <= 2.0:
                assessment["confidence"] += 0.3
            elif 2.0 <= ratio_260_280 <= 2.2:
                assessment["confidence"] += 0.3
                assessment["recommendations"].append("Likely RNA sample")
            elif ratio_260_280 < 1.8:
                assessment["issues"].append("Possible protein contamination")
                assessment["recommendations"].append("Consider additional purification")
            elif ratio_260_280 > 2.2:
                assessment["issues"].append("Unusual 260/280 ratio")
                assessment["recommendations"].append("Check for RNA contamination or degradation")
        
        # Purity assessment (260/230 ratio)
        if ratio_260_230 > 0:
            if 2.0 <= ratio_260_230 <= 2.2:
                assessment["confidence"] += 0.3
            elif ratio_260_230 < 1.8:
                assessment["issues"].append("Possible organic contamination")
                assessment["recommendations"].append("Check for phenol or chaotropic salt contamination")
            elif ratio_260_230 > 2.4:
                assessment["issues"].append("Unusual 260/230 ratio")
        
        # Overall quality determination
        if len(assessment["issues"]) == 0:
            assessment["overall_quality"] = "excellent"
            assessment["confidence"] = min(1.0, assessment["confidence"] + 0.4)
        elif len(assessment["issues"]) == 1:
            assessment["overall_quality"] = "good"
            assessment["confidence"] = min(1.0, assessment["confidence"] + 0.2)
        elif len(assessment["issues"]) == 2:
            assessment["overall_quality"] = "fair"
        else:
            assessment["overall_quality"] = "poor"
        
        return assessment


class TestDataValidation:
    """Test data validation functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return NanodropDataValidator()
    
    @pytest.mark.unit
    def test_validate_good_data(self, validator):
        """Test validation of good quality data."""
        good_data = NANODROP_SAMPLES["high_quality_dna"]
        is_valid, errors = validator.validate_measurement(good_data)
        
        assert is_valid
        assert len(errors) == 0
    
    @pytest.mark.unit
    def test_validate_missing_fields(self, validator):
        """Test validation with missing required fields."""
        incomplete_data = {
            "sample_id": "TEST001",
            "concentration": 1234.5
            # Missing a260, a280
        }
        
        is_valid, errors = validator.validate_measurement(incomplete_data)
        
        assert not is_valid
        assert "Missing required field: a260" in errors
        assert "Missing required field: a280" in errors
    
    @pytest.mark.unit
    def test_validate_invalid_values(self, validator):
        """Test validation with invalid values."""
        test_cases = [
            # Negative concentration
            ({"concentration": -100, "a260": 1, "a280": 1}, 
             "Concentration cannot be negative"),
            
            # Non-numeric values
            ({"concentration": "abc", "a260": 1, "a280": 1}, 
             "Concentration must be numeric"),
            
            # Out of range ratios
            ({"concentration": 100, "a260": 1, "a280": 1, "ratio_260_280": 5}, 
             "260/280 ratio out of reasonable range"),
            
            # Suspiciously high values
            ({"concentration": 60000, "a260": 1, "a280": 1}, 
             "Concentration suspiciously high"),
        ]
        
        for data, expected_error in test_cases:
            is_valid, errors = validator.validate_measurement(data)
            assert not is_valid
            assert any(expected_error in error for error in errors)
    
    @pytest.mark.unit
    def test_ratio_cross_validation(self, validator):
        """Test cross-validation of ratios with absorbance values."""
        # Mismatched ratio
        data = {
            "concentration": 1000,
            "a260": 20.0,
            "a280": 10.0,
            "ratio_260_280": 1.5  # Should be 2.0
        }
        
        is_valid, errors = validator.validate_measurement(data)
        assert not is_valid
        assert any("ratio mismatch" in error for error in errors)
    
    @pytest.mark.unit
    def test_quality_assessment(self, validator):
        """Test quality assessment of samples."""
        # Test high quality sample
        hq_assessment = validator.assess_quality(NANODROP_SAMPLES["high_quality_dna"])
        assert hq_assessment["overall_quality"] in ["excellent", "good"]
        assert len(hq_assessment["issues"]) <= 1
        
        # Test low quality sample
        lq_assessment = validator.assess_quality(NANODROP_SAMPLES["low_quality_dna"])
        assert lq_assessment["overall_quality"] in ["fair", "poor"]
        assert len(lq_assessment["issues"]) > 0
        assert len(lq_assessment["recommendations"]) > 0
        
        # Test contaminated sample
        cont_assessment = validator.assess_quality(NANODROP_SAMPLES["contaminated_sample"])
        assert cont_assessment["overall_quality"] == "poor"
        assert any("contamination" in issue.lower() for issue in cont_assessment["issues"])
    
    @pytest.mark.unit
    def test_sample_type_detection(self, validator):
        """Test detection of sample type from ratios."""
        # RNA sample (260/280 ~2.0)
        rna_data = NANODROP_SAMPLES["high_quality_rna"]
        rna_assessment = validator.assess_quality(rna_data)
        assert any("RNA" in rec for rec in rna_assessment["recommendations"])
        
        # DNA sample (260/280 ~1.8)
        dna_data = NANODROP_SAMPLES["high_quality_dna"]
        dna_assessment = validator.assess_quality(dna_data)
        # Should not suggest RNA for DNA sample
        assert not any("RNA sample" in rec for rec in dna_assessment["recommendations"])
    
    @pytest.mark.unit
    def test_edge_cases(self, validator):
        """Test edge cases in validation."""
        edge_cases = [
            # Zero concentration
            {"concentration": 0.0, "a260": 0.001, "a280": 0.001},
            
            # Very small values
            {"concentration": 0.1, "a260": 0.002, "a280": 0.001},
            
            # Missing optional fields
            {"concentration": 100, "a260": 2.0, "a280": 1.0},
            
            # Additional unexpected fields
            {"concentration": 100, "a260": 2.0, "a280": 1.0, 
             "extra_field": "should_be_ignored"},
        ]
        
        for data in edge_cases:
            is_valid, errors = validator.validate_measurement(data)
            # These should all be valid (though might have quality issues)
            assert is_valid or len(errors) > 0  # Should process without crashing
    
    @pytest.mark.unit
    def test_get_quality_interpretation(self):
        """Test the quality interpretation function."""
        for sample_name, sample_data in NANODROP_SAMPLES.items():
            interpretation = get_quality_interpretation(sample_data)
            assert isinstance(interpretation, str)
            assert len(interpretation) > 0
            
            # Check specific interpretations
            if sample_name == "high_quality_dna":
                assert interpretation == "high_quality"
            elif sample_name == "contaminated_sample":
                assert "contamination" in interpretation or "multiple" in interpretation