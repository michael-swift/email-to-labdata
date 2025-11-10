#!/usr/bin/env python3
"""
Integration tests for loop prevention in email processing.
"""

import pytest
import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestLoopPreventionIntegration:
    """Test loop prevention in full Lambda handler context."""
    
    @patch('src.lambda_function.s3')
    @patch('src.lambda_function.logger')
    def test_results_email_ignored(self, mock_logger, mock_s3):
        """Test that results emails are ignored to prevent loops."""
        from lambda_function import lambda_handler
        
        # Mock S3 object with a results email
        results_email_content = b"""From: user@example.com
To: digitizer@seminalcapital.net
Subject: Lab Data Results - DNA Analysis (3 samples, 1 images)
CC: colleague@example.com

This is a results email that should be ignored.
"""
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=results_email_content))
        }
        
        # Create test event
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test-key', 'size': 1024}
                }
            }]
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Call lambda handler
        result = lambda_handler(event, context)
        
        # Should return early and ignore the email
        assert result['statusCode'] == 200
        assert result['body'] == 'Results email ignored'
        
        # Should log the ignore action
        mock_logger.info.assert_called_with(
            "Ignoring results email to prevent loop",
            subject="Lab Data Results - DNA Analysis (3 samples, 1 images)",
            from_email="user@example.com"
        )
    
    @patch('src.lambda_function.s3')
    @patch('src.lambda_function.logger')
    def test_service_sender_ignored(self, mock_logger, mock_s3):
        """Test that emails from service addresses are ignored."""
        from lambda_function import lambda_handler
        
        # Mock S3 object with email from service address
        service_email_content = b"""From: digitizer@seminalcapital.net
To: user@example.com
Subject: Some forwarded email

This email is from our service and should be ignored.
"""
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=service_email_content))
        }
        
        # Create test event
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test-key', 'size': 1024}
                }
            }]
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Call lambda handler
        result = lambda_handler(event, context)
        
        # Should return early and ignore the email
        assert result['statusCode'] == 200
        assert result['body'] == 'Results email ignored'
    
    @patch('src.lambda_function.s3')
    @patch('src.lambda_function.logger')
    def test_processed_header_ignored(self, mock_logger, mock_s3):
        """Test that emails with our processing header are ignored."""
        from lambda_function import lambda_handler
        
        # Mock S3 object with already processed email
        processed_email_content = b"""From: user@example.com
To: digitizer@seminalcapital.net
Subject: New lab data
X-Lab-Data-Processed: true

This email was already processed and should be ignored.
"""
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=processed_email_content))
        }
        
        # Create test event
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test-key', 'size': 1024}
                }
            }]
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Call lambda handler
        result = lambda_handler(event, context)
        
        # Should return early and ignore the email
        assert result['statusCode'] == 200
        assert result['body'] == 'Already processed'
        
        # Should log the ignore action
        mock_logger.info.assert_called_with(
            "Ignoring already processed email",
            message_id=None
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])