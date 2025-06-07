#!/usr/bin/env python3
"""
Local test script for Lambda function - much faster debugging!
"""
import json
import os

# Set up environment FIRST
with open('.env') as f:
    for line in f:
        if line.startswith('OPENAI_API_KEY='):
            os.environ['OPENAI_API_KEY'] = line.split('=', 1)[1].strip()

# Patch SES to avoid sending emails during testing
import boto3
from unittest.mock import patch

def mock_send_email(*args, **kwargs):
    print("📧 Mock: Would send email here")
    return {}

def mock_send_raw_email(*args, **kwargs):
    print("📧 Mock: Would send raw email here")  
    return {}

# Patch SES methods
boto3.client('ses').send_email = mock_send_email
boto3.client('ses').send_raw_email = mock_send_raw_email

from lambda_function import lambda_handler

# Mock S3 event (simulates what Lambda gets when email arrives)
mock_event = {
    "Records": [{
        "s3": {
            "bucket": {"name": "nanodrop-emails-seminalcapital"},
            "object": {"key": "incoming/pi9n807iffh6vdiemfdjqag03nu5f469qtpu1ng1"}
        }
    }]
}

# Mock context
class MockContext:
    def __init__(self):
        self.function_name = "test"
        self.memory_limit_in_mb = 512
        self.invoked_function_arn = "test"
        self.aws_request_id = "test"

if __name__ == "__main__":
    print("🧪 Testing Lambda function locally...")
    
    try:
        result = lambda_handler(mock_event, MockContext())
        print(f"✅ Success: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()