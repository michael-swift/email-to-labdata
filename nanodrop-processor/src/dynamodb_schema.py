"""
DynamoDB schema and operations for nanodrop processor analytics.
"""

import boto3
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid

class DynamoDBManager:
    """Manages DynamoDB operations for request logging and analytics."""
    
    def __init__(self, table_prefix=''):
        """Initialize DynamoDB client and table names."""
        self.dynamodb = boto3.resource('dynamodb')
        self.table_prefix = table_prefix
        self.requests_table_name = f'{table_prefix}nanodrop-requests'
        self.user_stats_table_name = f'{table_prefix}nanodrop-user-stats'
        
        # Initialize requests table
        try:
            self.requests_table = self.dynamodb.Table(self.requests_table_name)
            # Test if table exists by describing it
            self.requests_table.table_status
        except Exception:
            # Table doesn't exist, but don't fail - just log errors
            self.requests_table = None
        
        # Initialize user stats table
        try:
            self.user_stats_table = self.dynamodb.Table(self.user_stats_table_name)
            # Test if table exists by describing it
            self.user_stats_table.table_status
        except Exception:
            # Table doesn't exist, but don't fail - just log errors
            self.user_stats_table = None
    
    def log_request(
        self,
        user_email: str,
        request_id: str,
        images_processed: int,
        samples_extracted: int,
        processing_time_ms: int,
        success: bool,
        error_message: Optional[str] = None,
        instrument_types: Optional[List[str]] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log a request to DynamoDB for analytics.
        
        Returns True if successful, False if failed (but doesn't raise).
        """
        if not self.requests_table:
            # Table not available, silently skip
            return False
        
        try:
            item = {
                'request_id': request_id,
                'user_email': user_email,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'images_processed': images_processed,
                'samples_extracted': samples_extracted,
                'processing_time_ms': processing_time_ms,
                'success': success,
                'date_partition': datetime.now(timezone.utc).strftime('%Y-%m-%d')
            }
            
            if error_message:
                item['error_message'] = error_message
            
            if instrument_types:
                item['instrument_types'] = instrument_types
            
            if additional_data:
                item['additional_data'] = additional_data
            
            self.requests_table.put_item(Item=item)
            
            # Update user stats (aggregation)
            self._update_user_stats(user_email, success, processing_time_ms, samples_extracted, instrument_types)
            
            return True
            
        except Exception:
            # Don't fail the main request if DynamoDB fails
            return False
    
    def _update_user_stats(self, user_email: str, success: bool, processing_time_ms: int, 
                          samples_extracted: int, instrument_types: Optional[List[str]] = None):
        """Update aggregated user statistics."""
        if not self.user_stats_table:
            return
        
        try:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            # Try to get existing stats for today
            response = self.user_stats_table.get_item(
                Key={
                    'user_email': user_email,
                    'date': today
                }
            )
            
            if 'Item' in response:
                # Update existing stats
                item = response['Item']
                item['total_requests'] = item.get('total_requests', 0) + 1
                item['successful_requests'] = item.get('successful_requests', 0) + (1 if success else 0)
                item['failed_requests'] = item.get('failed_requests', 0) + (0 if success else 1)
                item['total_samples'] = item.get('total_samples', 0) + samples_extracted
                item['total_processing_time_ms'] = item.get('total_processing_time_ms', 0) + processing_time_ms
                
                # Update instrument types
                existing_instruments = item.get('instrument_types_used', [])
                if instrument_types:
                    for instrument in instrument_types:
                        if instrument not in existing_instruments:
                            existing_instruments.append(instrument)
                item['instrument_types_used'] = existing_instruments
                
                # Calculate averages
                item['avg_processing_time_ms'] = item['total_processing_time_ms'] // item['total_requests']
                item['success_rate'] = item['successful_requests'] / item['total_requests']
                
            else:
                # Create new stats entry
                item = {
                    'user_email': user_email,
                    'date': today,
                    'total_requests': 1,
                    'successful_requests': 1 if success else 0,
                    'failed_requests': 0 if success else 1,
                    'total_samples': samples_extracted,
                    'total_processing_time_ms': processing_time_ms,
                    'avg_processing_time_ms': processing_time_ms,
                    'success_rate': 1.0 if success else 0.0,
                    'instrument_types_used': instrument_types or [],
                    'first_request_timestamp': datetime.now(timezone.utc).isoformat(),
                    'last_request_timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # Always update the last request timestamp
            item['last_request_timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # Save updated stats
            self.user_stats_table.put_item(Item=item)
            
        except Exception:
            # Don't fail if user stats update fails - fail silently
            pass
    
    def get_user_analytics(self, user_email: str, days: int = 30) -> Optional[Dict]:
        """Get analytics for a specific user."""
        if not self.requests_table:
            return None
        
        try:
            # This would require a GSI on user_email + timestamp
            # For now, just return None to indicate feature not available
            return None
        except Exception:
            return None
    
    def get_system_analytics(self, days: int = 7) -> Optional[Dict]:
        """Get system-wide analytics."""
        if not self.requests_table:
            return None
        
        try:
            # This would require scanning/querying by date
            # For now, just return None to indicate feature not available
            return None
        except Exception:
            return None