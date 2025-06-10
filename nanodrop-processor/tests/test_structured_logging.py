#!/usr/bin/env python3
"""Test structured logging functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import json
from structured_logger import StructuredLogger
from io import StringIO
import unittest
from unittest.mock import patch


class TestStructuredLogging(unittest.TestCase):
    def setUp(self):
        self.logger = StructuredLogger("test-service")
        
    def capture_log_output(self, func, *args, **kwargs):
        """Capture printed JSON output from logger."""
        with patch('sys.stdout', new=StringIO()) as captured:
            func(*args, **kwargs)
            output = captured.getvalue().strip()
            return json.loads(output) if output else None
    
    def test_basic_info_log(self):
        """Test basic info logging."""
        log = self.capture_log_output(
            self.logger.info, 
            "Test message", 
            custom_field="test_value"
        )
        
        self.assertEqual(log['level'], 'INFO')
        self.assertEqual(log['message'], 'Test message')
        self.assertEqual(log['custom_field'], 'test_value')
        self.assertIn('timestamp', log)
    
    def test_request_context(self):
        """Test request context setting."""
        self.logger.set_request_context("test-request-123", {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "test-key", "size": 1024}
                }
            }]
        })
        
        log = self.capture_log_output(self.logger.info, "With context")
        
        self.assertEqual(log['request_id'], 'test-request-123')
        self.assertEqual(log['s3_bucket'], 'test-bucket')
        self.assertEqual(log['s3_key'], 'test-key')
        self.assertEqual(log['s3_size_bytes'], 1024)
    
    def test_user_context(self):
        """Test user context setting."""
        self.logger.set_user_context("test@example.com", "Test Subject")
        
        log = self.capture_log_output(self.logger.info, "With user")
        
        self.assertEqual(log['user_email'], 'test@example.com')
        self.assertEqual(log['email_subject'], 'Test Subject')
    
    def test_error_logging(self):
        """Test error logging with exception."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            log = self.capture_log_output(
                self.logger.error,
                "Error occurred",
                exception=e
            )
        
        self.assertEqual(log['level'], 'ERROR')
        self.assertEqual(log['error_type'], 'ValueError')
        self.assertEqual(log['error_message'], 'Test error')
        self.assertIn('stack_trace', log)
    
    def test_metric_logging(self):
        """Test metric logging."""
        log = self.capture_log_output(
            self.logger.metric,
            "processing_time",
            1234,
            unit="ms"
        )
        
        self.assertEqual(log['metric_name'], 'processing_time')
        self.assertEqual(log['metric_value'], 1234)
        self.assertEqual(log['metric_unit'], 'ms')
    
    def test_image_processed_log(self):
        """Test image processing log."""
        log = self.capture_log_output(
            self.logger.image_processed,
            image_number=1,
            total_images=3,
            success=True,
            samples_extracted=5
        )
        
        self.assertEqual(log['image_number'], 1)
        self.assertEqual(log['total_images'], 3)
        self.assertTrue(log['success'])
        self.assertEqual(log['samples_extracted'], 5)
    
    def test_openai_request_log(self):
        """Test OpenAI request logging."""
        log = self.capture_log_output(
            self.logger.openai_request,
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            duration_ms=2000
        )
        
        self.assertEqual(log['openai_model'], 'gpt-4o')
        self.assertEqual(log['prompt_tokens'], 100)
        self.assertEqual(log['completion_tokens'], 50)
        self.assertEqual(log['total_tokens'], 150)
        self.assertEqual(log['openai_duration_ms'], 2000)
    
    def test_request_completed_log(self):
        """Test request completion logging."""
        # Set start time to test duration calculation
        self.logger.request_start_time = 1000.0
        
        with patch('time.time', return_value=1002.5):  # 2.5 seconds later
            log = self.capture_log_output(
                self.logger.request_completed,
                success=True,
                images_processed=2,
                samples_extracted=10,
                csv_generated=True
            )
        
        self.assertTrue(log['success'])
        self.assertEqual(log['images_processed'], 2)
        self.assertEqual(log['samples_extracted'], 10)
        self.assertTrue(log['csv_generated'])
        self.assertEqual(log['total_duration_ms'], 2500)


if __name__ == '__main__':
    unittest.main()