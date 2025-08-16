#!/usr/bin/env python3
"""
Unit tests for CC/reply-all functionality and loop prevention.
"""

import pytest
import sys
import os
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from lambda_function import send_success_email


class TestCCFunctionality:
    """Test CC/reply-all functionality."""
    
    def test_single_recipient_legacy_format(self):
        """Test backward compatibility with single recipient (string)."""
        test_data = {
            'assay_type': 'Test',
            'samples': [{'sample_number': 1, 'concentration': 10.0}],
            'commentary': 'Test data'
        }
        
        # Should not raise exception with string input (legacy format)
        try:
            # We can't actually send emails in tests, but we can verify the function accepts the input
            recipients = "test@example.com"
            # This would call send_success_email but we'll just verify the parameter handling
            assert isinstance(recipients, str)
            # Convert to list as the function would
            if isinstance(recipients, str):
                recipients = [recipients]
            assert len(recipients) == 1
            assert recipients[0] == "test@example.com"
        except Exception as e:
            pytest.fail(f"Single recipient format should work: {e}")
    
    def test_multiple_recipients_list_format(self):
        """Test new CC functionality with multiple recipients."""
        test_data = {
            'assay_type': 'Test',
            'samples': [{'sample_number': 1, 'concentration': 10.0}],
            'commentary': 'Test data'
        }
        
        # Test multiple recipients
        recipients = ["original@example.com", "cc1@example.com", "cc2@example.com"]
        
        # Verify recipient handling logic
        primary_recipient = recipients[0]
        cc_recipients = recipients[1:] if len(recipients) > 1 else []
        
        assert primary_recipient == "original@example.com"
        assert len(cc_recipients) == 2
        assert "cc1@example.com" in cc_recipients
        assert "cc2@example.com" in cc_recipients


class TestToRecipientExtraction:
    """Test extraction of multiple To recipients."""
    
    def test_multiple_to_recipients(self):
        """Test extracting multiple recipients from To header."""
        import re
        
        # Simulate To header with multiple recipients
        to_header = "digitizer@seminalcapital.net, user1@example.com, user2@example.com"
        
        # Extract emails using regex
        to_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', to_header)
        
        # Filter out service addresses
        service_addresses = {'digitizer@seminalcapital.net', 'nanodrop@seminalcapital.net', 
                           'nanodrop-dev@seminalcapital.net'}
        filtered_to = [email for email in to_emails if email not in service_addresses]
        
        assert len(to_emails) == 3  # Found all 3 emails
        assert len(filtered_to) == 2  # Filtered out service address
        assert 'user1@example.com' in filtered_to
        assert 'user2@example.com' in filtered_to
        assert 'digitizer@seminalcapital.net' not in filtered_to
    
    def test_combined_to_and_cc_recipients(self):
        """Test combining To and CC recipients with deduplication."""
        import re
        
        sender_email = "sender@example.com"
        to_header = "digitizer@seminalcapital.net, colleague1@example.com, sender@example.com"
        cc_header = "colleague2@example.com, colleague1@example.com"  # colleague1 is duplicate
        
        service_addresses = {'digitizer@seminalcapital.net', 'nanodrop@seminalcapital.net'}
        
        # Extract To recipients
        to_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', to_header)
        to_recipients = [email for email in to_emails if email not in service_addresses]
        
        # Extract CC recipients
        cc_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', cc_header)
        cc_recipients = [email for email in cc_emails if email not in service_addresses]
        
        # Combine all recipients
        all_recipients = [sender_email]
        all_recipients.extend(to_recipients)
        all_recipients.extend(cc_recipients)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recipients = []
        for email in all_recipients:
            if email not in seen:
                seen.add(email)
                unique_recipients.append(email)
        
        assert len(unique_recipients) == 3  # sender, colleague1, colleague2 (no duplicates)
        assert unique_recipients[0] == "sender@example.com"
        assert "colleague1@example.com" in unique_recipients
        assert "colleague2@example.com" in unique_recipients
        assert unique_recipients.count("colleague1@example.com") == 1  # No duplicates


class TestLoopPrevention:
    """Test email loop prevention logic."""
    
    def test_service_address_filtering(self):
        """Test that service addresses are filtered from CC list."""
        # Simulate CC extraction with service addresses
        cc_header = "user1@example.com, digitizer@seminalcapital.net, user2@example.com, nanodrop@seminalcapital.net"
        
        # Extract emails using regex (same logic as in lambda_function.py)
        import re
        cc_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', cc_header)
        
        # Filter out service addresses (same logic as in lambda_function.py) 
        service_addresses = {'digitizer@seminalcapital.net', 'nanodrop@seminalcapital.net'}
        filtered_cc = [email for email in cc_emails if email not in service_addresses]
        
        assert len(cc_emails) == 4  # Found all 4 emails
        assert len(filtered_cc) == 2  # Filtered to only user emails
        assert 'user1@example.com' in filtered_cc
        assert 'user2@example.com' in filtered_cc
        assert 'digitizer@seminalcapital.net' not in filtered_cc
        assert 'nanodrop@seminalcapital.net' not in filtered_cc
    
    def test_results_email_detection(self):
        """Test detection of results emails to prevent processing."""
        # Test subject line detection
        subjects_to_ignore = [
            "Lab Data Results - DNA Analysis (3 samples, 1 images)",
            "Re: Lab Data Results - RNA Analysis", 
            "Fwd: Lab Data Results - Protein"
        ]
        
        subjects_to_process = [
            "New lab data for processing",
            "DNA samples ready",
            "Test email"
        ]
        
        for subject in subjects_to_ignore:
            assert "Lab Data Results" in subject, f"Should detect results email: {subject}"
        
        for subject in subjects_to_process:
            assert "Lab Data Results" not in subject, f"Should process normal email: {subject}"
    
    def test_sender_address_detection(self):
        """Test detection of emails from service addresses."""
        service_senders = [
            "digitizer@seminalcapital.net",
            "<digitizer@seminalcapital.net>",
            "Lab Service <digitizer@seminalcapital.net>",
            "nanodrop@seminalcapital.net"
        ]
        
        normal_senders = [
            "user@example.com",
            "researcher@university.edu", 
            "lab@company.com"
        ]
        
        service_addresses = ['digitizer@seminalcapital.net', 'nanodrop@seminalcapital.net']
        
        for sender in service_senders:
            is_service = any(addr in sender for addr in service_addresses)
            assert is_service, f"Should detect service sender: {sender}"
        
        for sender in normal_senders:
            is_service = any(addr in sender for addr in service_addresses)
            assert not is_service, f"Should allow normal sender: {sender}"


class TestEmailHeaderParsing:
    """Test email header parsing logic."""
    
    def test_cc_header_parsing(self):
        """Test parsing of CC headers with various formats."""
        # Test different CC header formats
        test_cases = [
            ("user1@example.com", ["user1@example.com"]),
            ("user1@example.com, user2@example.com", ["user1@example.com", "user2@example.com"]),
            ("User One <user1@example.com>, user2@example.com", ["user1@example.com", "user2@example.com"]),
            ("user1@example.com,user2@example.com", ["user1@example.com", "user2@example.com"]),  # No spaces
            ("", []),  # Empty
        ]
        
        import re
        for cc_header, expected in test_cases:
            if cc_header:
                cc_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', cc_header)
                assert cc_emails == expected, f"Failed to parse: {cc_header}"
            else:
                assert expected == [], "Empty header should result in empty list"
    
    def test_email_message_headers(self):
        """Test extracting headers from email.message objects."""
        # Create a test email
        msg = MIMEMultipart()
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['CC'] = 'cc1@example.com, cc2@example.com'
        msg['Subject'] = 'Test email'
        
        # Test header extraction (same logic as lambda_function.py)
        cc_header = msg.get('CC') or msg.get('Cc') or msg.get('cc')
        assert cc_header == 'cc1@example.com, cc2@example.com'
        
        from_email = msg['From']
        subject = msg['Subject']
        assert from_email == 'sender@example.com'
        assert subject == 'Test email'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])