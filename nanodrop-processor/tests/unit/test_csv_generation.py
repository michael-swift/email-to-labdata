#!/usr/bin/env python3
"""
Unit tests for CSV generation functionality.
Tests different data formats to catch variable scope and header alignment issues.
"""

import pytest
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from lambda_function import generate_csv


class TestCSVGeneration:
    """Test CSV generation with different input formats."""
    
    def test_simplified_format_with_columns(self):
        """Test new simplified format where GPT returns all data including quality."""
        data = {
            'columns': ['Sample', 'ng/uL', 'A260/A280', 'A260/A230', 'Quality Assessment', 'Assay Type'],
            'samples': [
                {
                    'Sample': '1',
                    'ng/uL': '17.4',
                    'A260/A280': '1.86',
                    'A260/A230': '2.21',
                    'Quality Assessment': 'Good quality',
                    'Assay Type': 'Nanodrop'
                },
                {
                    'Sample': '2', 
                    'ng/uL': '18.2',
                    'A260/A280': '1.89',
                    'A260/A230': '1.99',
                    'Quality Assessment': 'Good quality',
                    'Assay Type': 'Nanodrop'
                }
            ]
        }
        
        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]
        
        # Check header
        assert lines[0] == 'Sample,ng/uL,A260/A280,A260/A230,Quality Assessment,Assay Type'
        
        # Check data rows
        assert lines[1] == '1,17.4,1.86,2.21,Good quality,Nanodrop'
        assert lines[2] == '2,18.2,1.89,1.99,Good quality,Nanodrop'
    
    def test_simplified_format_with_hash_column(self):
        """Test simplified format with # column header (keep as-is from GPT)."""
        data = {
            'columns': ['#', 'ng/uL', 'A260/A280', 'A260/A230'],
            'samples': [
                {
                    '#': '1',
                    'ng/uL': '17.4',
                    'A260/A280': '1.86',
                    'A260/A230': '2.21'
                }
            ]
        }

        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]

        # Header should keep # as GPT returned it, plus auto-added Quality Assessment and Assay Type
        assert lines[0] == '#,ng/uL,A260/A280,A260/A230,Quality Assessment,Assay Type'
        # Data row should include default quality and assay type values
        assert lines[1] == '1,17.4,1.86,2.21,Check manually,Unknown'
    
    def test_plate_format(self):
        """Test 96-well plate format."""
        data = {
            'is_plate_format': True,
            'samples': [
                {'well': 'A1', 'value': '123.4'},
                {'well': 'A2', 'value': '156.7'},
                {'well': 'B1', 'value': '89.2'}
            ]
        }
        
        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]
        
        # Check header
        assert lines[0] == 'Well,Value,Quality Assessment,Assay Type'
        
        # Should generate all 96 wells, not just the extracted ones
        assert len(lines) == 97  # 1 header + 96 wells
        
        # Check some specific wells
        a1_line = next(line for line in lines if line.startswith('A1,'))
        assert 'A1,123.4,' in a1_line
        
        # Wells not extracted should show "not extracted"
        c1_line = next(line for line in lines if line.startswith('C1,'))
        assert 'C1,not extracted,' in c1_line
    
    def test_legacy_format(self):
        """Test legacy format without columns key."""
        data = {
            'samples': [
                {
                    'sample_number': '1',
                    'concentration': '17.4',
                    'a260_a280': '1.86',
                    'a260_a230': '2.21'
                }
            ]
        }

        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]

        # Legacy format is detected as nanodrop-like, so uses "Sample Number" header
        assert lines[0] == 'Sample Number,Concentration (ng/uL),A260/A280,A260/A230,Quality Assessment,Assay Type'

        # Check data row
        assert '1,17.4,1.86,2.21,' in lines[1]
    
    def test_long_form_data_format(self):
        """Test complex long form data format."""
        data = {
            'long_form_data': {
                'samples': [
                    {
                        'standardized_values': {
                            'sample_id': 'Sample_1',
                            'concentration_ng_ul': '17.4',
                            'a260_a280': '1.86',
                            'a260_a230': '2.21'
                        }
                    }
                ]
            }
        }
        
        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]
        
        # Should handle this format without errors
        assert len(lines) >= 2  # Header + at least one data row
        assert 'Sample ID' in lines[0]
    
    def test_empty_samples(self):
        """Test handling of empty samples."""
        data = {
            'samples': []
        }
        
        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]
        
        # Should return empty CSV with headers
        assert lines[0] == 'Sample,Data,Note'
        assert lines[1] == 'No data,extracted,Please check image quality'
    
    def test_missing_quality_values(self):
        """Test samples without quality assessment values."""
        data = {
            'columns': ['Sample', 'ng/uL', 'A260/A280'],
            'samples': [
                {
                    'Sample': '1',
                    'ng/uL': '17.4',
                    'A260/A280': '1.86'
                    # No Quality Assessment or Assay Type
                }
            ]
        }

        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]

        # Should handle missing values gracefully by adding default quality and assay type
        assert len(lines) >= 2
        assert lines[0] == 'Sample,ng/uL,A260/A280,Quality Assessment,Assay Type'
        assert lines[1] == '1,17.4,1.86,Check manually,Unknown'
    
    def test_mixed_data_types(self):
        """Test samples with mixed data types (numbers, strings, empty)."""
        data = {
            'columns': ['Sample', 'Concentration', 'Notes'],
            'samples': [
                {
                    'Sample': 1,  # Number
                    'Concentration': 17.4,  # Float
                    'Notes': 'Good'  # String
                },
                {
                    'Sample': '2',
                    'Concentration': '',  # Empty
                    'Notes': None  # None
                }
            ]
        }

        csv_output = generate_csv(data)
        lines = [line.rstrip('\r') for line in csv_output.strip().split('\n')]

        # Should convert all values to strings safely and append quality/assay type
        assert lines[0] == 'Sample,Concentration,Notes,Quality Assessment,Assay Type'
        assert lines[1] == '1,17.4,Good,Check manually,Unknown'
        assert lines[2] == '2,,,Check manually,Unknown'  # Empty and None should become empty strings


if __name__ == '__main__':
    pytest.main([__file__])