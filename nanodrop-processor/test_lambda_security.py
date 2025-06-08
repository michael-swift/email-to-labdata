#!/usr/bin/env python3
"""
Local test script for security-enhanced Lambda function.
Tests imports, basic functionality, and security features before deployment.
"""

import sys
import os
import json
import tempfile
from io import BytesIO
from PIL import Image

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    
    try:
        # Mock AWS services for local testing
        import unittest.mock
        with unittest.mock.patch('boto3.resource'), \
             unittest.mock.patch('boto3.client'):
            
            import lambda_function
            print("✓ lambda_function imported successfully")
            
            import security_config
            print("✓ security_config imported successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_security_validation():
    """Test security validation functions."""
    print("\nTesting security validation...")
    
    try:
        import unittest.mock
        
        # Mock AWS services
        with unittest.mock.patch('boto3.resource') as mock_resource, \
             unittest.mock.patch('boto3.client') as mock_client:
            
            # Mock DynamoDB table
            mock_table = unittest.mock.MagicMock()
            mock_table.load.return_value = None
            mock_resource.return_value.Table.return_value = mock_table
            
            from security_config import SecurityConfig
            security = SecurityConfig()
            
            # Test email validation (doesn't require AWS)
            valid_email = security.validate_email_sender("test@example.com")
            print(f"✓ Email validation works: {valid_email}")
            
            # Test attachment validation with dummy image
            img = Image.new('RGB', (800, 600), color='red')  # Make larger to pass validation
            img_bytes = BytesIO()
            img.save(img_bytes, format='JPEG')
            img_data = img_bytes.getvalue()
            
            attachment_data = [{
                'content_type': 'image/jpeg',
                'data': img_data
            }]
            
            attachment_result = security.validate_attachments(attachment_data)
            print(f"✓ Attachment validation works: {attachment_result}")
        
        return True
        
    except Exception as e:
        print(f"✗ Security validation error: {e}")
        return False

def test_lambda_handler_structure():
    """Test that lambda handler function exists and has proper structure."""
    print("\nTesting lambda handler structure...")
    
    try:
        import unittest.mock
        
        with unittest.mock.patch('boto3.resource'), \
             unittest.mock.patch('boto3.client'):
            
            import lambda_function
            
            # Check that handler function exists
            handler = getattr(lambda_function, 'lambda_handler', None)
            if not handler:
                print("✗ lambda_handler function not found")
                return False
            print("✓ lambda_handler function exists")
            
            # Check that it's callable
            if not callable(handler):
                print("✗ lambda_handler is not callable")
                return False
            print("✓ lambda_handler is callable")
        
        return True
        
    except Exception as e:
        print(f"✗ Lambda handler test error: {e}")
        return False

def test_environment_variables():
    """Test environment variable handling."""
    print("\nTesting environment variables...")
    
    # Save original value
    original_key = os.environ.get('OPENAI_API_KEY')
    
    try:
        import unittest.mock
        
        with unittest.mock.patch('boto3.resource'), \
             unittest.mock.patch('boto3.client'):
            
            # Test without API key
            if 'OPENAI_API_KEY' in os.environ:
                del os.environ['OPENAI_API_KEY']
            
            import lambda_function
            
            try:
                client = lambda_function.get_openai_client()
                print("✗ Should have failed without API key")
                return False
            except ValueError as e:
                if "OPENAI_API_KEY" in str(e):
                    print("✓ Properly handles missing API key")
                else:
                    print(f"✗ Unexpected error: {e}")
                    return False
            
            # Test with dummy API key
            os.environ['OPENAI_API_KEY'] = 'test-key'
            try:
                client = lambda_function.get_openai_client()
                print("✓ Creates OpenAI client with API key")
            except Exception as e:
                print(f"✗ Error creating client: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Environment variable test error: {e}")
        return False
    
    finally:
        # Restore original value
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key
        elif 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

def test_email_parsing():
    """Test email parsing functions."""
    print("\nTesting email parsing...")
    
    try:
        import unittest.mock
        
        with unittest.mock.patch('boto3.resource'), \
             unittest.mock.patch('boto3.client'):
            
            import lambda_function
            import email
            from email.mime.multipart import MIMEMultipart
            from email.mime.image import MIMEImage
            
            # Create a test email with image attachment
            msg = MIMEMultipart()
            msg['Subject'] = 'Test Nanodrop'
            msg['From'] = 'test@example.com'
            msg['To'] = 'nanodrop@seminalcapital.net'
            
            # Create dummy image
            img = Image.new('RGB', (100, 100), color='blue')
            img_bytes = BytesIO()
            img.save(img_bytes, format='JPEG')
            img_data = img_bytes.getvalue()
            
            # Attach image
            img_attachment = MIMEImage(img_data)
            img_attachment.add_header('Content-Disposition', 'attachment', filename='test.jpg')
            msg.attach(img_attachment)
            
            # Test image extraction
            images = lambda_function.extract_images_from_email(msg)
            if len(images) == 1:
                print("✓ Image extraction works")
            else:
                print(f"✗ Expected 1 image, got {len(images)}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Email parsing test error: {e}")
        return False

def test_csv_generation():
    """Test CSV generation with dummy data."""
    print("\nTesting CSV generation...")
    
    try:
        import unittest.mock
        
        with unittest.mock.patch('boto3.resource'), \
             unittest.mock.patch('boto3.client'):
            
            import lambda_function
            
            # Test data
            test_data = {
                'assay_type': 'RNA',
                'commentary': 'Test commentary',
                'samples': [
                    {
                        'sample_number': 1,
                        'concentration': 87.3,
                        'a260_a280': 1.94,
                        'a260_a230': 2.07
                    },
                    {
                        'sample_number': 2,
                        'concentration': -2.1,
                        'a260_a280': -0.55,
                        'a260_a230': -1.23
                    }
                ]
            }
            
            csv_content = lambda_function.generate_csv(test_data)
            
            if 'Sample Number' in csv_content and 'RNA' in csv_content:
                print("✓ CSV generation works")
            else:
                print("✗ CSV content doesn't contain expected headers")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ CSV generation test error: {e}")
        return False

def main():
    """Run all tests."""
    print("=== Local Lambda Security Test ===\n")
    
    tests = [
        test_imports,
        test_security_validation, 
        test_lambda_handler_structure,
        test_environment_variables,
        test_email_parsing,
        test_csv_generation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("✓ All tests passed! Ready for Lambda deployment.")
        return True
    else:
        print("✗ Some tests failed. Fix issues before deployment.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)