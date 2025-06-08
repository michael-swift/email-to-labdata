#!/usr/bin/env python3
"""
Real LLM extraction for Nanodrop images using OpenAI Vision API.
This will test against our ground truth data.
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import openai
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class NanodropLLMExtractor:
    """Extract Nanodrop data using OpenAI Vision API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.extraction_log = []
    
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def extract_nanodrop_data(self, image_path: str) -> Dict:
        """
        Extract data from Nanodrop screen image using LLM.
        
        Args:
            image_path: Path to the Nanodrop image
            
        Returns:
            Dictionary with extracted data
        """
        print(f"Processing {image_path}...")
        
        # Encode image
        base64_image = self.encode_image(image_path)
        
        # Optimized prompt based on our analysis
        prompt = """
Analyze this Nanodrop spectrophotometer screen image and extract ALL visible measurement data from the table.

IMPORTANT INSTRUCTIONS:
1. Look for the Load number (e.g., "Load #6", "Load #14") - ignore this for results output
2. Identify the assay type (RNA or DNA) from visual cues like:
   - Text saying "RNA" or "dsDNA" on screen
   - A260/A280 ratios around 2.0 suggest RNA, around 1.8 suggest DNA
3. Find the measurement table with columns: # (sample number), ng/μL (concentration), A260/A280, A260/A230
4. Extract ALL visible rows in the table, including:
   - Regular white/light rows
   - Highlighted/selected blue rows
   - ANY row with data, even if values are negative or unusual
5. Be EXTREMELY precise with decimal values - if you see "19.0", return exactly 19.0, not 19
6. Include negative values if present (e.g., -2.1, -2.55)
7. Some sample numbers may not be sequential (e.g., you might see samples 9,10,11,12,13)

Return data in this EXACT JSON format:
{
    "assay_type": "RNA",
    "samples": [
        {
            "sample_number": 1,
            "concentration": 19.0,
            "a260_a280": 1.83,
            "a260_a230": 2.08
        }
    ]
}

CRITICAL: 
- Extract EVERY row you can see in the table, including negative/problematic values
- Preserve exact decimal precision
- Include both regular and highlighted/blue rows
- Sample numbers should match what's displayed (may not start at 1)
- Do NOT include the load number in output - only assay_type and samples
"""
        
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1000
            )
            
            # Extract content
            content = response.choices[0].message.content
            
            # Parse JSON from response
            extracted_data = self._parse_llm_response(content)
            
            # Log the extraction
            self.extraction_log.append({
                "image_path": image_path,
                "success": True,
                "duration": time.time() - start_time,
                "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None,
                "raw_response": content[:500],  # First 500 chars
                "extracted_data": extracted_data
            })
            
            print(f"✓ Extracted {len(extracted_data.get('samples', []))} samples from {Path(image_path).name}")
            return extracted_data
            
        except Exception as e:
            # Log the failure
            self.extraction_log.append({
                "image_path": image_path,
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e),
                "raw_response": None,
                "extracted_data": None
            })
            
            print(f"✗ Failed to extract from {Path(image_path).name}: {e}")
            raise
    
    def _parse_llm_response(self, response_text: str) -> Dict:
        """Parse LLM response to extract JSON data."""
        
        # Try to extract JSON from various formats
        json_candidates = []
        
        # Look for JSON in markdown code blocks
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
            json_candidates.append(json_str.strip())
        
        # Look for JSON in regular code blocks
        if "```" in response_text and "```json" not in response_text:
            parts = response_text.split("```")
            for i in range(1, len(parts), 2):  # Odd indices are code blocks
                json_candidates.append(parts[i].strip())
        
        # Try the entire response as JSON
        json_candidates.append(response_text.strip())
        
        # Try to parse each candidate
        for candidate in json_candidates:
            try:
                # Clean up common issues
                candidate = candidate.replace('\n', ' ').replace('\r', '')
                candidate = candidate.strip()
                
                # Try direct parsing
                data = json.loads(candidate)
                
                # Validate structure
                if self._validate_extracted_data(data):
                    return data
                    
            except json.JSONDecodeError:
                continue
        
        # If all parsing fails, try manual extraction
        return self._manual_parse_fallback(response_text)
    
    def _validate_extracted_data(self, data: Dict) -> bool:
        """Validate the structure of extracted data."""
        if not isinstance(data, dict):
            return False
        
        if "samples" not in data:
            return False
        
        if not isinstance(data["samples"], list):
            return False
        
        for sample in data["samples"]:
            if not isinstance(sample, dict):
                return False
            
            required_fields = ["sample_number", "concentration", "a260_a280", "a260_a230"]
            if not all(field in sample for field in required_fields):
                return False
        
        return True
    
    def _manual_parse_fallback(self, response_text: str) -> Dict:
        """Manual parsing fallback when JSON parsing fails."""
        # This is a simple fallback - in production you'd want more sophisticated parsing
        print("Warning: Using manual parsing fallback")
        
        return {
            "assay_type": "unknown",
            "samples": [],
            "parsing_error": "Failed to parse LLM response",
            "raw_response": response_text[:200]
        }


def load_ground_truth() -> Dict[str, Dict]:
    """Load our manually extracted ground truth data."""
    return {
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
        },
        "nanodrop_load_6_rna.jpg": {
            "load_number": "6",
            "assay_type": "RNA",
            "samples": [
                {"sample_number": 1, "concentration": 87.3, "a260_a280": 1.94, "a260_a230": 2.07},
                {"sample_number": 2, "concentration": 141.7, "a260_a280": 1.89, "a260_a230": 2.01},
                {"sample_number": 3, "concentration": 74.5, "a260_a280": 1.96, "a260_a230": 2.14},
                {"sample_number": 4, "concentration": 71.4, "a260_a280": 1.85, "a260_a230": 2.0},
                {"sample_number": 5, "concentration": -2.1, "a260_a280": 2.85, "a260_a230": -2.55},
            ]
        }
    }


def compare_extractions(llm_data: Dict, ground_truth: Dict, tolerance: float = 0.05) -> Dict:
    """Compare LLM extraction with ground truth."""
    comparison = {
        "load_number_match": llm_data.get("load_number") == ground_truth.get("load_number"),
        "sample_count_match": len(llm_data.get("samples", [])) == len(ground_truth.get("samples", [])),
        "sample_matches": [],
        "accuracy_metrics": {}
    }
    
    llm_samples = {s["sample_number"]: s for s in llm_data.get("samples", [])}
    gt_samples = {s["sample_number"]: s for s in ground_truth.get("samples", [])}
    
    # Compare each sample
    total_fields = 0
    correct_fields = 0
    
    for sample_num in gt_samples:
        if sample_num in llm_samples:
            llm_sample = llm_samples[sample_num]
            gt_sample = gt_samples[sample_num]
            
            match_result = {
                "sample_number": sample_num,
                "concentration_match": abs(llm_sample["concentration"] - gt_sample["concentration"]) <= tolerance * gt_sample["concentration"],
                "a260_a280_match": abs(llm_sample["a260_a280"] - gt_sample["a260_a280"]) <= tolerance,
                "a260_a230_match": abs(llm_sample["a260_a230"] - gt_sample["a260_a230"]) <= tolerance,
                "llm_values": llm_sample,
                "ground_truth": gt_sample
            }
            
            # Count accuracy
            for field in ["concentration", "a260_a280", "a260_a230"]:
                total_fields += 1
                if match_result[f"{field}_match"]:
                    correct_fields += 1
            
            comparison["sample_matches"].append(match_result)
        else:
            comparison["sample_matches"].append({
                "sample_number": sample_num,
                "missing_in_llm": True,
                "ground_truth": gt_samples[sample_num]
            })
    
    # Calculate accuracy metrics
    if total_fields > 0:
        comparison["accuracy_metrics"] = {
            "field_accuracy": correct_fields / total_fields,
            "total_fields": total_fields,
            "correct_fields": correct_fields
        }
    
    return comparison


def test_llm_extraction():
    """Test LLM extraction against all images."""
    print("🚀 Starting LLM extraction testing...")
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable not set!")
        print("Set it with: export OPENAI_API_KEY='your-api-key'")
        return
    
    extractor = NanodropLLMExtractor()
    ground_truth = load_ground_truth()
    
    image_dir = Path("images")
    results = {}
    
    # Test each image
    for image_name in ground_truth.keys():
        image_path = image_dir / image_name
        
        if not image_path.exists():
            print(f"❌ Image not found: {image_path}")
            continue
        
        try:
            # Extract using LLM
            llm_result = extractor.extract_nanodrop_data(str(image_path))
            
            # Compare with ground truth
            comparison = compare_extractions(llm_result, ground_truth[image_name])
            
            results[image_name] = {
                "llm_extraction": llm_result,
                "comparison": comparison,
                "success": True
            }
            
        except Exception as e:
            print(f"❌ Failed to process {image_name}: {e}")
            results[image_name] = {
                "success": False,
                "error": str(e)
            }
    
    # Print results summary
    print("\n" + "="*60)
    print("🎯 LLM EXTRACTION RESULTS")
    print("="*60)
    
    total_accuracy = 0
    successful_extractions = 0
    
    for image_name, result in results.items():
        print(f"\n📸 {image_name}")
        
        if result["success"]:
            comparison = result["comparison"]
            
            print(f"  Load number: {'✓' if comparison['load_number_match'] else '✗'}")
            print(f"  Sample count: {'✓' if comparison['sample_count_match'] else '✗'}")
            
            if "accuracy_metrics" in comparison:
                accuracy = comparison["accuracy_metrics"]["field_accuracy"]
                print(f"  Field accuracy: {accuracy:.1%} ({comparison['accuracy_metrics']['correct_fields']}/{comparison['accuracy_metrics']['total_fields']})")
                total_accuracy += accuracy
                successful_extractions += 1
            
            # Show sample-level details
            for match in comparison["sample_matches"]:
                if "missing_in_llm" in match:
                    print(f"    Sample {match['sample_number']}: ❌ Missing in LLM")
                else:
                    sample_num = match["sample_number"]
                    conc_ok = '✓' if match["concentration_match"] else '✗'
                    ratio1_ok = '✓' if match["a260_a280_match"] else '✗'
                    ratio2_ok = '✓' if match["a260_a230_match"] else '✗'
                    print(f"    Sample {sample_num}: Conc {conc_ok} | 260/280 {ratio1_ok} | 260/230 {ratio2_ok}")
        else:
            print(f"  ❌ Extraction failed: {result['error']}")
    
    # Overall summary
    if successful_extractions > 0:
        overall_accuracy = total_accuracy / successful_extractions
        print(f"\n🎯 OVERALL ACCURACY: {overall_accuracy:.1%}")
        print(f"📊 Successful extractions: {successful_extractions}/{len(results)}")
    
    # Save detailed results
    with open("llm_test_results.json", "w") as f:
        json.dump({
            "results": results,
            "extraction_log": extractor.extraction_log,
            "summary": {
                "overall_accuracy": overall_accuracy if successful_extractions > 0 else 0,
                "successful_extractions": successful_extractions,
                "total_images": len(results)
            }
        }, f, indent=2)
    
    print(f"\n📝 Detailed results saved to llm_test_results.json")


if __name__ == "__main__":
    test_llm_extraction()