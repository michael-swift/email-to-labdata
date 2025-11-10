"""
Ground truth test data for nanodrop lambda function.
Expected exact matches for sample data, flexible matching for commentary.
"""

# Expected lambda function output format for each image
LAMBDA_GROUND_TRUTH = {
    "IMG_3163.jpg": {
        "expected_output": {
            "assay_type": "DNA",  # A260/A280 ratios ~1.8 suggest DNA
            "commentary": "5 DNA samples with good overall quality",  # Flexible - will vary
            "samples": [
                {"sample_number": 1, "concentration": 19.0, "a260_a280": 1.83, "a260_a230": 2.08},
                {"sample_number": 2, "concentration": 20.0, "a260_a280": 1.80, "a260_a230": 1.85},
                {"sample_number": 3, "concentration": 14.1, "a260_a280": 1.85, "a260_a230": 1.79},
                {"sample_number": 4, "concentration": 19.4, "a260_a280": 1.79, "a260_a230": 2.04},
                {"sample_number": 5, "concentration": 21.8, "a260_a280": 1.77, "a260_a230": 1.89},
            ]
        },
        "source_image": "IMG_3163.jpg",
        "expected_csv_rows": 5,
        "notes": "DNA samples, Load 6, all positive concentrations"
    },
    
    "IMG_3168.jpg": {
        "expected_output": {
            "assay_type": "DNA", # A260/A280 ratios ~1.9 suggest DNA
            "commentary": "5 DNA samples, samples 12-13 show contamination issues",  # Flexible
            "samples": [
                {"sample_number": 9, "concentration": 60.5, "a260_a280": 1.89, "a260_a230": 1.94},
                {"sample_number": 10, "concentration": 75.3, "a260_a280": 1.87, "a260_a230": 2.03},
                {"sample_number": 11, "concentration": 75.0, "a260_a280": 1.88, "a260_a230": 1.98},
                {"sample_number": 12, "concentration": 21.3, "a260_a280": 1.91, "a260_a230": 1.49},
                {"sample_number": 13, "concentration": 24.5, "a260_a280": 1.89, "a260_a230": 1.62},
            ]
        },
        "source_image": "IMG_3168.jpg", 
        "expected_csv_rows": 5,
        "notes": "DNA samples, Load 14, samples 12-13 have low 260/230 ratios indicating contamination"
    },
    
    "IMG_3169.jpg": {
        "expected_output": {
            "assay_type": "DNA", # A260/A280 ratios ~1.8 suggest DNA  
            "commentary": "5 DNA samples, samples 4-5 show contamination issues",  # Flexible
            "samples": [
                {"sample_number": 4, "concentration": 24.3, "a260_a280": 1.93, "a260_a230": 1.58},
                {"sample_number": 5, "concentration": 18.4, "a260_a280": 1.78, "a260_a230": 1.52},
                {"sample_number": 6, "concentration": 82.8, "a260_a280": 1.88, "a260_a230": 2.10},
                {"sample_number": 7, "concentration": 46.5, "a260_a280": 1.85, "a260_a230": 1.91},
                {"sample_number": 8, "concentration": 39.6, "a260_a280": 1.86, "a260_a230": 1.87},
            ]
        },
        "source_image": "IMG_3169.jpg",
        "expected_csv_rows": 5, 
        "notes": "DNA samples, Load 14, samples 4-5 have low 260/230 ratios"
    },
    
    "image.png": {
        "expected_output": {
            "assay_type": "DNA", # A260/A280 ratios ~1.9 suggest DNA
            "commentary": "2 DNA samples with unusually high 260/230 ratios",  # Flexible
            "samples": [
                {"sample_number": 1, "concentration": 46.3, "a260_a280": 1.90, "a260_a230": 2.64},
                {"sample_number": 2, "concentration": 37.4, "a260_a280": 1.88, "a260_a230": 2.33},
            ]
        },
        "source_image": "image.png",
        "expected_csv_rows": 2,
        "notes": "DNA samples, Load 3, high 260/230 ratios may indicate measurement issues"
    },
    
    # New test case from your uploaded CSV 
    "IMG_3180.jpg": {
        "expected_output": {
            "assay_type": "RNA", # A260/A280 ratios ~1.9-2.0 suggest RNA
            "commentary": "4 good RNA samples, sample 5 shows measurement error with negative values",  # Flexible
            "samples": [
                {"sample_number": 1, "concentration": 87.3, "a260_a280": 1.94, "a260_a230": 2.07},
                {"sample_number": 2, "concentration": 141.7, "a260_a280": 1.89, "a260_a230": 2.01},
                {"sample_number": 3, "concentration": 74.5, "a260_a280": 1.96, "a260_a230": 2.14},
                {"sample_number": 4, "concentration": 71.4, "a260_a280": 1.85, "a260_a230": 2.0},
                {"sample_number": 5, "concentration": -2.1, "a260_a280": 2.85, "a260_a230": -2.55},
            ]
        },
        "source_image": "IMG_3180.jpg",
        "expected_csv_rows": 5,
        "notes": "RNA samples, Load 6, sample 5 has negative concentration (measurement error)"
    }
}

# Multi-image test scenarios
MULTI_IMAGE_SCENARIOS = {
    "load_14_combined": {
        "input_images": ["IMG_3168.jpg", "IMG_3169.jpg"],
        "expected_output": {
            "assay_type": "DNA",
            "commentary": "Processed 2 images with 10 DNA samples total",  # Flexible
            "samples": [
                # From IMG_3169.jpg (samples 4-8)
                {"sample_number": 4, "concentration": 24.3, "a260_a280": 1.93, "a260_a230": 1.58},
                {"sample_number": 5, "concentration": 18.4, "a260_a280": 1.78, "a260_a230": 1.52},
                {"sample_number": 6, "concentration": 82.8, "a260_a280": 1.88, "a260_a230": 2.10},
                {"sample_number": 7, "concentration": 46.5, "a260_a280": 1.85, "a260_a230": 1.91},
                {"sample_number": 8, "concentration": 39.6, "a260_a280": 1.86, "a260_a230": 1.87},
                # From IMG_3168.jpg (samples 9-13)  
                {"sample_number": 9, "concentration": 60.5, "a260_a280": 1.89, "a260_a230": 1.94},
                {"sample_number": 10, "concentration": 75.3, "a260_a280": 1.87, "a260_a230": 2.03},
                {"sample_number": 11, "concentration": 75.0, "a260_a280": 1.88, "a260_a230": 1.98},
                {"sample_number": 12, "concentration": 21.3, "a260_a280": 1.91, "a260_a230": 1.49},
                {"sample_number": 13, "concentration": 24.5, "a260_a280": 1.89, "a260_a230": 1.62},
            ]
        },
        "expected_csv_rows": 10,
        "notes": "Combined Load 14 data, should be sorted by sample number"
    }
}

# Expected CSV format for each image
EXPECTED_CSV_FORMAT = {
    "headers": ['Sample Number', 'Concentration (ng/uL)', 'A260/A280', 'A260/A230', 'Quality Assessment', 'Assay Type'],
    "sample_row_example": [1, 87.3, 1.94, 2.07, 'Good quality', 'RNA']
}

# Email output expectations
EXPECTED_EMAIL_FORMAT = {
    "subject_pattern": r"Nanodrop Results - (RNA|DNA|Mixed) Analysis \(\d+ samples, \d+ images?\)",
    "body_contains": [
        "Assay Type:",
        "Images Processed:",
        "Samples Extracted:", 
        "ANALYSIS SUMMARY:",
        "SAMPLE RESULTS:",
        "Nanodrop Processing Service"
    ],
    "attachments": {
        "csv_filename_pattern": r"nanodrop_(RNA|DNA|Mixed)_\d+_samples\.csv",
        "image_filenames": ["nanodrop_image_1.jpg", "nanodrop_image_2.jpg"]  # For multi-image
    }
}

def validate_sample_data_exact_match(actual_samples, expected_samples):
    """
    Validate that sample data matches exactly (for numeric precision testing).
    """
    if len(actual_samples) != len(expected_samples):
        return False, f"Sample count mismatch: {len(actual_samples)} vs {len(expected_samples)}"
    
    # Sort both by sample_number for comparison
    actual_sorted = sorted(actual_samples, key=lambda x: x['sample_number'])
    expected_sorted = sorted(expected_samples, key=lambda x: x['sample_number'])
    
    for actual, expected in zip(actual_sorted, expected_sorted):
        for field in ['sample_number', 'concentration', 'a260_a280', 'a260_a230']:
            if actual[field] != expected[field]:
                return False, f"Sample {actual['sample_number']} field '{field}': {actual[field]} != {expected[field]}"
    
    return True, "All samples match exactly"


def validate_sample_data_with_tolerance(actual_samples, expected_samples, tolerance=0.05):
    """
    Validate sample data with tolerance for LLM precision variations.
    """
    if len(actual_samples) != len(expected_samples):
        return False, f"Sample count mismatch: {len(actual_samples)} vs {len(expected_samples)}"
    
    # Sort both by sample_number for comparison
    actual_sorted = sorted(actual_samples, key=lambda x: x['sample_number'])
    expected_sorted = sorted(expected_samples, key=lambda x: x['sample_number'])
    
    for actual, expected in zip(actual_sorted, expected_sorted):
        # Sample number must match exactly
        if actual['sample_number'] != expected['sample_number']:
            return False, f"Sample number mismatch: {actual['sample_number']} != {expected['sample_number']}"
        
        # Check numeric fields with tolerance
        for field in ['concentration', 'a260_a280', 'a260_a230']:
            actual_val = actual[field]
            expected_val = expected[field]
            
            # For negative values, allow exact match or reasonable tolerance
            if expected_val < 0:
                diff = abs(actual_val - expected_val)
                if diff > abs(expected_val * 0.1):  # 10% tolerance for negative values
                    return False, f"Sample {actual['sample_number']} field '{field}': {actual_val} != {expected_val} (tolerance exceeded)"
            else:
                # Positive values: use percentage tolerance
                diff = abs(actual_val - expected_val)
                max_diff = max(abs(expected_val * tolerance), tolerance)  # At least absolute tolerance
                if diff > max_diff:
                    return False, f"Sample {actual['sample_number']} field '{field}': {actual_val} != {expected_val} (diff: {diff}, max: {max_diff})"
    
    return True, "All samples match within tolerance"

def validate_commentary_flexible(actual_commentary):
    """
    Flexible validation for commentary - check for key concepts rather than exact match.
    """
    if not actual_commentary:
        return False, "No commentary provided"
    
    # Basic checks - should be a reasonable length string
    if len(actual_commentary.strip()) < 10:
        return False, f"Commentary too short: '{actual_commentary}'"
    
    return True, "Commentary present and reasonable"
