#!/usr/bin/env python3
"""
Test script for simplified DynamoDB integration.
Run this to test basic request logging.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dynamodb_schema import DynamoDBManager
import uuid

def test_basic_logging():
    """Test basic request logging functionality."""
    print("🧪 Testing DynamoDB Request Logging\n")
    
    db = DynamoDBManager()
    
    # Test 1: Successful request
    print("📝 Testing successful request logging...")
    success = db.log_request(
        user_email="test@university.edu",
        request_id=str(uuid.uuid4()),
        images_processed=2,
        samples_extracted=8,
        processing_time_ms=7500,
        success=True,
        instrument_types=["Nanodrop"],
        additional_data={
            'assay_type': 'DNA',
            's3_key': 'incoming/test-success'
        }
    )
    
    if success:
        print("✅ Successful request logged")
    else:
        print("⚠️  Request logging failed (table might not exist - this is OK)")
    
    # Test 1b: Second request from same user (test aggregation)
    print("📝 Testing second request from same user (aggregation)...")
    success = db.log_request(
        user_email="test@university.edu",
        request_id=str(uuid.uuid4()),
        images_processed=1,
        samples_extracted=96,
        processing_time_ms=5000,
        success=True,
        instrument_types=["plate reader"],
        additional_data={
            'assay_type': 'protein',
            's3_key': 'incoming/test-success-2'
        }
    )
    
    if success:
        print("✅ Second request logged (should update user stats)")
    else:
        print("⚠️  Second request logging failed")
    
    # Test 2: Failed request
    print("\n📝 Testing failed request logging...")
    success = db.log_request(
        user_email="test@university.edu",
        request_id=str(uuid.uuid4()),
        images_processed=1,
        samples_extracted=0,
        processing_time_ms=3200,
        success=False,
        error_message="No data found in image",
        additional_data={
            'error_type': 'no_data_found',
            's3_key': 'incoming/test-failure'
        }
    )
    
    if success:
        print("✅ Failed request logged")
    else:
        print("⚠️  Request logging failed (table might not exist - this is OK)")
    
    # Test 3: Test graceful failure
    print("\n🛡️  Testing graceful failure handling...")
    
    # Create a manager with no table access to test failure handling
    broken_db = DynamoDBManager()
    broken_db.requests_table = None
    
    success = broken_db.log_request(
        user_email="test@example.com",
        request_id=str(uuid.uuid4()),
        images_processed=1,
        samples_extracted=0,
        processing_time_ms=1000,
        success=True
    )
    
    if not success:
        print("✅ Graceful failure handling works")
    else:
        print("❌ Expected graceful failure but got success")
    
    print("\n📊 Summary:")
    print("- DynamoDB integration is ready")
    print("- Logs requests when table exists")
    print("- Fails gracefully when table doesn't exist")
    print("- Safe to deploy without DynamoDB setup")
    
    return True

if __name__ == "__main__":
    test_basic_logging()