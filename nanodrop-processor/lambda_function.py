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

# Initialize AWS clients
s3 = boto3.client('s3')
ses = boto3.client('ses', region_name='us-west-2')

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

def lambda_handler(event, context):
    """Main Lambda handler - processes emails from S3."""
    print(f"Processing event: {json.dumps(event)}")
    
    try:
        # Get S3 object info from event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        # Download email from S3
        email_obj = s3.get_object(Bucket=bucket, Key=key)
        email_content = email_obj['Body'].read()
        
        # Parse email
        msg = email.message_from_bytes(email_content)
        from_email = msg['From']
        subject = msg['Subject']
        
        print(f"Processing email from: {from_email}, subject: {subject}")
        
        # Extract image attachment
        image_data = extract_image_from_email(msg)
        if not image_data:
            send_error_email(from_email, "No image attachment found")
            return {'statusCode': 200, 'body': 'No image found'}
        
        # Process with GPT-4o
        nanodrop_data = extract_nanodrop_data(image_data)
        
        # Generate CSV
        csv_content = generate_csv(nanodrop_data)
        
        # Send reply with CSV
        send_success_email(from_email, csv_content, nanodrop_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Email processed successfully')
        }
        
    except Exception as e:
        print(f"Error processing email: {str(e)}")
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


def extract_nanodrop_data(image_bytes):
    """Extract data from Nanodrop image using GPT-4o."""
    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = """
    Analyze this Nanodrop spectrophotometer screen image and extract ALL visible measurement data.

    Look for:
    1. Load number (e.g., "Load #6")
    2. Sample measurements table with columns:
       - Sample number (#)
       - Concentration (ng/μL)
       - A260/A280 ratio
       - A260/A230 ratio

    Return data in this EXACT JSON format:
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

    Be EXTREMELY precise with decimal values.
    """
    
    try:
        response = openai_client.chat.completions.create(
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
    
    return json.loads(json_str.strip())


def generate_csv(data):
    """Generate CSV content from extracted data."""
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Load Number', 'Sample Number', 'Concentration (ng/μL)', 
        'A260/A280', 'A260/A230', 'Quality Assessment'
    ])
    
    # Data rows
    for sample in data['samples']:
        quality = assess_quality(sample['a260_a280'], sample['a260_a230'])
        writer.writerow([
            data['load_number'],
            sample['sample_number'],
            sample['concentration'],
            sample['a260_a280'],
            sample['a260_a230'],
            quality
        ])
    
    return output.getvalue()


def assess_quality(ratio_260_280, ratio_260_230):
    """Simple quality assessment based on ratios."""
    issues = []
    
    if ratio_260_280 < 1.8:
        issues.append("Possible protein contamination")
    elif ratio_260_280 > 2.2:
        issues.append("Possible RNA/degraded sample")
    
    if ratio_260_230 < 1.8:
        issues.append("Possible organic contamination")
    elif ratio_260_230 > 2.4:
        issues.append("Unusually high 260/230")
    
    return "; ".join(issues) if issues else "Good quality"


def send_success_email(to_email, csv_content, data):
    """Send email with CSV attachment."""
    msg = MIMEMultipart()
    msg['Subject'] = f'Nanodrop Results - Load #{data["load_number"]}'
    msg['From'] = 'nanodrop@seminalcapital.net'
    msg['To'] = to_email
    
    # Email body
    body = f"""
    Your Nanodrop data has been processed successfully!
    
    Load Number: {data['load_number']}
    Samples Processed: {len(data['samples'])}
    
    The results are attached as a CSV file.
    
    --
    Nanodrop Processing Service
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach CSV
    attachment = MIMEBase('text', 'csv')
    attachment.set_payload(csv_content)
    encoders.encode_base64(attachment)
    attachment.add_header(
        'Content-Disposition',
        f'attachment; filename=nanodrop_load_{data["load_number"]}.csv'
    )
    msg.attach(attachment)
    
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