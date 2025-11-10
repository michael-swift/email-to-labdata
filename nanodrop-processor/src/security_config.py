#!/usr/bin/env python3
"""
Improved security configuration for open Nanodrop processor service.
Balances security with usability for legitimate users.
"""

import os
import hashlib
import time
from typing import List, Dict, Optional
import boto3
from datetime import datetime, timedelta
from PIL import Image
import io

class SecurityConfig:
    """Security configuration optimized for open service."""
    
    # Remove domain validation - allow any sender
    VALIDATE_EMAIL_DOMAINS = False
    
    # Rate limiting (conservative for research use)
    RATE_LIMIT_PER_HOUR = 3
    RATE_LIMIT_PER_DAY = 10
    BURST_LIMIT = 2  # Max 2 emails in 5 minutes
    
    # Input validation limits
    MAX_ATTACHMENT_SIZE_MB = 20
    MAX_ATTACHMENTS_PER_EMAIL = 5
    MAX_EMAIL_SIZE_MB = 25
    
    # Cost protection
    DAILY_OPENAI_LIMIT_USD = 50.00
    DAILY_TOKEN_LIMIT = 1000000  # ~$20-30 for GPT-4
    
    # Allowed file types
    ALLOWED_MIME_TYPES = [
        'image/jpeg',
        'image/png', 
        'image/jpg'
    ]
    
    # Reputable top-level domains for research use
    ALLOWED_TLDS = [
        '.com', '.org', '.edu', '.gov', '.net', '.ai', '.io',
        '.ac.uk', '.ac.jp', '.ac.kr', '.ac.in',  # Academic domains
        '.de', '.fr', '.it', '.nl', '.ch', '.se', '.dk', '.no',  # European research
        '.ca', '.au', '.nz', '.jp', '.kr', '.sg', '.hk',  # International
        '.mil', '.int'  # Government and international orgs
    ]
    
    # Blocked patterns for obvious abuse
    BLOCKED_EMAIL_PATTERNS = [
        '@tempmail.', '@guerrillamail.', '@10minutemail.',
        '@mailinator.', '@yopmail.', '@throwaway.',
        '@spam.', '@fake.', '@test.', '@example.',
        # Suspicious TLDs
        '.tk', '.ml', '.ga', '.cf'  # Free domains often used for spam
    ]
    
    def __init__(self, table_prefix: str = ''):
        self.dynamodb = boto3.resource('dynamodb')
        self.cloudwatch = boto3.client('cloudwatch')
        self.table_name = f'{table_prefix}nanodrop-rate-limits'
        self._ensure_rate_limit_table()

    def _ensure_rate_limit_table(self):
        """Ensure DynamoDB table exists for rate limiting."""
        try:
            table = self.dynamodb.Table(self.table_name)
            table.load()
            self.rate_table = table
            return
        except Exception:
            pass  # Attempt to create below

        try:
            self._create_rate_limit_table()
            table = self.dynamodb.Table(self.table_name)
            table.load()
            self.rate_table = table
        except Exception as e:
            self.rate_table = None
            print(
                f"Warning: Could not initialize rate limiting table {self.table_name}: {e}."
                " Rate limiting disabled."
            )

    def _create_rate_limit_table(self):
        """Create DynamoDB table for rate limiting."""
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {
                    'AttributeName': 'email_hash',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'email_hash',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Wait for table to be created
        table.meta.client.get_waiter('table_exists').wait(TableName=self.table_name)

        # Enable TTL after table creation (for compatibility)
        try:
            table.meta.client.update_time_to_live(
                TableName=self.table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'expiration_time',
                    'Enabled': True
                }
            )
        except Exception as e:
            print(f"Warning: Could not enable TTL: {e}")

        self.rate_table = table
    
    def validate_email_sender(self, from_email: str) -> Dict[str, any]:
        """Enhanced email validation - check for reputable domains."""
        result = {'valid': True, 'reason': ''}
        
        if not from_email:
            result['valid'] = False
            result['reason'] = 'No sender email provided'
            return result
        
        # Basic format check
        if '@' not in from_email or '.' not in from_email.split('@')[-1]:
            result['valid'] = False
            result['reason'] = 'Invalid email format'
            return result
        
        email_lower = from_email.lower()
        domain = email_lower.split('@')[-1]
        
        # Check for blocked patterns
        for pattern in self.BLOCKED_EMAIL_PATTERNS:
            if pattern in email_lower:
                result['valid'] = False
                result['reason'] = 'Email from blocked provider (temporary/spam domain)'
                return result
        
        # Check for reputable TLD
        has_reputable_tld = any(domain.endswith(tld) for tld in self.ALLOWED_TLDS)
        if not has_reputable_tld:
            result['valid'] = False
            result['reason'] = f'Email domain "{domain}" not from a recognized institution or organization'
            return result
        
        return result
    
    def check_rate_limit(self, from_email: str) -> Dict[str, any]:
        """Enhanced rate limiting with burst protection."""
        # If rate limiting table is not available, log warning and allow requests
        if self.rate_table is None:
            print(f"WARNING: Rate limiting disabled - table {self.table_name} not available")
            # Log metric to CloudWatch
            try:
                self.cloudwatch.put_metric_data(
                    Namespace='NanodropProcessor',
                    MetricData=[{
                        'MetricName': 'RateLimitingDisabled',
                        'Value': 1,
                        'Unit': 'Count'
                    }]
                )
            except Exception:
                pass
            return {'allowed': True, 'reason': 'Rate limiting unavailable', 'retry_after': 0}
        
        email_hash = hashlib.sha256(from_email.lower().encode()).hexdigest()
        current_time = int(time.time())
        
        result = {'allowed': True, 'reason': '', 'retry_after': 0}
        
        try:
            response = self.rate_table.get_item(
                Key={'email_hash': email_hash}
            )
            
            if 'Item' in response:
                item = response['Item']
                
                # Check hourly limit
                hour_start = current_time - (current_time % 3600)
                hourly_count = item.get('hourly_count', 0) if item.get('hour_start') == hour_start else 0
                
                if hourly_count >= self.RATE_LIMIT_PER_HOUR:
                    result['allowed'] = False
                    result['reason'] = f'Hourly limit exceeded ({self.RATE_LIMIT_PER_HOUR}/hour)'
                    result['retry_after'] = 3600 - (current_time % 3600)
                    return result
                
                # Check daily limit
                day_start = current_time - (current_time % 86400)
                daily_count = item.get('daily_count', 0) if item.get('day_start') == day_start else 0
                
                if daily_count >= self.RATE_LIMIT_PER_DAY:
                    result['allowed'] = False
                    result['reason'] = f'Daily limit exceeded ({self.RATE_LIMIT_PER_DAY}/day)'
                    result['retry_after'] = 86400 - (current_time % 86400)
                    return result
                
                # Check burst limit (3 in 5 minutes)
                recent_requests = item.get('recent_requests', [])
                recent_requests = [ts for ts in recent_requests if current_time - ts < 300]  # 5 minutes
                
                if len(recent_requests) >= self.BURST_LIMIT:
                    result['allowed'] = False
                    result['reason'] = f'Burst limit exceeded ({self.BURST_LIMIT} in 5 minutes)'
                    result['retry_after'] = 300 - (current_time - min(recent_requests))
                    return result
                
                # Update counters
                recent_requests.append(current_time)
                self.rate_table.update_item(
                    Key={'email_hash': email_hash},
                    UpdateExpression='''SET 
                        hourly_count = if_not_exists(hourly_count, :zero) + :inc,
                        daily_count = if_not_exists(daily_count, :zero) + :inc,
                        recent_requests = :recent,
                        hour_start = :hour_start,
                        day_start = :day_start,
                        expiration_time = :exp_time''',
                    ExpressionAttributeValues={
                        ':inc': 1,
                        ':zero': 0,
                        ':recent': recent_requests[-self.BURST_LIMIT:],  # Keep only recent N
                        ':hour_start': hour_start,
                        ':day_start': day_start,
                        ':exp_time': current_time + 86400  # 24 hour TTL
                    }
                )
            else:
                # First request
                self.rate_table.put_item(
                    Item={
                        'email_hash': email_hash,
                        'hourly_count': 1,
                        'daily_count': 1,
                        'recent_requests': [current_time],
                        'hour_start': current_time - (current_time % 3600),
                        'day_start': current_time - (current_time % 86400),
                        'expiration_time': current_time + 86400
                    }
                )
            
            return result
            
        except Exception as e:
            print(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limiting fails
            result['allowed'] = True
            result['reason'] = 'Rate limit check unavailable'
            return result
    
    def validate_image_content(self, image_data: bytes) -> Dict[str, any]:
        """Enhanced image validation with magic number checking."""
        result = {'valid': True, 'errors': []}
        
        # Check file size first (before processing)
        size_mb = len(image_data) / (1024 * 1024)
        if size_mb > self.MAX_ATTACHMENT_SIZE_MB:
            result['valid'] = False
            result['errors'].append(f'Image too large ({size_mb:.1f}MB). Maximum {self.MAX_ATTACHMENT_SIZE_MB}MB allowed.')
            return result
        
        # Magic number validation for common image formats
        if not self._validate_image_magic_numbers(image_data):
            result['valid'] = False
            result['errors'].append('File is not a valid image format (JPEG, PNG, or GIF)')
            return result
        
        try:
            # Verify it's a valid image that can be opened
            img = Image.open(io.BytesIO(image_data))
            
            # Dimension validation
            if img.width < 200 or img.height < 200:
                result['valid'] = False
                result['errors'].append('Image too small (minimum 200x200 pixels). Please ensure the entire Nanodrop screen is visible.')
            
            if img.width > 8000 or img.height > 8000:
                result['valid'] = False
                result['errors'].append('Image dimensions too large (maximum 8000x8000 pixels)')
            
            # Check aspect ratio (nanodrop screens are typically ~4:3 or 16:9)
            aspect_ratio = img.width / img.height
            if aspect_ratio < 0.5 or aspect_ratio > 3.0:
                result['valid'] = False
                result['errors'].append('Unusual aspect ratio. Please ensure the photo shows a complete equipment screen.')
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append('Invalid or corrupted image file. Please try re-taking the photo.')
        
        return result
    
    def _validate_image_magic_numbers(self, image_data: bytes) -> bool:
        """Check file magic numbers to verify image format."""
        if len(image_data) < 12:
            return False
        
        # JPEG magic numbers
        if image_data[:2] == b'\xff\xd8':
            return True
        
        # PNG magic numbers  
        if image_data[:8] == b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a':
            return True
        
        # GIF magic numbers
        if image_data[:6] in (b'GIF87a', b'GIF89a'):
            return True
        
        return False
    
    def validate_attachments(self, attachments: List[Dict]) -> Dict[str, any]:
        """Enhanced attachment validation."""
        result = {
            'valid': True,
            'errors': []
        }
        
        if len(attachments) == 0:
            result['valid'] = False
            result['errors'].append("No images found. Please attach a photo of your Nanodrop screen.")
            return result
        
        if len(attachments) > self.MAX_ATTACHMENTS_PER_EMAIL:
            result['valid'] = False
            result['errors'].append(f"Too many attachments ({len(attachments)}). Maximum {self.MAX_ATTACHMENTS_PER_EMAIL} images allowed per email.")
        
        total_size = 0
        for i, attachment in enumerate(attachments):
            # Check file type
            content_type = attachment.get('content_type', '')
            if content_type not in self.ALLOWED_MIME_TYPES:
                result['valid'] = False
                result['errors'].append(f"Image {i+1}: Unsupported file type '{content_type}'. Please send JPEG, PNG, or GIF images only.")
            
            # Validate image content (includes size check and magic numbers)
            image_data = attachment.get('data', b'')
            image_validation = self.validate_image_content(image_data)
            if not image_validation['valid']:
                result['valid'] = False
                result['errors'].extend([f"Image {i+1}: {error}" for error in image_validation['errors']])
            
            total_size += len(image_data) / (1024 * 1024)
        
        if total_size > self.MAX_EMAIL_SIZE_MB:
            result['valid'] = False
            result['errors'].append(f"Total email size too large ({total_size:.1f}MB). Maximum {self.MAX_EMAIL_SIZE_MB}MB allowed. Try compressing your images or sending fewer at once.")
        
        return result
    
    def check_daily_cost_limit(self) -> Dict[str, any]:
        """Check if daily OpenAI cost limit would be exceeded."""
        # This would need to be implemented with actual cost tracking
        # For now, return always allowed
        return {'allowed': True, 'estimated_cost': 0.0}
    
    def sanitize_error_message(self, error: str) -> str:
        """Sanitize error messages to prevent information leakage."""
        sanitized = str(error)
        
        # Remove file paths
        import re
        sanitized = re.sub(r'/[^\s]*', '[REDACTED_PATH]', sanitized)
        
        # Remove potential API keys or tokens
        sanitized = re.sub(r'sk-[a-zA-Z0-9]{48}', '[REDACTED_API_KEY]', sanitized)
        sanitized = re.sub(r'AKIA[A-Z0-9]{16}', '[REDACTED_AWS_KEY]', sanitized)
        
        # Generic error for unexpected issues
        if 'internal' in sanitized.lower() or 'server' in sanitized.lower():
            return "Processing temporarily unavailable. Please try again later."
        
        return sanitized[:200]  # Limit error message length
    
    def log_security_event(self, event_type: str, from_email: str, details: str):
        """Log security events for monitoring."""
        try:
            self.cloudwatch.put_metric_data(
                Namespace='NanodropProcessor/Security',
                MetricData=[
                    {
                        'MetricName': event_type,
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {
                                'Name': 'EmailDomain',
                                'Value': from_email.split('@')[-1] if '@' in from_email else 'unknown'
                            }
                        ]
                    }
                ]
            )
        except Exception as e:
            print(f"Failed to log security event: {e}")


def create_security_response(allowed: bool, reason: str = '', retry_after: int = 0) -> Dict:
    """Create standardized security response."""
    return {
        'allowed': allowed,
        'reason': reason,
        'retry_after': retry_after,
        'timestamp': int(time.time())
    }
