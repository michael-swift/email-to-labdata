#!/usr/bin/env python3
"""
Validate the accuracy of Nanodrop data extraction.
This script checks the extracted data against expected patterns and validates quality assessments.
"""

import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple


def load_csv_data(csv_path: str) -> List[Dict]:
    """Load data from CSV file."""
    data = []
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Convert numeric fields
            row['concentration_ng_ul'] = float(row['concentration_ng_ul'])
            row['a260_a280'] = float(row['a260_a280'])
            row['a260_a230'] = float(row['a260_a230'])
            data.append(row)
    return data


def validate_data_ranges(data: List[Dict]) -> Tuple[bool, List[str]]:
    """Validate that all values are within reasonable ranges."""
    issues = []
    
    for i, row in enumerate(data, 1):
        # Check concentration range
        conc = row['concentration_ng_ul']
        if conc < 0 or conc > 10000:
            issues.append(f"Row {i}: Concentration {conc} outside normal range (0-10000)")
        
        # Check A260/A280 ratio
        ratio_280 = row['a260_a280']
        if ratio_280 < 1.0 or ratio_280 > 3.0:
            issues.append(f"Row {i}: A260/A280 ratio {ratio_280} outside normal range (1.0-3.0)")
        
        # Check A260/A230 ratio
        ratio_230 = row['a260_a230']
        if ratio_230 < 0.5 or ratio_230 > 4.0:
            issues.append(f"Row {i}: A260/A230 ratio {ratio_230} outside normal range (0.5-4.0)")
    
    return len(issues) == 0, issues


def validate_quality_assessments(data: List[Dict]) -> Tuple[bool, List[str]]:
    """Validate that quality assessments match the ratios."""
    issues = []
    
    for i, row in enumerate(data, 1):
        ratio_280 = row['a260_a280']
        ratio_230 = row['a260_a230']
        quality = row['quality_assessment']
        
        # Check if quality assessment is consistent with ratios
        expected_issues = []
        
        if ratio_280 < 1.8:
            expected_issues.append("protein contamination")
        if ratio_280 > 2.2:
            expected_issues.append("RNA or degraded")
        if ratio_230 < 1.8:
            expected_issues.append("organic contamination")
        if ratio_230 > 2.4:
            expected_issues.append("high 260/230")
        
        if not expected_issues and quality != "Good quality":
            issues.append(f"Row {i}: Should be 'Good quality' but got '{quality}'")
        elif expected_issues and "Good quality" in quality:
            issues.append(f"Row {i}: Should have quality issues but marked as 'Good quality'")
    
    return len(issues) == 0, issues


def check_data_completeness(data: List[Dict]) -> Tuple[bool, List[str]]:
    """Check that all required fields are present."""
    required_fields = ['load_number', 'sample_number', 'concentration_ng_ul', 
                      'a260_a280', 'a260_a230', 'quality_assessment']
    
    issues = []
    
    for i, row in enumerate(data, 1):
        for field in required_fields:
            if field not in row or row[field] == '' or row[field] is None:
                issues.append(f"Row {i}: Missing or empty field '{field}'")
    
    return len(issues) == 0, issues


def analyze_sample_distribution(data: List[Dict]) -> Dict:
    """Analyze the distribution of samples across loads."""
    loads = {}
    quality_counts = {"Good quality": 0, "With issues": 0}
    
    for row in data:
        load_num = row['load_number']
        if load_num not in loads:
            loads[load_num] = []
        loads[load_num].append(row)
        
        if row['quality_assessment'] == "Good quality":
            quality_counts["Good quality"] += 1
        else:
            quality_counts["With issues"] += 1
    
    return {
        "loads": loads,
        "quality_distribution": quality_counts,
        "total_samples": len(data)
    }


def generate_validation_report(csv_path: str) -> Dict:
    """Generate a comprehensive validation report."""
    data = load_csv_data(csv_path)
    
    # Run all validations
    ranges_valid, range_issues = validate_data_ranges(data)
    quality_valid, quality_issues = validate_quality_assessments(data)
    complete_valid, completeness_issues = check_data_completeness(data)
    
    # Analyze distribution
    distribution = analyze_sample_distribution(data)
    
    report = {
        "file": csv_path,
        "total_samples": len(data),
        "validations": {
            "data_ranges": {"valid": ranges_valid, "issues": range_issues},
            "quality_assessments": {"valid": quality_valid, "issues": quality_issues},
            "data_completeness": {"valid": complete_valid, "issues": completeness_issues}
        },
        "distribution": distribution,
        "overall_valid": ranges_valid and quality_valid and complete_valid
    }
    
    return report


def print_validation_report(report: Dict):
    """Print a formatted validation report."""
    print(f"\n=== Validation Report: {Path(report['file']).name} ===")
    print(f"Total samples: {report['total_samples']}")
    
    # Print validation results
    validations = report['validations']
    print(f"\nValidation Results:")
    print(f"  Data ranges: {'✓' if validations['data_ranges']['valid'] else '✗'}")
    print(f"  Quality assessments: {'✓' if validations['quality_assessments']['valid'] else '✗'}")
    print(f"  Data completeness: {'✓' if validations['data_completeness']['valid'] else '✗'}")
    
    # Print issues if any
    all_issues = []
    for validation in validations.values():
        all_issues.extend(validation['issues'])
    
    if all_issues:
        print(f"\nIssues found:")
        for issue in all_issues[:10]:  # Show first 10 issues
            print(f"  - {issue}")
        if len(all_issues) > 10:
            print(f"  ... and {len(all_issues) - 10} more issues")
    
    # Print distribution
    dist = report['distribution']
    print(f"\nLoad distribution:")
    for load_num, samples in dist['loads'].items():
        print(f"  Load {load_num}: {len(samples)} samples")
    
    print(f"\nQuality distribution:")
    for quality, count in dist['quality_distribution'].items():
        percentage = (count / dist['total_samples']) * 100
        print(f"  {quality}: {count} samples ({percentage:.1f}%)")
    
    print(f"\nOverall: {'✓ VALID' if report['overall_valid'] else '✗ INVALID'}")


def cross_validate_images() -> List[str]:
    """Cross-validate data between multiple images of the same load."""
    issues = []
    
    # Load data from images that show the same load (14)
    img_3168_path = "extracted_data/IMG_3168_extracted.csv"
    img_3169_path = "extracted_data/IMG_3169_extracted.csv"
    
    if os.path.exists(img_3168_path) and os.path.exists(img_3169_path):
        data_3168 = load_csv_data(img_3168_path)
        data_3169 = load_csv_data(img_3169_path)
        
        # Check if both are from load 14
        load_14_3168 = [row for row in data_3168 if row['load_number'] == '14']
        load_14_3169 = [row for row in data_3169 if row['load_number'] == '14']
        
        if load_14_3168 and load_14_3169:
            # Find overlapping samples
            samples_3168 = {int(row['sample_number']): row for row in load_14_3168}
            samples_3169 = {int(row['sample_number']): row for row in load_14_3169}
            
            common_samples = set(samples_3168.keys()) & set(samples_3169.keys())
            
            if common_samples:
                print(f"\nCross-validation between IMG_3168 and IMG_3169:")
                print(f"Found {len(common_samples)} overlapping samples: {sorted(common_samples)}")
                
                for sample_num in common_samples:
                    row1 = samples_3168[sample_num]
                    row2 = samples_3169[sample_num]
                    
                    # Compare values (should be identical or very close)
                    if abs(row1['concentration_ng_ul'] - row2['concentration_ng_ul']) > 0.1:
                        issues.append(f"Sample {sample_num}: Concentration mismatch ({row1['concentration_ng_ul']} vs {row2['concentration_ng_ul']})")
                    
                    if abs(row1['a260_a280'] - row2['a260_a280']) > 0.01:
                        issues.append(f"Sample {sample_num}: A260/A280 mismatch ({row1['a260_a280']} vs {row2['a260_a280']})")
    
    return issues


if __name__ == "__main__":
    # Validate all CSV files
    csv_files = [
        "extracted_data/IMG_3163_extracted.csv",
        "extracted_data/IMG_3168_extracted.csv", 
        "extracted_data/IMG_3169_extracted.csv",
        "extracted_data/image_extracted.csv",
        "extracted_data/all_samples_combined.csv"
    ]
    
    all_valid = True
    
    for csv_file in csv_files:
        if os.path.exists(csv_file):
            report = generate_validation_report(csv_file)
            print_validation_report(report)
            if not report['overall_valid']:
                all_valid = False
        else:
            print(f"File not found: {csv_file}")
            all_valid = False
    
    # Cross-validate images
    cross_issues = cross_validate_images()
    if cross_issues:
        print(f"\nCross-validation issues:")
        for issue in cross_issues:
            print(f"  - {issue}")
        all_valid = False
    else:
        print(f"\n✓ Cross-validation passed")
    
    print(f"\n{'='*50}")
    print(f"FINAL RESULT: {'✓ ALL VALIDATIONS PASSED' if all_valid else '✗ VALIDATION FAILURES FOUND'}")
    print(f"{'='*50}")
    
    if all_valid:
        print("\n🎉 Extraction system is working correctly!")
        print("Ready for production use with real LLM integration.")
    else:
        print("\n⚠️  Please review and fix the issues above.")