#!/usr/bin/env python3
"""
Check extraction accuracy by comparing AI-extracted data with the actual plate reader image.
"""

import json
import argparse

def analyze_plate_accuracy():
    """
    Analyze the accuracy of the 96-well plate extraction.
    Based on the plate reader image: tests/fixtures/test_images/plate_reader_96well.jpg
    """
    
    # Ground truth from the actual plate reader image (manual verification)
    # Reading the values row by row from the image
    ground_truth = {
        # Row A
        "A1": 400, "A2": 109, "A3": 381, "A4": 314, "A5": 169, "A6": 601, 
        "A7": 384, "A8": 775, "A9": 495, "A10": 25, "A11": 22, "A12": 20,
        
        # Row B  
        "B1": 509, "B2": 236, "B3": 519, "B4": 378, "B5": 163, "B6": 628,
        "B7": 505, "B8": 803, "B9": 700, "B10": 19, "B11": 54, "B12": 46,
        
        # Row C
        "C1": 383, "C2": 192, "C3": 269, "C4": 275, "C5": 220, "C6": 527,
        "C7": 440, "C8": 422, "C9": 511, "C10": 23, "C11": 73, "C12": 78,
        
        # Row D
        "D1": 334, "D2": 152, "D3": 260, "D4": 271, "D5": 218, "D6": 458,
        "D7": 454, "D8": 472, "D9": 436, "D10": 19, "D11": 164, "D12": 144,
        
        # Row E
        "E1": 326, "E2": 271, "E3": 235, "E4": 308, "E5": 93, "E6": 456,
        "E7": 604, "E8": 432, "E9": 502, "E10": 24, "E11": 330, "E12": 300,
        
        # Row F
        "F1": 443, "F2": 251, "F3": 377, "F4": 387, "F5": 67, "F6": 648,
        "F7": 577, "F8": 670, "F9": 723, "F10": 23, "F11": 472, "F12": 425,
        
        # Row G
        "G1": 937, "G2": 204, "G3": 500, "G4": 388, "G5": 108, "G6": 1087,
        "G7": 461, "G8": 821, "G9": 678, "G10": 24, "G11": 616, "G12": 610,
        
        # Row H
        "H1": 678, "H2": 22, "H3": 410, "H4": 27, "H5": 83, "H6": 969,
        "H7": 21, "H8": 672, "H9": 19, "H10": 17, "H11": 736, "H12": 721
    }
    
    # Load extracted data
    try:
        with open('extracted_data.json', 'r') as f:
            data = json.load(f)
        
        extracted_samples = data['extracted_data']['samples']
        extracted_dict = {sample['well']: sample['value'] for sample in extracted_samples}
        
    except FileNotFoundError:
        print("❌ extracted_data.json not found. Run a test first to generate the data.")
        return
    except Exception as e:
        print(f"❌ Error loading extracted data: {e}")
        return
    
    # Compare values
    total_wells = len(ground_truth)
    correct_matches = 0
    errors = []
    missing_wells = []
    
    print(f"🔍 ACCURACY ANALYSIS")
    print(f"{'='*60}")
    print(f"Total wells in ground truth: {total_wells}")
    print(f"Total wells extracted: {len(extracted_dict)}")
    print()
    
    for well, true_value in ground_truth.items():
        if well in extracted_dict:
            extracted_value = extracted_dict[well]
            if extracted_value == true_value:
                correct_matches += 1
            else:
                errors.append({
                    'well': well,
                    'expected': true_value,
                    'extracted': extracted_value,
                    'diff': abs(extracted_value - true_value)
                })
        else:
            missing_wells.append(well)
    
    # Calculate accuracy
    accuracy = (correct_matches / total_wells) * 100
    
    print(f"✅ Correct matches: {correct_matches}/{total_wells}")
    print(f"📊 Accuracy: {accuracy:.1f}%")
    
    if missing_wells:
        print(f"❌ Missing wells: {len(missing_wells)}")
        print(f"   {', '.join(missing_wells)}")
    
    if errors:
        print(f"⚠️  Incorrect values: {len(errors)}")
        print(f"{'Well':<6} {'Expected':<10} {'Extracted':<10} {'Diff':<6}")
        print("-" * 35)
        for error in errors[:10]:  # Show first 10 errors
            print(f"{error['well']:<6} {error['expected']:<10} {error['extracted']:<10} {error['diff']:<6}")
        
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    
    # Column-specific analysis
    print(f"\n📈 COLUMN ANALYSIS")
    print("Checking if columns 11 and 12 have more errors...")
    
    col_11_errors = [e for e in errors if e['well'].endswith('11')]
    col_12_errors = [e for e in errors if e['well'].endswith('12')]
    
    print(f"Column 11 errors: {len(col_11_errors)}/8 wells")
    print(f"Column 12 errors: {len(col_12_errors)}/8 wells")
    
    if col_11_errors:
        print("Column 11 issues:", [f"{e['well']}({e['expected']}→{e['extracted']})" for e in col_11_errors])
    if col_12_errors:
        print("Column 12 issues:", [f"{e['well']}({e['expected']}→{e['extracted']})" for e in col_12_errors])
    
    print(f"\n💡 SUMMARY")
    if accuracy >= 95:
        print("🎉 Excellent accuracy! The AI is reading the plate very well.")
    elif accuracy >= 90:
        print("✅ Good accuracy. Minor issues that could be improved.")
    elif accuracy >= 80:
        print("⚠️  Moderate accuracy. Some systematic issues to investigate.")
    else:
        print("❌ Low accuracy. Significant problems with extraction.")
    
    return {
        'accuracy': accuracy,
        'correct': correct_matches,
        'total': total_wells,
        'errors': len(errors),
        'missing': len(missing_wells)
    }

def main():
    parser = argparse.ArgumentParser(description='Check extraction accuracy')
    parser.add_argument('--json', help='Path to extracted data JSON file', 
                        default='extracted_data.json')
    
    args = parser.parse_args()
    
    # Change to the JSON file if specified
    if args.json != 'extracted_data.json':
        import os
        global extracted_data_file
        extracted_data_file = args.json
    
    analyze_plate_accuracy()

if __name__ == '__main__':
    main()