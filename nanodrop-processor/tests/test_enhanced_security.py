#!/usr/bin/env python3
"""
Test enhanced security features for Phase 3 hardening.
"""

import sys
import os
import unittest
from io import BytesIO
from PIL import Image

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

# Mock AWS services for testing
import unittest.mock
with unittest.mock.patch('boto3.resource'), \
     unittest.mock.patch('boto3.client'):
    from security_config import SecurityConfig


class TestEnhancedSecurity(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock DynamoDB table
        with unittest.mock.patch('boto3.resource'), \
             unittest.mock.patch('boto3.client'):
            self.security = SecurityConfig()
    
    def test_reputable_domain_validation(self):
        """Test that reputable domains are accepted."""
        test_cases = [
            ('researcher@university.edu', True),
            ('lab@company.com', True),
            ('scientist@institute.org', True),
            ('user@government.gov', True),
            ('team@startup.ai', True),
            ('researcher@cambridge.ac.uk', True),
            ('student@tempmail.com', False),  # Blocked pattern
            ('user@example.tk', False),  # Suspicious TLD
            ('test@fake.xyz', False),  # Not in allowed TLDs
        ]
        
        for email, should_be_valid in test_cases:
            with self.subTest(email=email):
                result = self.security.validate_email_sender(email)
                self.assertEqual(result['valid'], should_be_valid, 
                               f"Email {email} validation failed: {result.get('reason', '')}")
    
    def test_magic_number_validation(self):
        """Test magic number validation for different file types."""
        # Create valid JPEG data
        img = Image.new('RGB', (800, 600), color='red')
        jpeg_bytes = BytesIO()
        img.save(jpeg_bytes, format='JPEG')
        jpeg_data = jpeg_bytes.getvalue()
        
        # Create valid PNG data  
        png_bytes = BytesIO()
        img.save(png_bytes, format='PNG')
        png_data = png_bytes.getvalue()
        
        # Test valid images
        jpeg_result = self.security.validate_image_content(jpeg_data)
        self.assertTrue(jpeg_result['valid'], f"JPEG validation failed: {jpeg_result['errors']}")
        
        png_result = self.security.validate_image_content(png_data)
        self.assertTrue(png_result['valid'], f"PNG validation failed: {png_result['errors']}")
        
        # Test invalid magic numbers
        fake_data = b'This is not an image file'
        fake_result = self.security.validate_image_content(fake_data)
        self.assertFalse(fake_result['valid'])
        self.assertIn('not a valid image format', fake_result['errors'][0])
    
    def test_image_size_validation(self):
        """Test image size limits."""
        # Create oversized image data (simulate large file)
        large_data = b'\xff\xd8' + b'x' * (25 * 1024 * 1024)  # 25MB with JPEG magic
        
        result = self.security.validate_image_content(large_data)
        self.assertFalse(result['valid'])
        self.assertIn('too large', result['errors'][0])
    
    def test_attachment_validation_messages(self):
        """Test user-friendly error messages."""
        # Test no attachments
        result = self.security.validate_attachments([])
        self.assertFalse(result['valid'])
        self.assertIn('No images found', result['errors'][0])
        
        # Test unsupported file type
        attachments = [{
            'content_type': 'application/pdf',
            'data': b'fake pdf data'
        }]
        
        result = self.security.validate_attachments(attachments)
        self.assertFalse(result['valid'])
        self.assertIn('Unsupported file type', result['errors'][0])
        self.assertIn('JPEG or PNG', result['errors'][0])
    
    def test_comprehensive_validation(self):
        """Test complete validation flow with good image."""
        # Create valid test image
        img = Image.new('RGB', (800, 600), color='blue')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_data = img_bytes.getvalue()
        
        attachments = [{
            'content_type': 'image/jpeg',
            'data': img_data
        }]
        
        result = self.security.validate_attachments(attachments)
        self.assertTrue(result['valid'], f"Valid image failed validation: {result['errors']}")


if __name__ == '__main__':
    unittest.main()
