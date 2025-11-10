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
import openai
from datetime import datetime
import time
import re
from PIL import Image
from security_config import SecurityConfig
from structured_logger import logger
from dynamodb_schema import DynamoDBManager
from services.csv_service import (
    annotate_sample_quality as service_annotate_sample_quality,
    generate_csv as service_generate_csv,
    assess_quality as service_assess_quality,
)
from services.email_service import (
    send_success_email as service_send_success_email,
    send_error_email as service_send_error_email,
)

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


def assess_quality(a260_a280, a260_a230, concentration):
    return service_assess_quality(a260_a280, a260_a230, concentration)


def annotate_sample_quality(data):
    return service_annotate_sample_quality(data)


def generate_csv(data):
    return service_generate_csv(data)


def send_success_email(recipients, csv_content, data, original_images):
    return service_send_success_email(ses, recipients, csv_content, data, original_images)


def send_error_email(to_email, error_message):
    return service_send_error_email(ses, to_email, error_message)

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
        
        # Loop prevention: Check if this is a results email we sent
        if (subject and "Lab Data Results" in subject) or \
           (from_email and any(addr in from_email for addr in ['digitizer@seminalcapital.net', 'nanodrop@seminalcapital.net'])):
            logger.info("Ignoring results email to prevent loop", subject=subject, from_email=from_email)
            return {'statusCode': 200, 'body': 'Results email ignored'}
        
        # Check for our processing header to prevent re-processing
        if msg.get('X-Lab-Data-Processed'):
            logger.info("Ignoring already processed email", message_id=msg.get('Message-ID'))
            return {'statusCode': 200, 'body': 'Already processed'}
        
        # Extract just the email address from the From field
        # Handle formats like "Name <email@domain.com>" or just "email@domain.com"
        email_match = re.search(r'<(.+?)>', from_email)
        if email_match:
            sender_email = email_match.group(1)
        else:
            sender_email = from_email.strip()
        
        # Extract all recipients for reply-all functionality
        service_addresses = {'digitizer@seminalcapital.net', 'nanodrop@seminalcapital.net', 
                            'nanodrop-dev@seminalcapital.net'}
        
        # Extract To recipients (multiple recipients in To field)
        to_recipients = []
        to_header = msg.get('To') or msg.get('to')
        if to_header:
            # Parse To header which can contain multiple emails
            to_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', to_header)
            # Filter out our service addresses to prevent loops
            to_recipients = [addr for addr in to_emails if addr not in service_addresses]
            if to_recipients:
                logger.info("To recipients extracted", to_count=len(to_recipients), to_recipients=to_recipients)
        
        # Extract CC recipients
        cc_recipients = []
        cc_header = msg.get('CC') or msg.get('Cc') or msg.get('cc')
        if cc_header:
            # Parse CC header which can contain multiple emails
            cc_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', cc_header)
            # Filter out our service addresses to prevent loops
            cc_recipients = [addr for addr in cc_emails if addr not in service_addresses]
            if cc_recipients:
                logger.info("CC recipients extracted", cc_count=len(cc_recipients), cc_recipients=cc_recipients)
        
        # Combine all recipients and remove duplicates
        # Start with sender, add To recipients, then CC recipients
        all_recipients = [sender_email]
        all_recipients.extend(to_recipients)
        all_recipients.extend(cc_recipients)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recipients = []
        for addr in all_recipients:
            if addr not in seen:
                seen.add(addr)
                unique_recipients.append(addr)
        
        # Remove the sender from additional recipients (they're already first)
        additional_recipients = unique_recipients[1:] if len(unique_recipients) > 1 else []
        
        if additional_recipients:
            logger.info("All additional recipients", 
                       additional_count=len(additional_recipients), 
                       additional_recipients=additional_recipients)
        
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
        logger.info("Starting image extraction from email")
        image_attachments = extract_images_from_email(msg)
        logger.info(f"Found {len(image_attachments) if image_attachments else 0} image attachments")
        if not image_attachments:
            logger.info("No image attachments found, sending error email")
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
                lab_data = extract_lab_data(image_data)
                results_list.append(lab_data)
                processed_images.append(image_data)
                
                # Log successful image processing
                samples_in_image = len(lab_data.get('samples', []))
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
        combined_data = merge_lab_results(results_list)
        
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
        
        # Send reply with CSV and original photos (including all recipients)
        send_success_email(unique_recipients, csv_content, combined_data, processed_images)
        
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
