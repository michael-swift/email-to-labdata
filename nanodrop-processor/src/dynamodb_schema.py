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
    
    def __init__(self):
        """Initialize DynamoDB client and table names."""
        self.dynamodb = boto3.resource('dynamodb')
        self.requests_table_name = 'nanodrop-requests'
        
        # Try to get the table, create if it doesn't exist
        try:
            self.requests_table = self.dynamodb.Table(self.requests_table_name)
            # Test if table exists by describing it
            self.requests_table.table_status
        except Exception:
            # Table doesn't exist, but don't fail - just log errors
            self.requests_table = None
    
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
            return True
            
        except Exception:
            # Don't fail the main request if DynamoDB fails
            return False
    
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