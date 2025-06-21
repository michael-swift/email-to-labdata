#!/usr/bin/env python3
"""
Send test emails to the Nanodrop processor for testing.
Usage: python send_test_email.py [--prod|--dev] [--image path/to/image.png]
"""

import boto3
import argparse
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
from datetime import datetime

def send_test_email(to_address, from_address, subject, body, attachment_path=None):
    """Send a test email using AWS SES."""
    
    # Create SES client
    ses = boto3.client('ses', region_name='us-west-2')
    
    # Create message
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = from_address
    msg['To'] = to_address
    
    # Add body
    body_part = MIMEText(body, 'plain')
    msg.attach(body_part)
    
    # Add attachment if provided
    if attachment_path and os.path.exists(attachment_path):
        # Guess the content type
        ctype, encoding = mimetypes.guess_type(attachment_path)
        if ctype is None:
            ctype = 'application/octet-stream'
        
        maintype, subtype = ctype.split('/', 1)
        
        # Read the attachment
        with open(attachment_path, 'rb') as f:
            if maintype == 'image':
                attachment = MIMEImage(f.read(), _subtype=subtype)
            else:
                attachment = MIMEBase(maintype, subtype)
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
        
        # Add header
        attachment.add_header(
            'Content-Disposition',
            'attachment',
            filename=os.path.basename(attachment_path)
        )
        msg.attach(attachment)
        print(f"✅ Attached: {attachment_path}")
    
    # Send the email
    try:
        response = ses.send_raw_email(
            Source=from_address,
            Destinations=[to_address],
            RawMessage={'Data': msg.as_string()}
        )
        print(f"✅ Email sent successfully!")
        print(f"   Message ID: {response['MessageId']}")
        print(f"   To: {to_address}")
        print(f"   From: {from_address}")
        if attachment_path:
            print(f"   Attachment: {os.path.basename(attachment_path)}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Send test emails to Nanodrop processor')
    
    # Environment selection
    env_group = parser.add_mutually_exclusive_group()
    env_group.add_argument('--prod', action='store_true', help='Send to production (nanodrop@)')
    env_group.add_argument('--dev', action='store_true', help='Send to development (nanodrop-dev@)')
    
    # Email options
    parser.add_argument('--from', dest='from_email', default='test@seminalcapital.net',
                        help='From email address (default: test@seminalcapital.net)')
    parser.add_argument('--subject', default=f'Test email - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                        help='Email subject')
    parser.add_argument('--body', default='This is a test email with an attached lab instrument image.',
                        help='Email body text')
    
    # Attachment
    parser.add_argument('--image', dest='image_path', 
                        help='Path to image file to attach')
    parser.add_argument('--attach', dest='attachment_path',
                        help='Path to any file to attach (alias for --image)')
    
    args = parser.parse_args()
    
    # Determine recipient
    if args.dev:
        to_address = 'nanodrop-dev@seminalcapital.net'
        print("🧪 Sending to DEVELOPMENT environment")
    else:
        to_address = 'nanodrop@seminalcapital.net'
        print("🚀 Sending to PRODUCTION environment")
        if not args.prod:
            print("   (Use --dev flag to send to development)")
    
    # Get attachment path
    attachment_path = args.image_path or args.attachment_path
    
    # If no attachment specified, try to find a test image
    if not attachment_path:
        # Look for test images in common locations
        test_locations = [
            'tests/fixtures/test_images/plate_reader_96well.jpg',
            'tests/fixtures/test_images/nanodrop_standard.jpg',
            'tests/fixtures/test_images/uv_vis_history.jpg',
            'tests/fixtures/test_images/luminescence_plate.jpg',
            'images/test_plate_reader.png',
            'images/nanodrop_screenshot.png',
        ]
        
        for loc in test_locations:
            if os.path.exists(loc):
                attachment_path = loc
                print(f"📎 Auto-detected test image: {loc}")
                break
        
        if not attachment_path:
            print("⚠️  No image attachment specified and no test images found")
            print("   Use --image path/to/image.png to attach an image")
            response = input("   Continue without attachment? (y/N): ")
            if response.lower() != 'y':
                return
    
    # Send the email
    print(f"\n📧 Sending email...")
    success = send_test_email(
        to_address=to_address,
        from_address=args.from_email,
        subject=args.subject,
        body=args.body,
        attachment_path=attachment_path
    )
    
    if success:
        print(f"\n✅ Test email sent to {to_address}")
        print(f"   Check CloudWatch logs in ~30-60 seconds")
        if args.dev:
            print(f"   Logs: https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logGroup:group=/aws/lambda/nanodrop-processor-dev")
        else:
            print(f"   Logs: https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logGroup:group=/aws/lambda/nanodrop-processor")

if __name__ == '__main__':
    main()