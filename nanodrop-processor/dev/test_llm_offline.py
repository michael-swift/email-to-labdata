#!/usr/bin/env python3
"""
Test LLM extraction without API calls for development.
This simulates LLM responses for testing the pipeline.
"""

import json
import random
from pathlib import Path
from llm_extractor import compare_extractions, load_ground_truth


def simulate_llm_response(image_name: str, accuracy_level: str = "high") -> dict:
    """
    Simulate LLM responses with different accuracy levels.
    
    Args:
        image_name: Name of the image being processed
        accuracy_level: "perfect", "high", "medium", "low", "bad"
    
    Returns:
        Simulated LLM extraction result
    """
    ground_truth = load_ground_truth()
    
    if image_name not in ground_truth:
        return {"error": "Unknown image"}
    
    gt_data = ground_truth[image_name]
    
    if accuracy_level == "perfect":
        # Return exact ground truth
        return gt_data.copy()
    
    elif accuracy_level == "high":
        # 95% accurate - minor decimal variations
        result = {
            "load_number": gt_data["load_number"],
            "samples": []
        }
        
        for sample in gt_data["samples"]:
            # Add small random errors (±2%)
            new_sample = {
                "sample_number": sample["sample_number"],
                "concentration": round(sample["concentration"] * random.uniform(0.98, 1.02), 1),
                "a260_a280": round(sample["a260_a280"] * random.uniform(0.99, 1.01), 2),
                "a260_a230": round(sample["a260_a230"] * random.uniform(0.99, 1.01), 2)
            }
            result["samples"].append(new_sample)
        
        return result
    
    elif accuracy_level == "medium":
        # 80% accurate - some values wrong, might miss samples
        result = {
            "load_number": gt_data["load_number"],
            "samples": []
        }
        
        # Randomly skip 20% of samples
        for sample in gt_data["samples"]:
            if random.random() > 0.2:  # Include 80% of samples
                new_sample = {
                    "sample_number": sample["sample_number"],
                    "concentration": round(sample["concentration"] * random.uniform(0.9, 1.1), 1),
                    "a260_a280": round(sample["a260_a280"] * random.uniform(0.95, 1.05), 2),
                    "a260_a230": round(sample["a260_a230"] * random.uniform(0.95, 1.05), 2)
                }
                result["samples"].append(new_sample)
        
        return result
    
    elif accuracy_level == "low":
        # 60% accurate - major errors
        result = {
            "load_number": gt_data["load_number"] if random.random() > 0.3 else "unknown",
            "samples": []
        }
        
        # Include only half the samples with large errors
        for sample in gt_data["samples"]:
            if random.random() > 0.5:
                new_sample = {
                    "sample_number": sample["sample_number"],
                    "concentration": round(sample["concentration"] * random.uniform(0.7, 1.3), 1),
                    "a260_a280": round(sample["a260_a280"] * random.uniform(0.8, 1.2), 2),
                    "a260_a230": round(sample["a260_a230"] * random.uniform(0.8, 1.2), 2)
                }
                result["samples"].append(new_sample)
        
        return result
    
    else:  # "bad"
        # Very poor extraction
        return {
            "load_number": "unknown",
            "samples": [
                {
                    "sample_number": 1,
                    "concentration": random.uniform(10, 100),
                    "a260_a280": random.uniform(1.5, 2.5),
                    "a260_a230": random.uniform(1.5, 2.5)
                }
            ]
        }


def test_accuracy_levels():
    """Test different accuracy levels."""
    print("🧪 Testing LLM Accuracy Simulation")
    print("="*50)
    
    ground_truth = load_ground_truth()
    accuracy_levels = ["perfect", "high", "medium", "low", "bad"]
    
    results = {}
    
    for level in accuracy_levels:
        print(f"\n📊 Testing accuracy level: {level.upper()}")
        
        level_results = []
        
        for image_name in ground_truth.keys():
            # Simulate LLM response
            simulated_result = simulate_llm_response(image_name, level)
            
            # Compare with ground truth
            comparison = compare_extractions(simulated_result, ground_truth[image_name])
            
            if "accuracy_metrics" in comparison:
                accuracy = comparison["accuracy_metrics"]["field_accuracy"]
                level_results.append(accuracy)
                print(f"  {image_name}: {accuracy:.1%}")
        
        if level_results:
            avg_accuracy = sum(level_results) / len(level_results)
            results[level] = avg_accuracy
            print(f"  Average: {avg_accuracy:.1%}")
    
    # Summary
    print(f"\n🎯 ACCURACY SIMULATION SUMMARY")
    print("-" * 30)
    for level, accuracy in results.items():
        print(f"{level.capitalize():>8}: {accuracy:.1%}")
    
    return results


def test_parsing_robustness():
    """Test parsing different LLM response formats."""
    print("\n🔧 Testing Response Parsing Robustness")
    print("="*50)
    
    from llm_extractor import NanodropLLMExtractor
    
    extractor = NanodropLLMExtractor()
    
    # Test different response formats
    test_responses = [
        # Clean JSON
        '{"load_number": "6", "samples": [{"sample_number": 1, "concentration": 19.0, "a260_a280": 1.83, "a260_a230": 2.08}]}',
        
        # JSON in markdown
        '''```json
{"load_number": "6", "samples": [{"sample_number": 1, "concentration": 19.0, "a260_a280": 1.83, "a260_a230": 2.08}]}
```''',
        
        # JSON with explanation
        '''Based on the image, I can extract the following data:

```json
{"load_number": "6", "samples": [{"sample_number": 1, "concentration": 19.0, "a260_a280": 1.83, "a260_a230": 2.08}]}
```

The measurements show good DNA purity.''',
        
        # Malformed but parseable
        '''{
  "load_number": "6",
  "samples": [
    {
      "sample_number": 1,
      "concentration": 19.0,
      "a260_a280": 1.83,
      "a260_a230": 2.08
    }
  ]
}''',
    ]
    
    for i, response in enumerate(test_responses, 1):
        print(f"\nTest {i}: ", end="")
        try:
            result = extractor._parse_llm_response(response)
            if extractor._validate_extracted_data(result):
                print("✓ Parsed successfully")
            else:
                print("✗ Parsed but invalid structure")
        except Exception as e:
            print(f"✗ Failed: {e}")


if __name__ == "__main__":
    # Test accuracy simulation
    test_accuracy_levels()
    
    # Test parsing robustness
    test_parsing_robustness()
    
    print(f"\n🚀 Ready to test with real LLM API!")
    print(f"Run: python llm_extractor.py (after setting OPENAI_API_KEY)")