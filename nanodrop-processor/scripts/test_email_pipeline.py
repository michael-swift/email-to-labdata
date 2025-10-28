#!/usr/bin/env python3
"""
Comprehensive email testing pipeline for Nanodrop processor.
Tests both production and development environments with various image types.
"""

import boto3
import argparse
import os
import time
import json
from datetime import datetime
from send_test_email import send_test_email

class EmailPipelineTester:
    def __init__(self, environment='dev'):
        self.environment = environment
        self.to_address = 'nanodrop-dev@seminalcapital.net' if environment == 'dev' else 'nanodrop@seminalcapital.net'
        self.from_address = 'test@seminalcapital.net'
        self.logs_client = boto3.client('logs', region_name='us-west-2')
        self.s3_client = boto3.client('s3', region_name='us-west-2')
        self.log_group = f'/aws/lambda/nanodrop-processor{"-dev" if environment == "dev" else ""}'
        
    def find_test_images(self, test_dir='images'):
        """Find all test images in the specified directory."""
        test_images = []
        
        # Look in multiple possible locations
        search_dirs = [test_dir, f'../{test_dir}', 'tests/fixtures/test_images', '../tests/fixtures/test_images']
        
        for dir_path in search_dirs:
            if os.path.exists(dir_path):
                for file in os.listdir(dir_path):
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        full_path = os.path.join(dir_path, file)
                        test_images.append(full_path)
        
        return test_images
    
    def send_test_batch(self, images, delay_between=5):
        """Send a batch of test emails with different images."""
        results = []
        
        for i, image_path in enumerate(images, 1):
            print(f"\n{'='*60}")
            print(f"Test {i}/{len(images)}: {os.path.basename(image_path)}")
            print(f"{'='*60}")
            
            subject = f"Test {i}/{len(images)} - {os.path.basename(image_path)} - {datetime.now().strftime('%H:%M:%S')}"
            
            success = send_test_email(
                to_address=self.to_address,
                from_address=self.from_address,
                subject=subject,
                body=f"Automated test email {i} of {len(images)}\\n\\nImage: {os.path.basename(image_path)}",
                attachment_path=image_path
            )
            
            results.append({
                'image': os.path.basename(image_path),
                'sent': success,
                'timestamp': datetime.now().isoformat()
            })
            
            if i < len(images):
                print(f"⏱️  Waiting {delay_between} seconds before next email...")
                time.sleep(delay_between)
        
        return results
    
    def check_logs_for_errors(self, start_time, duration_seconds=120):
        """Check CloudWatch logs for errors after sending emails."""
        print(f"\n🔍 Checking logs for errors...")
        
        end_time = start_time + (duration_seconds * 1000)
        
        try:
            response = self.logs_client.filter_log_events(
                logGroupName=self.log_group,
                startTime=start_time,
                endTime=end_time,
                filterPattern='ERROR'
            )
            
            errors = response.get('events', [])
            
            if errors:
                print(f"❌ Found {len(errors)} errors in logs:")
                for error in errors[:5]:  # Show first 5 errors
                    print(f"   - {error['message'].strip()}")
            else:
                print("✅ No errors found in logs")
                
            return errors
            
        except Exception as e:
            print(f"⚠️  Could not check logs: {e}")
            return []
    
    def run_full_test(self, test_images=None):
        """Run a full test suite."""
        print(f"\n🧪 NANODROP EMAIL PIPELINE TEST")
        print(f"📍 Environment: {self.environment.upper()}")
        print(f"📧 Target: {self.to_address}")
        print(f"📊 Log Group: {self.log_group}")
        
        # Find test images if not provided
        if not test_images:
            test_images = self.find_test_images()
            if not test_images:
                print("❌ No test images found!")
                return
        
        print(f"\n📎 Found {len(test_images)} test images:")
        for img in test_images:
            print(f"   - {os.path.basename(img)}")
        
        # Confirm before sending
        if self.environment == 'prod':
            print(f"\n⚠️  WARNING: Sending to PRODUCTION!")
            response = input("Continue? (y/N): ")
            if response.lower() != 'y':
                return
        
        # Record start time
        start_time = int(time.time() * 1000)
        
        # Send test emails
        print(f"\n📤 Sending {len(test_images)} test emails...")
        results = self.send_test_batch(test_images)
        
        # Summary
        print(f"\n📊 TEST SUMMARY")
        print(f"{'='*60}")
        successful = sum(1 for r in results if r['sent'])
        print(f"✅ Successful: {successful}/{len(results)}")
        
        if successful < len(results):
            print(f"❌ Failed: {len(results) - successful}/{len(results)}")
            for r in results:
                if not r['sent']:
                    print(f"   - {r['image']}")
        
        # Wait for processing
        print(f"\n⏱️  Waiting 30 seconds for Lambda processing...")
        time.sleep(30)
        
        # Check logs
        self.check_logs_for_errors(start_time)
        
        print(f"\n✅ Test pipeline complete!")
        print(f"📊 Check full logs at:")
        print(f"   https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logGroup:group={self.log_group}")

def main():
    parser = argparse.ArgumentParser(description='Test Nanodrop email processing pipeline')
    
    # Environment selection
    parser.add_argument('--env', choices=['dev', 'prod'], default='dev',
                        help='Environment to test (default: dev)')
    
    # Test options
    parser.add_argument('--images', nargs='+', help='Specific image files to test')
    parser.add_argument('--quick', action='store_true', 
                        help='Quick test with just one image')
    parser.add_argument('--delay', type=int, default=5,
                        help='Delay between emails in seconds (default: 5)')
    
    args = parser.parse_args()
    
    # Create tester
    tester = EmailPipelineTester(environment=args.env)
    
    # Determine which images to test
    if args.images:
        test_images = args.images
    elif args.quick:
        # Just test with first available image
        all_images = tester.find_test_images()
        test_images = all_images[:1] if all_images else []
    else:
        test_images = None  # Test all found images
    
    # Run tests
    tester.run_full_test(test_images)

if __name__ == '__main__':
    main()