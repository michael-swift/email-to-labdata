#!/usr/bin/env python3
"""
Simple deployment using AWS Lambda console upload.
This creates a zip file you can upload manually if permissions are limited.
"""

import zipfile
import os

def create_lambda_zip():
    """Create a zip file for Lambda deployment."""
    
    # Create deployment package
    with zipfile.ZipFile('nanodrop-lambda.zip', 'w') as zipf:
        # Add main function
        zipf.write('lambda_function.py')
        
        # We'll need to install packages manually or use Lambda layers
        print("📦 Created nanodrop-lambda.zip")
        print("")
        print("🎯 To deploy manually:")
        print("1. Go to AWS Lambda console")
        print("2. Create function 'nanodrop-processor'")
        print("3. Upload nanodrop-lambda.zip")
        print("4. Set environment variable: OPENAI_API_KEY")
        print("5. Add S3 trigger to your bucket")
        print("")
        print("OR fix Docker permissions and try ./deploy_lambda.sh again")

if __name__ == "__main__":
    create_lambda_zip()