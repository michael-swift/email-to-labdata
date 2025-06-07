#!/usr/bin/env python3
"""
Quick Lambda debugging script - diagnose common issues
"""

import os
import sys
import json
import subprocess

def check_env_vars():
    """Check required environment variables"""
    print("🔍 Checking environment variables...")
    
    if os.path.exists('.env'):
        print("✅ .env file found")
        with open('.env') as f:
            env_content = f.read()
            if 'OPENAI_API_KEY' in env_content:
                print("✅ OPENAI_API_KEY found in .env")
            else:
                print("❌ OPENAI_API_KEY not found in .env")
    else:
        print("❌ .env file not found")
    
def check_dependencies():
    """Check if required packages can be imported"""
    print("\n🔍 Checking Python dependencies...")
    
    try:
        import openai
        print(f"✅ openai installed (version: {openai.__version__})")
    except ImportError:
        print("❌ openai not installed - run: pip install openai")
    
    try:
        import boto3
        print(f"✅ boto3 installed (version: {boto3.__version__})")
    except ImportError:
        print("❌ boto3 not installed - run: pip install boto3")

def check_docker():
    """Check Docker setup"""
    print("\n🔍 Checking Docker...")
    
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker installed: {result.stdout.strip()}")
        else:
            print("❌ Docker not working properly")
    except FileNotFoundError:
        print("❌ Docker not found in PATH")
    
    # Check if Docker daemon is running
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker daemon is running")
        else:
            print("❌ Docker daemon not running - start with: sudo systemctl start docker")
    except:
        pass

def check_aws_cli():
    """Check AWS CLI configuration"""
    print("\n🔍 Checking AWS CLI...")
    
    try:
        result = subprocess.run(['aws', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ AWS CLI installed: {result.stdout.strip()}")
        else:
            print("❌ AWS CLI not working properly")
    except FileNotFoundError:
        print("❌ AWS CLI not found - install with: pip install awscli")
        return
    
    # Check credentials
    try:
        result = subprocess.run(['aws', 'sts', 'get-caller-identity'], capture_output=True, text=True)
        if result.returncode == 0:
            identity = json.loads(result.stdout)
            print(f"✅ AWS credentials configured for account: {identity['Account']}")
        else:
            print("❌ AWS credentials not configured - run: aws configure")
    except:
        print("❌ Could not verify AWS credentials")

def check_lambda_function():
    """Check if Lambda function exists"""
    print("\n🔍 Checking Lambda function...")
    
    try:
        result = subprocess.run(
            ['aws', 'lambda', 'get-function', '--function-name', 'nanodrop-processor', '--region', 'us-west-2'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Lambda function 'nanodrop-processor' exists")
            func_info = json.loads(result.stdout)
            print(f"   Runtime: {func_info['Configuration'].get('Runtime', 'Container Image')}")
            print(f"   Last Modified: {func_info['Configuration']['LastModified']}")
        else:
            print("❌ Lambda function 'nanodrop-processor' not found")
    except:
        print("❌ Could not check Lambda function")

def test_lambda_locally():
    """Test Lambda function locally"""
    print("\n🔍 Testing Lambda function locally...")
    
    if not os.path.exists('lambda_function.py'):
        print("❌ lambda_function.py not found")
        return
    
    print("✅ lambda_function.py found")
    print("   Run 'python3 test_lambda_local.py' to test the function")

def check_s3_bucket():
    """Check S3 bucket configuration"""
    print("\n🔍 Checking S3 bucket...")
    
    try:
        result = subprocess.run(
            ['aws', 's3', 'ls', 's3://nanodrop-emails-seminalcapital/incoming/', '--region', 'us-west-2'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ S3 bucket accessible")
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                print(f"   Found {len(lines)} objects in incoming/")
            else:
                print("   No objects in incoming/ folder")
        else:
            print("❌ Cannot access S3 bucket - check permissions")
    except:
        print("❌ Could not check S3 bucket")

def main():
    print("🏥 Nanodrop Lambda Deployment Diagnostic Tool")
    print("=" * 50)
    
    check_env_vars()
    check_dependencies()
    check_docker()
    check_aws_cli()
    check_lambda_function()
    check_s3_bucket()
    test_lambda_locally()
    
    print("\n📋 Summary:")
    print("- Use './deploy_lambda_improved.sh' for deployment")
    print("- Check DEBUGGING_GUIDE.md for troubleshooting")
    print("- Monitor logs: aws logs tail /aws/lambda/nanodrop-processor --follow")

if __name__ == "__main__":
    main()