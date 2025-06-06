"""
Mock Nanodrop data samples for testing.
These represent various types of readings you might encounter.
"""

NANODROP_SAMPLES = {
    "high_quality_dna": {
        "sample_id": "DNA_HQ_001",
        "concentration": 1856.3,
        "unit": "ng/μL",
        "a260": 37.126,
        "a280": 19.912,
        "a230": 17.854,
        "ratio_260_280": 1.86,
        "ratio_260_230": 2.08,
        "sample_type": "dsDNA",
        "expected_quality": "high"
    },
    
    "low_quality_dna": {
        "sample_id": "DNA_LQ_002",
        "concentration": 523.7,
        "unit": "ng/μL",
        "a260": 10.474,
        "a280": 7.123,
        "a230": 8.956,
        "ratio_260_280": 1.47,
        "ratio_260_230": 1.17,
        "sample_type": "dsDNA",
        "expected_quality": "low"
    },
    
    "high_quality_rna": {
        "sample_id": "RNA_HQ_003",
        "concentration": 2341.8,
        "unit": "ng/μL",
        "a260": 58.545,
        "a280": 28.234,
        "a230": 26.789,
        "ratio_260_280": 2.07,
        "ratio_260_230": 2.19,
        "sample_type": "RNA",
        "expected_quality": "high"
    },
    
    "contaminated_sample": {
        "sample_id": "CONT_004",
        "concentration": 156.2,
        "unit": "ng/μL",
        "a260": 3.124,
        "a280": 2.456,
        "a230": 4.123,
        "ratio_260_280": 1.27,
        "ratio_260_230": 0.76,
        "sample_type": "dsDNA",
        "expected_quality": "contaminated"
    },
    
    "very_low_concentration": {
        "sample_id": "LOW_005",
        "concentration": 8.3,
        "unit": "ng/μL",
        "a260": 0.166,
        "a280": 0.089,
        "a230": 0.078,
        "ratio_260_280": 1.87,
        "ratio_260_230": 2.13,
        "sample_type": "dsDNA",
        "expected_quality": "low_concentration"
    },
    
    "protein_contamination": {
        "sample_id": "PROT_006",
        "concentration": 892.4,
        "unit": "ng/μL",
        "a260": 17.848,
        "a280": 12.123,
        "a230": 8.234,
        "ratio_260_280": 1.47,
        "ratio_260_230": 2.17,
        "sample_type": "dsDNA",
        "expected_quality": "protein_contaminated"
    },
    
    "phenol_contamination": {
        "sample_id": "PHEN_007",
        "concentration": 1234.5,
        "unit": "ng/μL",
        "a260": 24.690,
        "a280": 12.987,
        "a230": 18.234,
        "ratio_260_280": 1.90,
        "ratio_260_230": 1.35,
        "sample_type": "dsDNA",
        "expected_quality": "phenol_contaminated"
    },
    
    "blank_sample": {
        "sample_id": "BLANK",
        "concentration": 0.0,
        "unit": "ng/μL",
        "a260": 0.001,
        "a280": 0.001,
        "a230": 0.001,
        "ratio_260_280": 1.00,
        "ratio_260_230": 1.00,
        "sample_type": "blank",
        "expected_quality": "blank"
    }
}


def get_quality_interpretation(sample_data):
    """
    Interpret the quality of a sample based on its measurements.
    
    Quality criteria:
    - DNA: 260/280 ratio should be ~1.8, 260/230 should be 2.0-2.2
    - RNA: 260/280 ratio should be ~2.0, 260/230 should be 2.0-2.2
    - Low 260/280: protein contamination
    - Low 260/230: phenol/chaotropic salt contamination
    """
    ratio_260_280 = sample_data.get("ratio_260_280", 0)
    ratio_260_230 = sample_data.get("ratio_260_230", 0)
    concentration = sample_data.get("concentration", 0)
    sample_type = sample_data.get("sample_type", "unknown")
    
    quality_issues = []
    
    # Check concentration
    if concentration < 10:
        quality_issues.append("very_low_concentration")
    elif concentration < 50:
        quality_issues.append("low_concentration")
    
    # Check 260/280 ratio
    if sample_type == "dsDNA":
        if ratio_260_280 < 1.7:
            quality_issues.append("protein_contamination")
        elif ratio_260_280 > 2.0:
            quality_issues.append("rna_contamination")
    elif sample_type == "RNA":
        if ratio_260_280 < 1.9:
            quality_issues.append("protein_contamination")
        elif ratio_260_280 > 2.2:
            quality_issues.append("degraded_rna")
    
    # Check 260/230 ratio
    if ratio_260_230 < 1.8:
        quality_issues.append("phenol_or_salt_contamination")
    elif ratio_260_230 > 2.4:
        quality_issues.append("measurement_error")
    
    if not quality_issues:
        return "high_quality"
    elif len(quality_issues) == 1:
        return quality_issues[0]
    else:
        return "multiple_quality_issues"


# Screen layout templates for generating mock images
SCREEN_LAYOUTS = {
    "nanodrop_one": {
        "title_position": (50, 30),
        "concentration_position": (100, 150),
        "concentration_label": "Nucleic Acid",
        "a260_position": (50, 250),
        "a280_position": (200, 250),
        "a230_position": (350, 250),
        "ratio_260_280_position": (50, 350),
        "ratio_260_230_position": (250, 350),
        "graph_position": (450, 150),
        "graph_size": (300, 200)
    },
    
    "nanodrop_2000": {
        "title_position": (100, 50),
        "concentration_position": (150, 200),
        "concentration_label": "dsDNA",
        "a260_position": (100, 300),
        "a280_position": (250, 300),
        "a230_position": (400, 300),
        "ratio_260_280_position": (100, 400),
        "ratio_260_230_position": (300, 400),
        "graph_position": (500, 100),
        "graph_size": (400, 300)
    }
}