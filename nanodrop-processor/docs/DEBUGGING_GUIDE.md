# Lambda Deployment Debugging Guide

This guide helps diagnose and fix common Lambda deployment issues for the Nanodrop processor.

## Quick Diagnostics

Run these commands to quickly identify issues:

```bash
# 1. Check Lambda function status
aws lambda get-function --function-name nanodrop-processor --region us-west-2

# 2. View recent CloudWatch logs
aws logs tail /aws/lambda/nanodrop-processor --follow --region us-west-2

# 3. Check S3 bucket for emails
aws s3 ls s3://nanodrop-emails-seminalcapital/incoming/ --recursive

# 4. Test Lambda locally
python3 test_lambda_local.py
```

## Common Issues and Solutions

### 1. Module Import Errors

**Symptoms:**
```
Unable to import module 'lambda_function': No module named 'openai'
```

**Solutions:**
- Rebuild Docker image: `docker build -t nanodrop-processor .`
- Check lambda_requirements.txt includes all dependencies
- Verify Docker image has all packages: 
  ```bash
  docker run --rm nanodrop-processor pip list
  ```

### 2. OPENAI_API_KEY Missing

**Symptoms:**
```
OpenAI API key not found
```

**Solutions:**
- Check Lambda environment variables:
  ```bash
  aws lambda get-function-configuration --function-name nanodrop-processor \
    --query 'Environment.Variables' --region us-west-2
  ```
- Update environment variable:
  ```bash
  aws lambda update-function-configuration --function-name nanodrop-processor \
    --environment Variables={OPENAI_API_KEY=your-key} --region us-west-2
  ```

### 3. S3 Access Denied

**Symptoms:**
```
Access Denied when accessing S3 bucket
```

**Solutions:**
- Check Lambda execution role has S3 permissions:
  ```bash
  aws iam get-role-policy --role-name nanodrop-lambda-role \
    --policy-name nanodrop-lambda-policy
  ```
- Verify S3 bucket exists and has correct name
- Check S3 bucket policy allows Lambda access

### 4. SES Send Email Failures

**Symptoms:**
```
MessageRejected: Email address is not verified
```

**Solutions:**
- Verify domain in SES:
  ```bash
  aws ses list-verified-email-addresses --region us-west-2
  ```
- Check SES is in production mode (not sandbox)
- Verify Lambda role has SES permissions

### 5. Docker Build Failures

**Symptoms:**
```
docker: permission denied
```

**Solutions:**
- Add user to docker group: `sudo usermod -aG docker $USER`
- Restart terminal or run: `newgrp docker`
- Check Docker daemon is running: `sudo systemctl status docker`

### 6. ECR Push Failures

**Symptoms:**
```
no basic auth credentials
```

**Solutions:**
- Re-authenticate with ECR:
  ```bash
  aws ecr get-login-password --region us-west-2 | \
    docker login --username AWS --password-stdin \
    $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-west-2.amazonaws.com
  ```
- Check IAM permissions for ECR

## Debugging Workflow

### Step 1: Local Testing
```bash
# Test Lambda function locally first
python3 test_lambda_local.py

# If successful, proceed to deployment
```

### Step 2: Deploy with Improved Script
```bash
# Use the improved deployment script for better error handling
./deploy_lambda_improved.sh
```

### Step 3: Monitor Deployment
```bash
# Watch CloudWatch logs during deployment
aws logs tail /aws/lambda/nanodrop-processor --follow --region us-west-2
```

### Step 4: Test with Real Email
1. Send test email to nanodrop@seminalcapital.net with a Nanodrop image
2. Check S3 bucket for incoming email
3. Monitor CloudWatch logs for processing
4. Check your email for response

## Manual Recovery Steps

If automated deployment fails, try manual steps:

### 1. Build and Push Docker Image Manually
```bash
# Build
docker build -t nanodrop-processor .

# Tag
docker tag nanodrop-processor:latest \
  YOUR_ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/nanodrop-processor:latest

# Push
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/nanodrop-processor:latest
```

### 2. Update Lambda Function Manually
```bash
# Update code
aws lambda update-function-code \
  --function-name nanodrop-processor \
  --image-uri YOUR_ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/nanodrop-processor:latest \
  --region us-west-2
```

### 3. Create Minimal ZIP Deployment (Fallback)
```bash
# Create minimal deployment package
pip install --target ./package openai boto3
cd package
cp ../lambda_function.py .
zip -r ../function.zip .
cd ..

# Upload via Console or CLI
aws lambda update-function-code \
  --function-name nanodrop-processor \
  --zip-file fileb://function.zip \
  --region us-west-2
```

## Monitoring and Logs

### View Real-time Logs
```bash
# Stream logs
aws logs tail /aws/lambda/nanodrop-processor --follow --region us-west-2

# Search logs for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/nanodrop-processor \
  --filter-pattern "ERROR" \
  --region us-west-2
```

### Check Lambda Metrics
```bash
# Get function metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=nanodrop-processor \
  --statistics Sum \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --region us-west-2
```

## Support Resources

- **AWS Lambda Docs**: https://docs.aws.amazon.com/lambda/
- **Docker Lambda Images**: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
- **SES Configuration**: https://docs.aws.amazon.com/ses/latest/dg/receiving-email.html
- **CloudWatch Insights**: Use for advanced log queries

## Emergency Rollback

If deployment breaks production:

```bash
# List function versions
aws lambda list-versions-by-function \
  --function-name nanodrop-processor \
  --region us-west-2

# Rollback to previous version
aws lambda update-alias \
  --function-name nanodrop-processor \
  --name PROD \
  --function-version PREVIOUS_VERSION_NUMBER \
  --region us-west-2
```