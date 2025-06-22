#!/usr/bin/env python3
"""
Check recent Lambda invocations and DynamoDB logs to debug missing responses.
"""

import boto3
import json
from datetime import datetime, timedelta, timezone
import sys
import os

def check_cloudwatch_logs():
    """Check CloudWatch logs for recent Lambda invocations."""
    print("Checking CloudWatch logs...")
    
    client = boto3.client('logs')
    
    # Look for Lambda log groups
    try:
        log_groups = client.describe_log_groups(
            logGroupNamePrefix='/aws/lambda/nanodrop'
        )
        
        if not log_groups['logGroups']:
            print("No Lambda log groups found with prefix '/aws/lambda/nanodrop'")
            return
        
        for log_group in log_groups['logGroups']:
            group_name = log_group['logGroupName']
            print(f"\nChecking log group: {group_name}")
            
            # Get recent log streams
            streams = client.describe_log_streams(
                logGroupName=group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=5
            )
            
            for stream in streams['logStreams']:
                stream_name = stream['logStreamName']
                last_event = datetime.fromtimestamp(stream['lastEventTime'] / 1000, tz=timezone.utc)
                
                if last_event > datetime.now(timezone.utc) - timedelta(days=7):
                    print(f"  Recent stream: {stream_name} (last event: {last_event})")
                    
                    # Get recent events
                    events = client.get_log_events(
                        logGroupName=group_name,
                        logStreamName=stream_name,
                        startTime=int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)
                    )
                    
                    for event in events['events'][-10:]:  # Last 10 events
                        timestamp = datetime.fromtimestamp(event['timestamp'] / 1000, tz=timezone.utc)
                        message = event['message']
                        print(f"    {timestamp}: {message[:100]}...")
    
    except Exception as e:
        print(f"Error checking CloudWatch logs: {e}")

def check_dynamodb_requests():
    """Check DynamoDB for recent requests."""
    print("\nChecking DynamoDB for recent requests...")
    
    dynamodb = boto3.resource('dynamodb')
    
    # Try different table name patterns
    table_names = ['nanodrop-requests', 'dev-nanodrop-requests', 'prod-nanodrop-requests']
    
    for table_name in table_names:
        try:
            table = dynamodb.Table(table_name)
            table.table_status  # Test if table exists
            
            print(f"Found table: {table_name}")
            
            # Scan for recent requests (last 7 days)
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('timestamp').gte(
                    (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                ),
                Limit=20
            )
            
            items = response.get('Items', [])
            print(f"Found {len(items)} recent requests")
            
            for item in sorted(items, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]:
                timestamp = item.get('timestamp', 'Unknown')
                user_email = item.get('user_email', 'Unknown')
                success = item.get('success', 'Unknown')
                error = item.get('error_message', 'No error')
                samples = item.get('samples_extracted', 0)
                
                print(f"  {timestamp}: {user_email} - Success: {success}, Samples: {samples}")
                if not success and error != 'No error':
                    print(f"    Error: {error}")
            
            return  # Found a table, stop looking
            
        except Exception as e:
            print(f"Table {table_name} not found or accessible: {e}")
    
    print("No DynamoDB tables found")

def check_s3_emails():
    """Check S3 for recent email objects."""
    print("\nChecking S3 for recent emails...")
    
    s3 = boto3.client('s3')
    
    # Try to find S3 buckets with email data
    buckets = s3.list_buckets()
    
    for bucket in buckets['Buckets']:
        bucket_name = bucket['Name']
        
        if 'nanodrop' in bucket_name.lower() or 'email' in bucket_name.lower():
            print(f"Checking bucket: {bucket_name}")
            
            try:
                # Look for recent objects
                response = s3.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix='incoming/',
                    MaxKeys=20
                )
                
                if 'Contents' in response:
                    recent_objects = sorted(
                        response['Contents'], 
                        key=lambda x: x['LastModified'], 
                        reverse=True
                    )[:10]
                    
                    for obj in recent_objects:
                        if obj['LastModified'] > datetime.now(timezone.utc) - timedelta(days=7):
                            print(f"  Recent email: {obj['Key']} ({obj['LastModified']})")
                
            except Exception as e:
                print(f"Error checking bucket {bucket_name}: {e}")

def check_lambda_function_config():
    """Check Lambda function configuration."""
    print("\nChecking Lambda function configuration...")
    
    lambda_client = boto3.client('lambda')
    
    try:
        functions = lambda_client.list_functions()
        
        nanodrop_functions = [f for f in functions['Functions'] if 'nanodrop' in f['FunctionName'].lower()]
        
        for func in nanodrop_functions:
            func_name = func['FunctionName']
            print(f"\nFunction: {func_name}")
            print(f"  Runtime: {func['Runtime']}")
            print(f"  Last Modified: {func['LastModified']}")
            print(f"  State: {func.get('State', 'Unknown')}")
            
            # Get function configuration
            config = lambda_client.get_function_configuration(FunctionName=func_name)
            
            # Check environment variables
            env_vars = config.get('Environment', {}).get('Variables', {})
            print(f"  Environment variables:")
            for key, value in env_vars.items():
                if 'key' in key.lower() or 'secret' in key.lower():
                    print(f"    {key}: [REDACTED]")
                else:
                    print(f"    {key}: {value}")
    
    except Exception as e:
        print(f"Error checking Lambda functions: {e}")

def main():
    """Main investigation function."""
    print("Investigating missing nanodrop response")
    print("=" * 50)
    
    # Check AWS credentials
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"AWS Account: {identity['Account']}")
        print(f"AWS User/Role: {identity['Arn']}")
    except Exception as e:
        print(f"AWS credentials issue: {e}")
        return
    
    # Run checks
    check_lambda_function_config()
    check_s3_emails()
    check_dynamodb_requests()
    check_cloudwatch_logs()
    
    print("\n" + "=" * 50)
    print("Investigation complete. Check output above for issues.")

if __name__ == "__main__":
    main()