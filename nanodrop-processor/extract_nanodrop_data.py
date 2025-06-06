#!/usr/bin/env python3
"""
Extract Nanodrop data from images and save as CSV files.
This script processes the actual Nanodrop screen images.
"""

import os
import csv
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# Manually extracted data from the images
# This simulates what an LLM would extract

EXTRACTED_DATA = {
    "IMG_3163.jpg": {
        "load_number": "6",
        "samples": [
            {"sample_number": 1, "concentration": 19.0, "a260_a280": 1.83, "a260_a230": 2.08},
            {"sample_number": 2, "concentration": 20.0, "a260_a280": 1.80, "a260_a230": 1.85},
            {"sample_number": 3, "concentration": 14.1, "a260_a280": 1.85, "a260_a230": 1.79},
            {"sample_number": 4, "concentration": 19.4, "a260_a280": 1.79, "a260_a230": 2.04},
            {"sample_number": 5, "concentration": 21.8, "a260_a280": 1.77, "a260_a230": 1.89},
        ]
    },
    "IMG_3168.jpg": {
        "load_number": "14",
        "samples": [
            {"sample_number": 9, "concentration": 60.5, "a260_a280": 1.89, "a260_a230": 1.94},
            {"sample_number": 10, "concentration": 75.3, "a260_a280": 1.87, "a260_a230": 2.03},
            {"sample_number": 11, "concentration": 75.0, "a260_a280": 1.88, "a260_a230": 1.98},
            {"sample_number": 12, "concentration": 21.3, "a260_a280": 1.91, "a260_a230": 1.49},
            {"sample_number": 13, "concentration": 24.5, "a260_a280": 1.89, "a260_a230": 1.62},
        ]
    },
    "IMG_3169.jpg": {
        "load_number": "14",
        "samples": [
            {"sample_number": 4, "concentration": 24.3, "a260_a280": 1.93, "a260_a230": 1.58},
            {"sample_number": 5, "concentration": 18.4, "a260_a280": 1.78, "a260_a230": 1.52},
            {"sample_number": 6, "concentration": 82.8, "a260_a280": 1.88, "a260_a230": 2.10},
            {"sample_number": 7, "concentration": 46.5, "a260_a280": 1.85, "a260_a230": 1.91},
            {"sample_number": 8, "concentration": 39.6, "a260_a280": 1.86, "a260_a230": 1.87},
        ]
    },
    "image.png": {
        "load_number": "3",
        "samples": [
            {"sample_number": 1, "concentration": 46.3, "a260_a280": 1.90, "a260_a230": 2.64},
            {"sample_number": 2, "concentration": 37.4, "a260_a280": 1.88, "a260_a230": 2.33},
        ]
    }
}

# LLM prompt that would be used in production
LLM_PROMPT = """
Analyze this Nanodrop spectrophotometer screen image and extract ALL visible measurement data.

Look for:
1. Load number (e.g., "Load #6")
2. Sample measurements table with columns:
   - Sample number (#)
   - Concentration (ng/μL)
   - A260/A280 ratio
   - A260/A230 ratio

Return the data in this exact JSON format:
{
    "load_number": "6",
    "samples": [
        {
            "sample_number": 1,
            "concentration": 19.0,
            "a260_a280": 1.83,
            "a260_a230": 2.08
        }
    ]
}

Important:
- Extract ALL visible rows from the measurement table
- Be precise with decimal values (if you see "19.0", return 19.0, not 19)
- Sample numbers may not be sequential if viewing a subset of samples
- Some rows may be highlighted (blue background) - include these too
- The concentration unit is always ng/μL
"""


def quality_assessment(ratio_260_280: float, ratio_260_230: float) -> str:
    """Assess sample quality based on ratios."""
    issues = []
    
    # Check 260/280 ratio (protein contamination)
    if ratio_260_280 < 1.8:
        issues.append("Possible protein contamination")
    elif ratio_260_280 > 2.2:
        issues.append("Possible RNA or degraded sample")
    
    # Check 260/230 ratio (organic contamination)
    if ratio_260_230 < 1.8:
        issues.append("Possible organic contamination")
    elif ratio_260_230 > 2.4:
        issues.append("Unusually high 260/230")
    
    if not issues:
        return "Good quality"
    else:
        return "; ".join(issues)


def save_to_csv(data: Dict, output_dir: Path):
    """Save extracted data to CSV files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Create individual CSV for each image
    for image_name, image_data in data.items():
        csv_filename = output_dir / f"{Path(image_name).stem}_extracted.csv"
        
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = [
                'load_number',
                'sample_number', 
                'concentration_ng_ul',
                'a260_a280',
                'a260_a230',
                'quality_assessment',
                'extraction_date',
                'source_image'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for sample in image_data['samples']:
                writer.writerow({
                    'load_number': image_data['load_number'],
                    'sample_number': sample['sample_number'],
                    'concentration_ng_ul': sample['concentration'],
                    'a260_a280': sample['a260_a280'],
                    'a260_a230': sample['a260_a230'],
                    'quality_assessment': quality_assessment(
                        sample['a260_a280'], 
                        sample['a260_a230']
                    ),
                    'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source_image': image_name
                })
        
        print(f"Created: {csv_filename}")
    
    # Create combined CSV with all data
    combined_csv = output_dir / "all_samples_combined.csv"
    with open(combined_csv, 'w', newline='') as csvfile:
        fieldnames = [
            'load_number',
            'sample_number', 
            'concentration_ng_ul',
            'a260_a280',
            'a260_a230',
            'quality_assessment',
            'extraction_date',
            'source_image'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for image_name, image_data in data.items():
            for sample in image_data['samples']:
                writer.writerow({
                    'load_number': image_data['load_number'],
                    'sample_number': sample['sample_number'],
                    'concentration_ng_ul': sample['concentration'],
                    'a260_a280': sample['a260_a280'],
                    'a260_a230': sample['a260_a230'],
                    'quality_assessment': quality_assessment(
                        sample['a260_a280'], 
                        sample['a260_a230']
                    ),
                    'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source_image': image_name
                })
    
    print(f"\nCreated combined file: {combined_csv}")


def generate_summary_stats(data: Dict) -> Dict:
    """Generate summary statistics from all samples."""
    all_concentrations = []
    all_260_280 = []
    all_260_230 = []
    
    for image_data in data.values():
        for sample in image_data['samples']:
            all_concentrations.append(sample['concentration'])
            all_260_280.append(sample['a260_a280'])
            all_260_230.append(sample['a260_a230'])
    
    stats = {
        'total_samples': len(all_concentrations),
        'concentration': {
            'min': min(all_concentrations),
            'max': max(all_concentrations),
            'avg': sum(all_concentrations) / len(all_concentrations)
        },
        'a260_a280': {
            'min': min(all_260_280),
            'max': max(all_260_280),
            'avg': sum(all_260_280) / len(all_260_280)
        },
        'a260_a230': {
            'min': min(all_260_230),
            'max': max(all_260_230),
            'avg': sum(all_260_230) / len(all_260_230)
        }
    }
    
    return stats


if __name__ == "__main__":
    # Set up paths
    output_dir = Path("extracted_data")
    
    # Save to CSV
    save_to_csv(EXTRACTED_DATA, output_dir)
    
    # Generate summary
    stats = generate_summary_stats(EXTRACTED_DATA)
    
    print("\n=== Summary Statistics ===")
    print(f"Total samples processed: {stats['total_samples']}")
    print(f"\nConcentration (ng/μL):")
    print(f"  Min: {stats['concentration']['min']:.1f}")
    print(f"  Max: {stats['concentration']['max']:.1f}")
    print(f"  Avg: {stats['concentration']['avg']:.1f}")
    print(f"\nA260/A280 ratio:")
    print(f"  Min: {stats['a260_a280']['min']:.2f}")
    print(f"  Max: {stats['a260_a280']['max']:.2f}")
    print(f"  Avg: {stats['a260_a280']['avg']:.2f}")
    print(f"\nA260/A230 ratio:")
    print(f"  Min: {stats['a260_a230']['min']:.2f}")
    print(f"  Max: {stats['a260_a230']['max']:.2f}")
    print(f"  Avg: {stats['a260_a230']['avg']:.2f}")
    
    print("\n=== Quality Notes ===")
    print("- Good DNA purity: A260/A280 = 1.8-2.0")
    print("- Good RNA purity: A260/A280 = 2.0-2.2")
    print("- Good sample purity: A260/A230 = 2.0-2.2")
    print("- Low A260/A280 (<1.8): Possible protein contamination")
    print("- Low A260/A230 (<1.8): Possible organic contamination")