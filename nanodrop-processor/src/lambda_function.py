#!/usr/bin/env python3
"""
AWS Lambda function for Nanodrop email processing.
Triggered by S3 when new emails arrive via SES.
"""

import os
import json
import boto3
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64
from io import BytesIO
import csv
import openai
from datetime import datetime
import time
import re
from PIL import Image
from security_config import SecurityConfig
from structured_logger import logger
from dynamodb_schema import DynamoDBManager

# Initialize AWS clients
s3 = boto3.client('s3')
ses = boto3.client('ses', region_name='us-west-2')

# Initialize OpenAI client (will be created when needed or mocked for testing)
openai_client = None

# Get environment configuration
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')
S3_PREFIX = os.environ.get('S3_PREFIX', 'incoming/')
TABLE_PREFIX = os.environ.get('TABLE_PREFIX', '')

# Initialize security configuration and DynamoDB
security = SecurityConfig(table_prefix=TABLE_PREFIX)
db_manager = DynamoDBManager(table_prefix=TABLE_PREFIX)

def get_openai_client():
    """Get or create OpenAI client."""
    global openai_client
    if openai_client is None:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        openai_client = openai.OpenAI(api_key=api_key)
    return openai_client

def lambda_handler(event, context):
    """Main Lambda handler - processes emails from S3."""
    # Set up logging context
    request_id = context.aws_request_id if context else "local-test"
    logger.set_request_context(request_id, event)
    logger.info("Lambda invoked", environment=ENVIRONMENT, s3_prefix=S3_PREFIX, table_prefix=TABLE_PREFIX)
    
    try:
        # Get S3 object info from event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        logger.info("Processing S3 event", bucket=bucket, key=key)
        
        # Start timing for analytics
        processing_start_time = time.time()
        
        # Download email from S3
        email_obj = s3.get_object(Bucket=bucket, Key=key)
        email_content = email_obj['Body'].read()
        
        # Parse email
        msg = email.message_from_bytes(email_content)
        from_email = msg['From']
        subject = msg['Subject']
        
        # Extract just the email address from the From field
        # Handle formats like "Name <email@domain.com>" or just "email@domain.com"
        email_match = re.search(r'<(.+?)>', from_email)
        if email_match:
            sender_email = email_match.group(1)
        else:
            sender_email = from_email.strip()
        
        # Set user context for logging
        logger.set_user_context(from_email, subject)
        logger.info("Email parsed successfully")
        
        # Security validation
        try:
            # Validate sender email
            email_validation = security.validate_email_sender(sender_email)
            if not email_validation['valid']:
                security.log_security_event('EmailBlocked', sender_email, email_validation['reason'])
                send_error_email(from_email, f"Email blocked: {email_validation['reason']}")
                return {'statusCode': 200, 'body': 'Email blocked'}
            
            # Check rate limits
            rate_check = security.check_rate_limit(sender_email)
            if not rate_check['allowed']:
                security.log_security_event('RateLimitExceeded', sender_email, rate_check['reason'])
                send_error_email(from_email, f"Rate limit exceeded: {rate_check['reason']}. Please try again in {rate_check['retry_after']} seconds.")
                return {'statusCode': 200, 'body': 'Rate limited'}
        
        except Exception as e:
            logger.error("Security validation failed", exception=e)
            # Continue processing if security check fails (fail open for availability)
        
        # Extract all image attachments
        image_attachments = extract_images_from_email(msg)
        if not image_attachments:
            send_error_email(from_email, "No image attachments found")
            return {'statusCode': 200, 'body': 'No images found'}
        
        # Validate attachments
        try:
            attachment_data = []
            for img_data in image_attachments:
                attachment_data.append({
                    'content_type': 'image/jpeg',  # Assume JPEG for extracted images
                    'data': img_data
                })
            
            attachment_validation = security.validate_attachments(attachment_data)
            if not attachment_validation['valid']:
                security.log_security_event('InvalidAttachment', from_email, '; '.join(attachment_validation['errors']))
                send_error_email(from_email, f"Invalid attachments: {'; '.join(attachment_validation['errors'])}")
                return {'statusCode': 200, 'body': 'Invalid attachments'}
        
        except Exception as e:
            logger.error("Attachment validation failed", exception=e)
            # Continue processing if attachment validation fails
        
        logger.info("Images found", image_count=len(image_attachments))
        
        # Process each image with GPT-4o
        results_list = []
        processed_images = []
        error_messages = []
        
        for i, image_data in enumerate(image_attachments, 1):
            try:
                logger.info("Processing image", image_number=i, total_images=len(image_attachments))
                nanodrop_data = extract_nanodrop_data(image_data)
                results_list.append(nanodrop_data)
                processed_images.append(image_data)
                
                # Log successful image processing
                samples_in_image = len(nanodrop_data.get('samples', []))
                logger.image_processed(
                    image_number=i,
                    total_images=len(image_attachments),
                    success=True,
                    samples_extracted=samples_in_image
                )
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing image {i}", error_message=error_msg)
                error_messages.append(f"Image {i}: {error_msg}")
                
                # Log failed image processing
                logger.image_processed(
                    image_number=i,
                    total_images=len(image_attachments),
                    success=False,
                    error_message=error_msg
                )
                # Continue with other images
                continue
        
        if not results_list:
            # Provide helpful error message for extraction failure
            if any("No tabular data found" in msg for msg in error_messages):
                error_detail = "Could not find any tabular data in your image(s). Please ensure you're photographing a lab instrument screen showing measurement results in a table format."
                error_type = "no_data_found"
            else:
                error_detail = "Unable to extract data from the image(s). Please ensure the entire instrument screen is clearly visible and well-lit in the photo."
                error_type = "extraction_failed"
            
            # Calculate processing time for failed requests too
            processing_time_ms = int((time.time() - processing_start_time) * 1000)
            
            # Log failed request to DynamoDB (fails gracefully)
            db_manager.log_request(
                user_email=sender_email,
                request_id=request_id,
                images_processed=len(image_attachments),
                samples_extracted=0,
                processing_time_ms=processing_time_ms,
                success=False,
                error_message=error_detail,
                additional_data={
                    'error_type': error_type,
                    's3_key': key
                }
            )
            
            logger.request_completed(
                success=False,
                images_processed=len(image_attachments),
                samples_extracted=0,
                error_type=error_type
            )
            
            send_error_email(from_email, error_detail)
            return {'statusCode': 200, 'body': 'No data extracted'}
        
        # Merge results using LLM intelligence (with fixed fallback)
        combined_data = merge_nanodrop_results(results_list)
        
        # Count total samples extracted
        total_samples = len(combined_data.get('samples', []))
        logger.info("Data extraction complete", 
                   images_processed=len(processed_images),
                   samples_extracted=total_samples)
        
        # Log the data structure for debugging
        logger.info("Data structure for CSV generation", 
                   data_keys=list(combined_data.keys()),
                   sample_count=len(combined_data.get('samples', [])),
                   first_sample_keys=list(combined_data.get('samples', [{}])[0].keys()) if combined_data.get('samples') else [],
                   has_columns=('columns' in combined_data),
                   has_is_plate_format=('is_plate_format' in combined_data),
                   columns=combined_data.get('columns', 'N/A'))
        
        # Generate CSV
        csv_content = generate_csv(combined_data)
        
        # Save extracted data and CSV to S3 for accuracy analysis
        debug_prefix = f"debug/{ENVIRONMENT}/" if ENVIRONMENT else "debug/"
        timestamp_str = int(time.time())
        
        # Save raw extracted data as JSON
        json_key = f"{debug_prefix}extractions/{request_id}_{timestamp_str}_raw_data.json"
        json_data = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "user_email": from_email,
            "image_count": len(processed_images),
            "extracted_data": combined_data,
            "processing_time_ms": int((time.time() - processing_start_time) * 1000)
        }
        s3.put_object(
            Bucket=bucket, 
            Key=json_key, 
            Body=json.dumps(json_data, indent=2), 
            ContentType='application/json'
        )
        logger.info("Raw extraction data saved", debug_json_key=json_key)
        
        # Save CSV for comparison
        csv_key = f"{debug_prefix}csv/{request_id}_{timestamp_str}.csv"
        s3.put_object(Bucket=bucket, Key=csv_key, Body=csv_content, ContentType='text/csv')
        logger.info("CSV data saved", debug_csv_key=csv_key)
        
        # Send reply with CSV and original photos
        send_success_email(from_email, csv_content, combined_data, processed_images)
        
        # Calculate processing time
        processing_time_ms = int((time.time() - processing_start_time) * 1000)
        
        # Extract instrument types for analytics
        instrument_types = []
        for result in results_list:
            if 'instrument' in result and result['instrument'] not in instrument_types:
                instrument_types.append(result['instrument'])
        
        # Log to DynamoDB for analytics (fails gracefully)
        db_manager.log_request(
            user_email=sender_email,
            request_id=request_id,
            images_processed=len(processed_images),
            samples_extracted=total_samples,
            processing_time_ms=processing_time_ms,
            success=True,
            instrument_types=instrument_types,
            additional_data={
                'assay_type': combined_data.get('assay_type', 'Unknown'),
                's3_key': key
            }
        )
        
        # Log successful completion
        logger.request_completed(
            success=True,
            images_processed=len(processed_images),
            samples_extracted=total_samples,
            csv_generated=True
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Email processed successfully')
        }
        
    except Exception as e:
        logger.error("Email processing failed", exception=e)
        
        # Log catastrophic failure to DynamoDB if we have sender info (fails gracefully)
        if 'sender_email' in locals() and 'processing_start_time' in locals():
            processing_time_ms = int((time.time() - processing_start_time) * 1000)
            db_manager.log_request(
                user_email=sender_email,
                request_id=request_id,
                images_processed=0,
                samples_extracted=0,
                processing_time_ms=processing_time_ms,
                success=False,
                error_message=f"Catastrophic failure: {str(e)}",
                additional_data={
                    'error_type': 'system_error',
                    's3_key': locals().get('key', 'unknown')
                }
            )
        
        if 'from_email' in locals():
            send_error_email(from_email, f"Processing error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }


def extract_image_from_email(msg):
    """Extract first image attachment from email."""
    for part in msg.walk():
        if part.get_content_type() in ['image/jpeg', 'image/png', 'image/jpg']:
            return part.get_payload(decode=True)
    return None


def extract_images_from_email(msg):
    """Extract all image attachments from email."""
    images = []
    for part in msg.walk():
        if part.get_content_type() in ['image/jpeg', 'image/png', 'image/jpg']:
            image_data = part.get_payload(decode=True)
            if image_data:
                images.append(image_data)
    return images


def extract_nanodrop_data(image_bytes):
    """Extract data from lab instrument image using GPT-4o - simplified universal approach."""
    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    # Single universal prompt that handles everything
    prompt = """
    Extract ALL data from this lab instrument image.

    For standard tables (Nanodrop, UV-Vis, etc.):
    - Extract exact column headers and all row data
    
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


def merge_nanodrop_results(results_list):
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


def generate_csv(data):
    """Generate CSV content from extracted data - flexible format."""
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    
    # Handle multiple data formats
    if 'samples' in data and isinstance(data['samples'], list):
        # New simplified format or legacy format
        samples = data['samples']
        assay_type = data.get('assay_type', data.get('instrument', 'Unknown'))
    elif 'long_form_data' in data:
        # Complex flexible format
        samples = data['long_form_data'].get('samples', [])
        assay_type = data.get('assay_type_guess', 'Unknown')
    else:
        # No samples found
        samples = []
        assay_type = 'Unknown'
    
    if not samples:
        # No samples found - return empty CSV with headers
        writer.writerow(['Sample', 'Data', 'Note'])
        writer.writerow(['No data', 'extracted', 'Please check image quality'])
        return output.getvalue()
    
    # Determine CSV structure based on available data
    first_sample = samples[0]
    
    # Check if this is plate format (samples have 'well' and 'value' OR columns are numbered)
    is_plate_format = ('well' in first_sample and 'value' in first_sample) or \
                     (data.get('is_plate_format', False)) or \
                     ('columns' in data and all(str(col).isdigit() for col in data['columns'][:5]))
    
    if is_plate_format:
        # Plate format - well positions and values
        headers = ['Well', 'Value', 'Quality Assessment', 'Assay Type']
    elif 'columns' in data:
        # New simplified format - use detected columns as headers
        headers = data['columns']
        # Add quality and assay columns
        headers.extend(['Quality Assessment', 'Assay Type'])
    elif 'long_form_data' in data:
        # Complex format (old flexible format)
        headers = ['Sample ID']
        if 'standardized_values' in first_sample:
            std_vals = first_sample['standardized_values']
            if 'concentration_ng_ul' in std_vals:
                headers.append('Concentration (ng/μL)')
            if 'a260_a280' in std_vals:
                headers.append('A260/A280')
            if 'a260_a230' in std_vals:
                headers.append('A260/A230')
        headers.extend(['Quality Assessment', 'Assay Type'])
    else:
        # Legacy format
        headers = ['Sample ID', 'Concentration (ng/μL)', 'A260/A280', 'A260/A230', 'Quality Assessment', 'Assay Type']
    
    writer.writerow(headers)
    
    # Write data rows
    if is_plate_format:
        # For plate format, generate complete 96-well grid
        # Create a mapping of extracted data
        extracted_data = {}
        for sample in samples:
            if 'well' in sample and 'value' in sample:
                extracted_data[sample['well']] = sample['value']
            else:
                # Fallback: reconstruct well position
                sample_index = samples.index(sample)
                row_letter = chr(ord('A') + (sample_index // 12))
                col_number = (sample_index % 12) + 1
                well = f"{row_letter}{col_number}"
                value = sample.get('value', '')
                if not value:
                    for key, val in sample.items():
                        if isinstance(val, (int, float)) and key not in ['sample_number', 'row', 'col']:
                            value = val
                            break
                extracted_data[well] = value
        
        # Generate all 96 wells in order
        for row_letter in 'ABCDEFGH':
            for col_number in range(1, 13):
                well = f"{row_letter}{col_number}"
                if well in extracted_data and extracted_data[well] != '':
                    value = extracted_data[well]
                    quality = 'Check manually'
                else:
                    value = 'not extracted'
                    quality = 'Manual entry required'
                
                writer.writerow([well, value, quality, assay_type])
    else:
        # Non-plate format - original logic
        for sample in samples:
            row = []
            
            if 'columns' in data:
                # New simplified format - extract values in column order
                for col in data['columns']:
                    row.append(sample.get(col, ''))
                
                # Try to assess quality if we have the right columns
                quality = 'Check manually'
                try:
                    if 'A260/A280' in sample and 'A260/A230' in sample:
                        a260_a280 = float(sample['A260/A280'])
                        a260_a230 = float(sample['A260/A230'])
                        concentration = float(sample.get('Concentration', sample.get('ng/uL', 0)))
                        quality = assess_quality(a260_a280, a260_a230, concentration)
                except (ValueError, TypeError, KeyError):
                    pass
                
            elif 'long_form_data' in data:
                # Complex format (old flexible format)
                std_vals = sample.get('standardized_values', {})
                row.append(std_vals.get('sample_id', sample.get('row_id', 'Unknown')))
                
                concentration = std_vals.get('concentration_ng_ul', '')
                a260_a280 = std_vals.get('a260_a280', '')
                a260_a230 = std_vals.get('a260_a230', '')
                
                if 'Concentration (ng/μL)' in headers:
                    row.append(concentration)
                if 'A260/A280' in headers:
                    row.append(a260_a280)
                if 'A260/A230' in headers:
                    row.append(a260_a230)
                
                # Quality assessment
                quality = 'Insufficient data'
                if concentration and a260_a280 and a260_a230:
                    try:
                        quality = assess_quality(float(a260_a280), float(a260_a230), float(concentration))
                    except (ValueError, TypeError):
                        quality = 'Check values'
            else:
                # Legacy format
                row = [
                    sample.get('sample_number', ''),
                    sample.get('concentration', ''),
                    sample.get('a260_a280', ''),
                    sample.get('a260_a230', '')
                ]
                
                try:
                    quality = assess_quality(sample['a260_a280'], sample['a260_a230'], sample['concentration'])
                except (KeyError, TypeError):
                    quality = 'Check values'
            
            row.append(quality)
            row.append(assay_type)
            writer.writerow(row)
    
    return output.getvalue()


def compress_image_for_email(image_data, max_size_kb=2000):
    """Compress image to reduce email attachment size."""
    try:
        # Open image
        img = Image.open(BytesIO(image_data))
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Start with moderate compression
        quality = 85
        compressed_data = None
        
        while quality >= 30:  # Don't go below 30% quality
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            compressed_data = output.getvalue()
            
            # Check size
            if len(compressed_data) <= max_size_kb * 1024:
                break
                
            quality -= 15  # Reduce quality more aggressively
        
        return compressed_data if compressed_data else image_data
    except Exception:
        # If compression fails, return original
        return image_data


def assess_quality(ratio_260_280, ratio_260_230, concentration):
    """Simple quality assessment based on ratios and concentration."""
    issues = []
    
    # Check for negative/problematic values
    if concentration < 0:
        issues.append("Invalid negative concentration")
    elif concentration < 5:
        issues.append("Very low concentration")
    
    if ratio_260_280 < 0 or ratio_260_230 < 0:
        issues.append("Invalid negative ratios")
    elif ratio_260_280 < 1.6:
        issues.append("Possible protein contamination")
    elif ratio_260_280 > 2.5:
        issues.append("Possible RNA degradation or contamination")
    
    if ratio_260_230 < 1.5:
        issues.append("Possible organic contamination")
    elif ratio_260_230 > 3.0:
        issues.append("Unusually high 260/230")
    
    return "; ".join(issues) if issues else "Good quality"


def send_success_email(to_email, csv_content, data, original_images):
    """Send email with CSV attachment and original photos."""
    msg = MIMEMultipart()
    
    assay_type = data.get('assay_type', 'Unknown')
    sample_count = len(data['samples'])
    commentary = data.get('commentary', 'No additional analysis provided.')
    image_count = len(original_images) if isinstance(original_images, list) else 1
    
    msg['Subject'] = f'Nanodrop Results - {assay_type} Analysis ({sample_count} samples, {image_count} images)'
    msg['From'] = 'nanodrop@seminalcapital.net'
    msg['To'] = to_email
    
    # Check if this is plate format
    is_plate_format = data.get('is_plate_format', False) or \
                     (data['samples'] and 'well' in data['samples'][0])
    
    # Log plate format detection for debugging
    logger.info("Email format detection", 
               is_plate_format=is_plate_format,
               has_is_plate_format_field=data.get('is_plate_format', False),
               has_well_in_samples=(data['samples'] and 'well' in data['samples'][0]) if data['samples'] else False,
               first_sample_structure=data['samples'][0] if data['samples'] else None)
    
    # Email body - simplified for plate readers
    if is_plate_format:
        body = f"""Your lab data has been digitized successfully!

Instrument Type: {data.get('instrument', assay_type)}
Format: 96-well plate
Samples extracted: {sample_count} of 96 wells

The detailed results are attached as a complete 96-well CSV. Wells not extracted by AI are marked as "not extracted" for manual review.

Data Preview (first 5 wells):
"""
        # Show only first 5 samples for preview
        for i, sample in enumerate(data['samples'][:5], 1):
            well = sample.get('well', f'Sample {i}')
            value = sample.get('value', 'N/A')
            body += f"    {well}: {value}\n"
        
        if sample_count > 5:
            body += f"    ... and {sample_count - 5} more wells (see CSV for complete data)\n"
    else:
        # Standard nanodrop format with full details
        body = f"""Your lab data has been digitized successfully!

Assay Type: {assay_type}
Images Processed: {image_count}
Samples Extracted: {sample_count}

ANALYSIS SUMMARY:
{commentary}

SAMPLE RESULTS:
"""
        
        # Handle standard format
        for i, sample in enumerate(data['samples'], 1):
            # Try to get concentration from various possible fields
            concentration = None
            sample_id = None
            a260_280 = None
            a260_230 = None
            
            # Standard table format - try different column names
            sample_id = sample.get('#', sample.get('sample_number', f'Sample {i}'))
            concentration = sample.get('ng/μL', sample.get('ng/uL', sample.get('concentration', 'N/A')))
            a260_280 = sample.get('A260/A280', sample.get('a260_a280'))
            a260_230 = sample.get('A260/A230', sample.get('a260_a230'))
            
            # Format the output
            if isinstance(concentration, (int, float)) and concentration < 0:
                body += f"    {sample_id}: INVALID (negative value: {concentration})\n"
            elif a260_280 and a260_230:
                body += f"    {sample_id}: {concentration} ng/μL (260/280: {a260_280}, 260/230: {a260_230})\n"
            else:
                body += f"    {sample_id}: {concentration}\n"
    
    body += f"""

The detailed results are attached as a CSV file, along with your original image(s) for reference.

--
Lab Data Digitization Service
"""
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach CSV
    csv_attachment = MIMEBase('text', 'csv')
    csv_attachment.set_payload(csv_content)
    encoders.encode_base64(csv_attachment)
    csv_attachment.add_header(
        'Content-Disposition',
        f'attachment; filename=nanodrop_{assay_type.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")}_{sample_count}_samples.csv'
    )
    msg.attach(csv_attachment)
    
    # Attach compressed images
    if isinstance(original_images, list):
        for i, image_data in enumerate(original_images, 1):
            # Compress image to reduce email size
            compressed_image = compress_image_for_email(image_data, max_size_kb=2000)
            
            img_attachment = MIMEBase('image', 'jpeg')
            img_attachment.set_payload(compressed_image)
            encoders.encode_base64(img_attachment)
            img_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename=nanodrop_image_{i}.jpg'
            )
            msg.attach(img_attachment)
    else:
        # Single image (backward compatibility)
        compressed_image = compress_image_for_email(original_images, max_size_kb=2000)
        
        img_attachment = MIMEBase('image', 'jpeg')
        img_attachment.set_payload(compressed_image)
        encoders.encode_base64(img_attachment)
        img_attachment.add_header(
            'Content-Disposition',
            f'attachment; filename=original_nanodrop_image.jpg'
        )
        msg.attach(img_attachment)
    
    # Send email
    ses.send_raw_email(
        Source=msg['From'],
        Destinations=[to_email],
        RawMessage={'Data': msg.as_string()}
    )


def send_error_email(to_email, error_message):
    """Send error notification email."""
    ses.send_email(
        Source='nanodrop@seminalcapital.net',
        Destination={'ToAddresses': [to_email]},
        Message={
            'Subject': {'Data': 'Nanodrop Processing Error'},
            'Body': {
                'Text': {
                    'Data': f"""
                    Sorry, we couldn't process your Nanodrop image.
                    
                    Error: {error_message}
                    
                    Please ensure:
                    - You attached a clear photo of the Nanodrop screen
                    - The entire screen is visible
                    - The image is in JPEG or PNG format
                    
                    --
                    Nanodrop Processing Service
                    """
                }
            }
        }
    )