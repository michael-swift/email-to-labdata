#!/usr/bin/env python3
"""LLM operations for data extraction and merging."""

import os
import json
import base64
import time
from typing import Any, Dict, List
import openai

from structured_logger import logger

# Global OpenAI client (lazy initialization)
openai_client = None


def get_openai_client():
    """Get or create OpenAI client."""
    global openai_client
    if openai_client is None:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        openai_client = openai.OpenAI(api_key=api_key)
    return openai_client


def normalize_unicode_headers(data):
    """Normalize Unicode characters in column headers and sample data to ASCII-safe alternatives."""
    if not isinstance(data, dict):
        return data

    # Character mapping for common corruptions
    char_mapping = {
        'μ': 'u',  # Greek mu to ASCII u
        '無': 'u',  # Corrupted character back to u
        '°': 'deg'  # Degree symbol to ASCII
    }

    def clean_string(text):
        if not isinstance(text, str):
            return text
        for old_char, new_char in char_mapping.items():
            text = text.replace(old_char, new_char)
        return text

    # Clean column headers
    if 'columns' in data and isinstance(data['columns'], list):
        data['columns'] = [clean_string(col) for col in data['columns']]

    # Clean sample data keys
    if 'samples' in data and isinstance(data['samples'], list):
        cleaned_samples = []
        for sample in data['samples']:
            if isinstance(sample, dict):
                cleaned_sample = {}
                for key, value in sample.items():
                    cleaned_key = clean_string(key)
                    cleaned_sample[cleaned_key] = value
                cleaned_samples.append(cleaned_sample)
            else:
                cleaned_samples.append(sample)
        data['samples'] = cleaned_samples

    return data


def extract_lab_data(image_bytes):
    """Extract data from lab instrument image using GPT-4o - simplified universal approach."""
    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    # Single universal prompt that handles everything
    prompt = """
    Extract ALL data from this lab instrument image.

    For standard tables (Nanodrop, UV-Vis, etc.):
    - Extract exact column headers and all row data
    - Use ASCII-safe units: "ng/uL" instead of "ng/μL", "deg" instead of "°"

    For 96-well plates:
    - Extract well positions (A1, B2, etc.) and values
    - Also provide in long form: [{"well": "A1", "value": X}, ...]

    Return JSON:
    {
        "instrument": "detected instrument type",
        "confidence": "high|medium|low",
        "is_plate_format": true/false,
        "columns": ["headers"] (if table format),
        "samples": [{"col1": "val1", ...}] or [{"well": "A1", "value": X}],
        "plate_data": {"A1": value, ...} (if plate format),
        "notes": "any relevant observations"
    }

    Extract all visible data precisely. Use scientific notation if shown (e.g., 1.23E+04).
    IMPORTANT: Use ASCII-safe characters only in column headers and units.
    """

    try:
        client = get_openai_client()
        start_time = time.time()

        response = client.chat.completions.create(
            model="gpt-4o",
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
            temperature=0.1
            # Let OpenAI handle tokens and timeout defaults
        )

        # Log OpenAI request details
        duration_ms = int((time.time() - start_time) * 1000)
        usage = response.usage
        logger.openai_request(
            model="gpt-4o",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            duration_ms=duration_ms
        )

    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")

    # Parse response
    content = response.choices[0].message.content

    # Extract JSON from response
    if "```json" in content:
        json_str = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        json_str = content.split("```")[1].split("```")[0]
    else:
        json_str = content

    try:
        result = json.loads(json_str.strip())

        # Normalize Unicode characters in headers and data
        result = normalize_unicode_headers(result)

        # Check if extraction completely failed (no data found)
        if "error" in result and result.get("error") == "no_data":
            raise Exception(f"No tabular data found in image")

        # Log what was detected for monitoring
        if "instrument" in result:
            instrument_type = result.get("instrument", "unknown")
            confidence = result.get("confidence", "unknown")
            logger.info(f"Detected instrument: {instrument_type} (confidence: {confidence})")

        return result

    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response", response_preview=content[:500])
        raise Exception(f"Invalid response format from AI model")


def merge_lab_results(results_list):
    """Merge results from multiple images using LLM intelligence."""
    if len(results_list) == 1:
        return results_list[0]

    # Prepare data for merge prompt
    merge_input = {
        "images": []
    }

    for i, result in enumerate(results_list, 1):
        merge_input["images"].append({
            "image_number": i,
            "assay_type": result.get("assay_type", "Unknown"),
            "commentary": result.get("commentary", ""),
            "samples": result.get("samples", [])
        })

    merge_prompt = f"""
    CRITICAL: You MUST respond with ONLY valid JSON. No explanations, no markdown, no conversational text.

    Task: Merge nanodrop results from {len(results_list)} images into a single result.

    Input data: {json.dumps(merge_input, indent=2)}

    Rules:
    1. Combine all samples, sorted by sample_number
    2. For duplicate sample_numbers: choose most reliable reading (avoid negative values, prefer good ratios)
    3. Determine overall assay_type
    4. Include brief commentary about conflicts and quality

    RESPOND WITH ONLY THIS JSON STRUCTURE (no other text):
    {{
        "assay_type": "DNA",
        "commentary": "Processed {len(results_list)} images with N samples. Brief quality assessment.",
        "samples": [
            {{
                "sample_number": 1,
                "concentration": 87.3,
                "a260_a280": 1.94,
                "a260_a230": 2.07
            }}
        ]
    }}"""

    try:
        client = get_openai_client()
        start_time = time.time()

        # Define function schema for structured output
        merge_function = {
            "name": "merge_nanodrop_results",
            "description": "Merge nanodrop sample results from multiple images",
            "parameters": {
                "type": "object",
                "properties": {
                    "assay_type": {
                        "type": "string",
                        "enum": ["DNA", "RNA", "Mixed", "Unknown"]
                    },
                    "commentary": {
                        "type": "string",
                        "description": "Brief explanation of merge process and quality assessment"
                    },
                    "samples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sample_number": {"type": "integer"},
                                "concentration": {"type": "number"},
                                "a260_a280": {"type": "number"},
                                "a260_a230": {"type": "number"}
                            },
                            "required": ["sample_number", "concentration", "a260_a280", "a260_a230"]
                        }
                    }
                },
                "required": ["assay_type", "commentary", "samples"]
            }
        }

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": merge_prompt
                }
            ],
            functions=[merge_function],
            function_call={"name": "merge_nanodrop_results"},
            temperature=0.1,
            timeout=30
        )

        # Log merge request
        duration_ms = int((time.time() - start_time) * 1000)
        usage = response.usage
        logger.openai_request(
            model="gpt-4o",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            duration_ms=duration_ms
        )

        # Handle both function calling and regular content responses
        message = response.choices[0].message

        if message.function_call:
            # Function calling returns structured data directly
            function_args = message.function_call.arguments
            logger.info("LLM merge via function calling",
                       function_name=message.function_call.name,
                       args_length=len(function_args))

            result = json.loads(function_args)

            # Validate the result has all required fields and reasonable data
            if not isinstance(result.get('samples'), list) or len(result.get('samples', [])) == 0:
                raise ValueError(f"Invalid function call result: missing or empty samples")

            # Count unique sample numbers
            sample_numbers = {s.get('sample_number') for s in result.get('samples', [])}
            if len(sample_numbers) < len(results_list):  # Should have at least as many samples as images
                logger.warning("Function call result may be incomplete",
                             samples_found=len(sample_numbers),
                             images_processed=len(results_list))

            return result
        else:
            # Fallback to content parsing
            content = message.content

            # Extract JSON from response - handle multiple JSON blocks by taking the largest
            if "```json" in content:
                # Find all JSON blocks and take the largest one (most complete)
                json_blocks = content.split("```json")[1:]
                json_candidates = []
                for block in json_blocks:
                    candidate = block.split("```")[0].strip()
                    if candidate:
                        json_candidates.append(candidate)

                if json_candidates:
                    # Choose the largest JSON block (likely the most complete)
                    json_str = max(json_candidates, key=len)
                else:
                    json_str = content
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            # Log the extracted JSON for debugging
            logger.info("LLM merge JSON extraction",
                       content_length=len(content),
                       json_blocks_found=content.count("```"),
                       extracted_json_preview=json_str[:200] + "..." if len(json_str) > 200 else json_str)

            return json.loads(json_str.strip())

    except Exception as e:
        logger.warning("LLM merge failed, using fallback", error=str(e))
        return fallback_merge(results_list)


def merge_nanodrop_results_old(results_list):
    """Original merge function - now using fallback only for debugging."""
    if len(results_list) == 1:
        return results_list[0]

    # Force fallback merge for debugging
    logger.info("Forcing fallback merge for debugging")
    return fallback_merge(results_list)


def fallback_merge(results_list):
    """Fallback deterministic merge if LLM merge fails."""
    all_samples = []
    all_assay_types = set()
    all_commentary = []

    for result in results_list:
        all_samples.extend(result.get('samples', []))
        if 'assay_type' in result and result['assay_type'] != 'Unknown':
            all_assay_types.add(result['assay_type'])
        if 'commentary' in result:
            all_commentary.append(result['commentary'])

    # Merge samples by sample_number (prefer non-zero concentrations and better ratios)
    sample_dict = {}
    for sample in all_samples:
        sample_num = sample['sample_number']
        if sample_num not in sample_dict:
            sample_dict[sample_num] = sample
        else:
            # If duplicate, prefer the sample with higher concentration and better ratios
            existing = sample_dict[sample_num]
            current = sample

            # Prefer non-zero/positive concentrations
            if existing.get('concentration', 0) <= 0 and current.get('concentration', 0) > 0:
                sample_dict[sample_num] = current
            elif existing.get('concentration', 0) > 0 and current.get('concentration', 0) <= 0:
                continue  # Keep existing
            else:
                # Both valid or both invalid - prefer higher concentration
                if current.get('concentration', 0) > existing.get('concentration', 0):
                    sample_dict[sample_num] = current

    unique_samples = sorted(sample_dict.values(), key=lambda x: x['sample_number'])

    return {
        'assay_type': list(all_assay_types)[0] if len(all_assay_types) == 1 else 'Mixed',
        'commentary': f"Processed {len(results_list)} images. " + " | ".join(all_commentary),
        'samples': unique_samples
    }
