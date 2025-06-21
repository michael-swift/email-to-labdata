#!/usr/bin/env python3
"""
Simple monitoring script for Nanodrop processor.
Shows system health, metrics, and recent activity.
"""

import boto3
import json
from datetime import datetime, timedelta
from collections import defaultdict

def main():
    s3 = boto3.client('s3')
    logs = boto3.client('logs', region_name='us-west-2')
    
    print("📊 NANODROP PROCESSOR MONITORING")
    print("=" * 60)
    
    # Check S3 data
    bucket = 'nanodrop-emails-seminalcapital'
    
    # Count recent extractions
    for env in ['dev', 'prod']:
        prefix = f'debug/{env}/' if env == 'dev' else 'debug/'
        
        try:
            response = s3.list_objects_v2(
                Bucket=bucket,
                Prefix=f'{prefix}extractions/',
                MaxKeys=100
            )
            
            objects = response.get('Contents', [])
            
            # Count by day
            by_day = defaultdict(int)
            total_size = 0
            
            for obj in objects:
                day = obj['LastModified'].strftime('%Y-%m-%d')
                by_day[day] += 1
                total_size += obj['Size']
            
            print(f"\n📁 {env.upper()} Environment:")
            print(f"   Total extractions: {len(objects)}")
            print(f"   Total size: {total_size / 1024 / 1024:.1f} MB")
            print(f"   Recent activity:")
            
            for day in sorted(by_day.keys(), reverse=True)[:5]:
                print(f"      {day}: {by_day[day]} extractions")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n✅ Monitoring complete!")

if __name__ == '__main__':
    main()