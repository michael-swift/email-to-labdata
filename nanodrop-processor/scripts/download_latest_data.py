#!/usr/bin/env python3
"""
Download latest extraction data from S3 for analysis.
Usage: python download_latest_data.py [--latest] [--all] [--env dev|prod]
"""

import boto3
import argparse
import os
import json
from datetime import datetime

class DataDownloader:
    def __init__(self, environment='dev'):
        self.environment = environment
        self.s3_client = boto3.client('s3')
        self.bucket = 'nanodrop-emails-seminalcapital'
        self.prefix = f'debug/{environment}/' if environment == 'dev' else 'debug/'
        
    def list_extractions(self, limit=10):
        """List recent extraction files."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=f'{self.prefix}extractions/',
                MaxKeys=limit * 2  # Get more to filter JSON files
            )
            
            objects = response.get('Contents', [])
            json_files = [obj for obj in objects if obj['Key'].endswith('.json')]
            
            # Sort by last modified (newest first)
            json_files.sort(key=lambda x: x['LastModified'], reverse=True)
            
            return json_files[:limit]
            
        except Exception as e:
            print(f"❌ Error listing extractions: {e}")
            return []
    
    def download_file(self, s3_key, local_filename):
        """Download a file from S3."""
        try:
            self.s3_client.download_file(self.bucket, s3_key, local_filename)
            return True
        except Exception as e:
            print(f"❌ Error downloading {s3_key}: {e}")
            return False
    
    def download_latest(self):
        """Download the latest extraction data."""
        extractions = self.list_extractions(limit=1)
        
        if not extractions:
            print(f"📭 No extraction data found in {self.environment} environment")
            return False
        
        latest = extractions[0]
        s3_key = latest['Key']
        filename = os.path.basename(s3_key)
        
        print(f"📥 Downloading latest extraction: {filename}")
        print(f"   Last modified: {latest['LastModified']}")
        print(f"   Size: {latest['Size']} bytes")
        
        success = self.download_file(s3_key, 'extracted_data.json')
        
        if success:
            print(f"✅ Downloaded to: extracted_data.json")
            
            # Also try to download corresponding CSV
            csv_key = s3_key.replace('extractions/', 'csv/').replace('_raw_data.json', '.csv')
            csv_success = self.download_file(csv_key, 'extracted_data.csv')
            
            if csv_success:
                print(f"✅ Downloaded CSV to: extracted_data.csv")
            
            # Show basic info about the data
            self.show_data_info('extracted_data.json')
            
        return success
    
    def download_all_recent(self, limit=5):
        """Download recent extraction files."""
        extractions = self.list_extractions(limit=limit)
        
        if not extractions:
            print(f"📭 No extraction data found in {self.environment} environment")
            return 0
        
        print(f"📥 Downloading {len(extractions)} recent extractions...")
        
        downloaded = 0
        for i, extraction in enumerate(extractions):
            s3_key = extraction['Key']
            filename = f"extraction_{i+1}_{os.path.basename(s3_key)}"
            
            if self.download_file(s3_key, filename):
                print(f"✅ {i+1}/{len(extractions)}: {filename}")
                downloaded += 1
            else:
                print(f"❌ {i+1}/{len(extractions)}: Failed to download {filename}")
        
        print(f"✅ Downloaded {downloaded}/{len(extractions)} files")
        return downloaded
    
    def show_data_info(self, filename):
        """Show basic information about downloaded data."""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            print(f"\n📊 Data Summary:")
            print(f"   Request ID: {data.get('request_id', 'Unknown')}")
            print(f"   Timestamp: {data.get('timestamp', 'Unknown')}")
            print(f"   User: {data.get('user_email', 'Unknown')}")
            print(f"   Images: {data.get('image_count', 0)}")
            
            extracted_data = data.get('extracted_data', {})
            print(f"   Instrument: {extracted_data.get('instrument', 'Unknown')}")
            print(f"   Confidence: {extracted_data.get('confidence', 'Unknown')}")
            print(f"   Samples: {len(extracted_data.get('samples', []))}")
            
            processing_time = data.get('processing_time_ms', 0)
            if processing_time > 0:
                print(f"   Processing time: {processing_time/1000:.1f} seconds")
                
        except Exception as e:
            print(f"⚠️  Could not read data info: {e}")
    
    def list_recent_files(self, limit=10):
        """List recent files without downloading."""
        extractions = self.list_extractions(limit=limit)
        
        if not extractions:
            print(f"📭 No extraction data found in {self.environment} environment")
            return
        
        print(f"📁 Recent extractions in {self.environment} environment:")
        print("-" * 80)
        
        for i, extraction in enumerate(extractions, 1):
            s3_key = extraction['Key']
            filename = os.path.basename(s3_key)
            timestamp = extraction['LastModified']
            size = extraction['Size']
            
            print(f"{i:2d}. {filename}")
            print(f"    Modified: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Size: {size:,} bytes")
            print()

def main():
    parser = argparse.ArgumentParser(description='Download extraction data for analysis')
    
    # Download options
    parser.add_argument('--latest', action='store_true', 
                        help='Download latest extraction (default)')
    parser.add_argument('--all', action='store_true',
                        help='Download recent extractions')
    parser.add_argument('--list', action='store_true',
                        help='List recent files without downloading')
    
    # Environment
    parser.add_argument('--env', choices=['dev', 'prod'], default='dev',
                        help='Environment to download from (default: dev)')
    
    # Options
    parser.add_argument('--limit', type=int, default=5,
                        help='Number of files to download/list (default: 5)')
    
    args = parser.parse_args()
    
    # Create downloader
    downloader = DataDownloader(environment=args.env)
    
    # Perform action
    if args.list:
        downloader.list_recent_files(args.limit)
    elif args.all:
        downloader.download_all_recent(args.limit)
    else:
        # Default: download latest
        downloader.download_latest()

if __name__ == '__main__':
    main()