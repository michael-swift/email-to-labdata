#!/usr/bin/env python3
"""
Smart log checking for Nanodrop processor.
Usage: python check_logs.py [--dev|--prod] [--recent|--last-run|--errors]
"""

import boto3
import argparse
import json
from datetime import datetime, timedelta
import time

class LogChecker:
    def __init__(self, environment='dev'):
        self.environment = environment
        self.logs_client = boto3.client('logs', region_name='us-west-2')
        self.log_group = f'/aws/lambda/nanodrop-processor{"-dev" if environment == "dev" else ""}'
        
    def get_recent_logs(self, minutes=30):
        """Get recent logs from the specified time range."""
        end_time = int(time.time() * 1000)
        start_time = end_time - (minutes * 60 * 1000)
        
        try:
            response = self.logs_client.filter_log_events(
                logGroupName=self.log_group,
                startTime=start_time,
                endTime=end_time
            )
            return response.get('events', [])
        except Exception as e:
            print(f"❌ Error fetching logs: {e}")
            return []
    
    def get_last_run_logs(self):
        """Get logs from the most recent Lambda execution."""
        # Look for recent START events to identify the last run
        recent_events = self.get_recent_logs(minutes=60)
        
        # Find the most recent START event
        start_events = [e for e in recent_events if 'START RequestId:' in e['message']]
        if not start_events:
            print("❌ No recent Lambda executions found")
            return []
        
        # Get the request ID from the most recent START
        last_start = start_events[-1]
        request_id = last_start['message'].split('RequestId: ')[1].split(' ')[0]
        
        # Filter events for this specific request
        run_events = [e for e in recent_events if request_id in e['message']]
        return run_events, request_id
    
    def get_error_logs(self, hours=24):
        """Get error logs from the specified time range."""
        end_time = int(time.time() * 1000)
        start_time = end_time - (hours * 60 * 60 * 1000)
        
        try:
            response = self.logs_client.filter_log_events(
                logGroupName=self.log_group,
                startTime=start_time,
                endTime=end_time,
                filterPattern='ERROR'
            )
            return response.get('events', [])
        except Exception as e:
            print(f"❌ Error fetching error logs: {e}")
            return []
    
    def analyze_last_run(self):
        """Analyze the last Lambda run and show key metrics."""
        result = self.get_last_run_logs()
        if not result:
            return
        
        events, request_id = result
        
        print(f"🔍 LAST RUN ANALYSIS ({self.environment.upper()})")
        print(f"{'='*60}")
        print(f"Request ID: {request_id}")
        
        # Extract key information
        success = False
        processing_time = None
        samples_extracted = None
        instrument_type = None
        errors = []
        
        for event in events:
            message = event['message']
            
            # Parse structured logs
            if message.strip().startswith('{'):
                try:
                    log_data = json.loads(message.strip())
                    if log_data.get('message') == 'Request completed':
                        success = log_data.get('success', False)
                        processing_time = log_data.get('total_duration_ms')
                        samples_extracted = log_data.get('samples_extracted')
                    elif 'instrument' in log_data.get('message', ''):
                        instrument_type = log_data.get('message', '').split(':')[1].strip() if ':' in log_data.get('message', '') else None
                except:
                    pass
            
            # Look for errors
            if 'ERROR' in message or 'error' in message.lower():
                errors.append(message.strip())
        
        # Show results
        print(f"Status: {'✅ Success' if success else '❌ Failed'}")
        if processing_time:
            print(f"Processing Time: {processing_time/1000:.1f} seconds")
        if samples_extracted:
            print(f"Samples Extracted: {samples_extracted}")
        if instrument_type:
            print(f"Instrument: {instrument_type}")
        
        if errors:
            print(f"\n⚠️  Errors ({len(errors)}):")
            for error in errors[:3]:  # Show first 3 errors
                print(f"  - {error}")
            if len(errors) > 3:
                print(f"  ... and {len(errors) - 3} more errors")
        else:
            print(f"✅ No errors detected")
        
        print(f"\n📊 Total log events: {len(events)}")
        
        # Show processing timeline
        if len(events) > 3:
            print(f"\n⏱️  Processing Timeline:")
            start_time = events[0]['timestamp']
            for event in events[:5]:  # Show first 5 events
                relative_time = (event['timestamp'] - start_time) / 1000
                message = event['message'].strip()
                if len(message) > 60:
                    message = message[:60] + "..."
                print(f"  +{relative_time:5.1f}s: {message}")
    
    def show_recent_logs(self, minutes=30):
        """Show recent logs with basic formatting."""
        events = self.get_recent_logs(minutes)
        
        if not events:
            print(f"📭 No logs found in the last {minutes} minutes")
            return
        
        print(f"📋 Recent logs ({len(events)} events, last {minutes} minutes):")
        print("-" * 60)
        
        for event in events[-10:]:  # Show last 10 events
            timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
            message = event['message'].strip()
            
            # Colorize based on content
            if 'ERROR' in message:
                prefix = "❌"
            elif 'success' in message.lower() or 'completed' in message.lower():
                prefix = "✅"
            elif 'Lambda invoked' in message:
                prefix = "🚀"
            else:
                prefix = "📝"
            
            print(f"{prefix} {timestamp.strftime('%H:%M:%S')} {message}")
    
    def show_errors(self, hours=24):
        """Show recent errors."""
        errors = self.get_error_logs(hours)
        
        if not errors:
            print(f"✅ No errors found in the last {hours} hours")
            return
        
        print(f"❌ Recent errors ({len(errors)} found, last {hours} hours):")
        print("-" * 60)
        
        for error in errors[-5:]:  # Show last 5 errors
            timestamp = datetime.fromtimestamp(error['timestamp'] / 1000)
            message = error['message'].strip()
            print(f"🔥 {timestamp.strftime('%m/%d %H:%M:%S')} {message}")

def main():
    parser = argparse.ArgumentParser(description='Check Nanodrop processor logs')
    
    # Environment
    env_group = parser.add_mutually_exclusive_group()
    env_group.add_argument('--dev', action='store_true', help='Check development logs')
    env_group.add_argument('--prod', action='store_true', help='Check production logs')
    
    # Log type
    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument('--recent', action='store_true', help='Show recent logs (default)')
    type_group.add_argument('--last-run', action='store_true', help='Analyze last Lambda run')
    type_group.add_argument('--errors', action='store_true', help='Show recent errors only')
    
    # Options
    parser.add_argument('--minutes', type=int, default=30, help='Minutes of logs to show (default: 30)')
    parser.add_argument('--hours', type=int, default=24, help='Hours of error logs to show (default: 24)')
    
    args = parser.parse_args()
    
    # Determine environment
    environment = 'dev' if args.dev else 'prod'
    
    # Create checker
    checker = LogChecker(environment)
    
    # Determine action
    if args.last_run:
        checker.analyze_last_run()
    elif args.errors:
        checker.show_errors(args.hours)
    else:
        checker.show_recent_logs(args.minutes)

if __name__ == '__main__':
    main()