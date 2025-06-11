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

# Initialize AWS clients
s3 = boto3.client('s3')
ses = boto3.client('ses', region_name='us-west-2')

# Initialize OpenAI client (will be created when needed or mocked for testing)
openai_client = None

# Initialize security configuration
security = SecurityConfig()

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
    logger.info("Lambda invoked")
    
    try:
        # Get S3 object info from event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        logger.info("Processing S3 event", bucket=bucket, key=key)
        
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
            # Provide specific error message based on what went wrong
            if any("Not a Nanodrop image" in msg for msg in error_messages):
                error_detail = "The image(s) you sent don't appear to be from a Nanodrop spectrophotometer. Please ensure you're photographing the Nanodrop screen showing the measurement results table."
                error_type = "wrong_instrument"
            else:
                error_detail = "Could not extract data from any of the images. Please ensure the entire Nanodrop screen is clearly visible in the photo."
                error_type = "extraction_failed"
            
            logger.request_completed(
                success=False,
                images_processed=len(image_attachments),
                samples_extracted=0,
                error_type=error_type
            )
            
            send_error_email(from_email, error_detail)
            return {'statusCode': 200, 'body': 'No data extracted'}
        
        # Merge results using LLM intelligence
        combined_data = merge_nanodrop_results(results_list)
        
        # Count total samples extracted
        total_samples = len(combined_data.get('samples', []))
        logger.info("Data extraction complete", 
                   images_processed=len(processed_images),
                   samples_extracted=total_samples)
        
        # Generate CSV
        csv_content = generate_csv(combined_data)
        
        # Send reply with CSV and original photos
        send_success_email(from_email, csv_content, combined_data, processed_images)
        
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
    """Extract data from Nanodrop image using GPT-4o."""
    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = """
    Analyze this image carefully.

    FIRST: Determine if this is a Nanodrop spectrophotometer screen. Look for:
    - The word "NanoDrop" or "Nanodrop" anywhere on screen
    - A table with columns like # (sample number), ng/uL, A260/A280, A260/A230
    - Typical Nanodrop interface elements

    IF THIS IS NOT A NANODROP IMAGE:
    Return this exact JSON:
    {
        "error": "not_nanodrop",
        "instrument_detected": "describe what instrument/screen you see instead",
        "commentary": "This appears to be a [instrument type] not a Nanodrop spectrophotometer"
    }

    IF THIS IS A NANODROP IMAGE:
    Extract ALL visible measurement data from the table following these instructions:
    1. Identify the assay type (RNA or DNA) from visual cues
    2. Find the measurement table with columns: # (sample number), ng/uL (concentration), A260/A280, A260/A230
    3. Extract ALL visible rows in the table, including negative or unusual values
    4. Be EXTREMELY precise with decimal values
    
    Return data in this format:
    {
        "assay_type": "RNA",
        "commentary": "Detected X samples. Brief quality assessment.",
        "samples": [
            {
                "sample_number": 1,
                "concentration": 19.0,
                "a260_a280": 1.83,
                "a260_a230": 2.08
            }
        ]
    }
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
        temperature=0.1,
        max_tokens=1000,
        timeout=30
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
        
        # Check if it's a non-nanodrop error response
        if "error" in result and result["error"] == "not_nanodrop":
            instrument = result.get("instrument_detected", "unknown instrument")
            raise Exception(f"Not a Nanodrop image. Detected: {instrument}")
        
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
    You have nanodrop results from {len(results_list)} different images. Please merge them intelligently into a single result.

    Input data: {json.dumps(merge_input, indent=2)}

    INSTRUCTIONS:
    1. Combine all samples into one list, sorted by sample_number
    2. If the same sample_number appears multiple times, choose the most reliable reading (avoid negative values, prefer readings with good ratios)
    3. Determine the overall assay_type (if mixed, note this)
    4. Provide comprehensive commentary explaining:
       - How many images processed
       - Any conflicts resolved
       - Overall quality assessment
       - Recommendations for problematic samples

    Return in this EXACT JSON format:
    {{
        "assay_type": "RNA",
        "commentary": "Processed 2 images with samples 1-5. Sample 3 appeared in both images - selected reading with better ratios. Overall good quality except sample 5 which shows measurement error.",
        "samples": [
            {{
                "sample_number": 1,
                "concentration": 87.3,
                "a260_a280": 1.94,
                "a260_a230": 2.07
            }}
        ]
    }}
    """
    
    try:
        client = get_openai_client()
        start_time = time.time()
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user", 
                    "content": merge_prompt
                }
            ],
            temperature=0.1,
            max_tokens=1500,
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
        
        content = response.choices[0].message.content
        
        # Extract JSON from response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        else:
            json_str = content
        
        return json.loads(json_str.strip())
        
    except Exception as e:
        logger.warning("LLM merge failed, using fallback", error=str(e))
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
    
    # Remove duplicates by sample_number (keep first occurrence)
    seen_samples = set()
    unique_samples = []
    for sample in sorted(all_samples, key=lambda x: x['sample_number']):
        if sample['sample_number'] not in seen_samples:
            unique_samples.append(sample)
            seen_samples.add(sample['sample_number'])
    
    return {
        'assay_type': list(all_assay_types)[0] if len(all_assay_types) == 1 else 'Mixed',
        'commentary': f"Processed {len(results_list)} images. " + " | ".join(all_commentary),
        'samples': unique_samples
    }


def generate_csv(data):
    """Generate CSV content from extracted data."""
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Sample Number', 'Concentration (ng/uL)', 
        'A260/A280', 'A260/A230', 'Quality Assessment', 'Assay Type'
    ])
    
    # Data rows
    assay_type = data.get('assay_type', 'Unknown')
    for sample in data['samples']:
        quality = assess_quality(sample['a260_a280'], sample['a260_a230'], sample['concentration'])
        writer.writerow([
            sample['sample_number'],
            sample['concentration'],
            sample['a260_a280'],
            sample['a260_a230'],
            quality,
            assay_type
        ])
    
    return output.getvalue()


def compress_image_for_email(image_data, max_size_kb=500):
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
    
    # Email body
    body = f"""Your Nanodrop data has been processed successfully!

Assay Type: {assay_type}
Images Processed: {image_count}
Samples Extracted: {sample_count}

ANALYSIS SUMMARY:
{commentary}

SAMPLE RESULTS:
"""
    
    for sample in data['samples']:
        concentration = sample['concentration']
        sample_num = sample['sample_number']
        a260_280 = sample['a260_a280']
        a260_230 = sample['a260_a230']
        
        if concentration < 0:
            body += f"    Sample {sample_num}: INVALID (negative concentration: {concentration})\n"
        else:
            body += f"    Sample {sample_num}: {concentration} ng/uL (260/280: {a260_280}, 260/230: {a260_230})\n"
    
    body += f"""

The detailed results are attached as a CSV file, along with your original image(s) for reference.

--
Nanodrop Processing Service
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
            compressed_image = compress_image_for_email(image_data, max_size_kb=500)
            
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
        compressed_image = compress_image_for_email(original_images, max_size_kb=500)
        
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