
#!/bin/bash

# S3 Trigger Debugging Script
# Helps diagnose and fix S3 -> Lambda trigger issues

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
LAMBDA_FUNCTION_NAME="nanodrop-processor"
S3_BUCKET="nanodrop-emails-seminalcapital"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "UNKNOWN")

echo -e "${BLUE}🔍 S3 Trigger Debugging Tool${NC}"
echo "================================"
echo "Lambda: $LAMBDA_FUNCTION_NAME"
echo "Bucket: $S3_BUCKET"
echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo ""

# Function to check S3 bucket configuration
check_s3_bucket() {
    echo -e "${YELLOW}1. Checking S3 Bucket Configuration...${NC}"
    
    # Check if bucket exists
    if aws s3api head-bucket --bucket $S3_BUCKET 2>/dev/null; then
        echo -e "${GREEN}✓ Bucket exists${NC}"
    else
        echo -e "${RED}✗ Bucket does not exist or no access${NC}"
        echo "  Create bucket: aws s3 mb s3://$S3_BUCKET --region $AWS_REGION"
        return 1
    fi
    
    # Check bucket region
    BUCKET_REGION=$(aws s3api get-bucket-location --bucket $S3_BUCKET --query LocationConstraint --output text 2>/dev/null || echo "UNKNOWN")
    if [ "$BUCKET_REGION" = "None" ]; then
        BUCKET_REGION="us-east-1"
    fi
    echo -e "  Bucket region: $BUCKET_REGION"
    
    # Check current notifications
    echo -e "\n${YELLOW}2. Current Bucket Notifications:${NC}"
    aws s3api get-bucket-notification-configuration --bucket $S3_BUCKET 2>/dev/null | jq '.' || echo "  No notifications configured"
}

# Function to check Lambda permissions
check_lambda_permissions() {
    echo -e "\n${YELLOW}3. Checking Lambda Permissions...${NC}"
    
    # Get Lambda policy
    POLICY=$(aws lambda get-policy --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>/dev/null || echo "{}")
    
    if [ "$POLICY" = "{}" ]; then
        echo -e "${RED}✗ No Lambda resource policy found${NC}"
    else
        echo "$POLICY" | jq -r '.Policy' | jq '.'
        
        # Check for S3 permission
        if echo "$POLICY" | grep -q "s3.amazonaws.com"; then
            echo -e "${GREEN}✓ S3 permission exists${NC}"
        else
            echo -e "${RED}✗ S3 permission missing${NC}"
        fi
    fi
}

# Function to test Lambda invocation
test_lambda_invocation() {
    echo -e "\n${YELLOW}4. Testing Direct Lambda Invocation...${NC}"
    
    # Create test payload
    cat > test-s3-event.json << EOF
{
    "Records": [{
        "eventSource": "aws:s3",
        "eventName": "ObjectCreated:Put",
        "s3": {
            "bucket": {
                "name": "$S3_BUCKET",
                "arn": "arn:aws:s3:::$S3_BUCKET"
            },
            "object": {
                "key": "incoming/test-trigger-debug.eml"
            }
        }
    }]
}
EOF
    
    # Invoke Lambda
    echo "Invoking Lambda with test S3 event..."
    aws lambda invoke \
        --function-name $LAMBDA_FUNCTION_NAME \
        --payload file://test-s3-event.json \
        --region $AWS_REGION \
        test-response.json 2>&1
    
    # Check response
    if [ -f test-response.json ]; then
        echo -e "${GREEN}✓ Lambda invocation successful${NC}"
        echo "Response:"
        cat test-response.json | jq '.' || cat test-response.json
        rm -f test-response.json
    else
        echo -e "${RED}✗ Lambda invocation failed${NC}"
    fi
    
    rm -f test-s3-event.json
}

# Function to fix S3 trigger
fix_s3_trigger() {
    echo -e "\n${YELLOW}5. Fixing S3 Trigger Configuration...${NC}"
    
    # Remove existing permission (if any)
    echo "Removing old S3 permission..."
    aws lambda remove-permission \
        --function-name $LAMBDA_FUNCTION_NAME \
        --statement-id AllowExecutionFromS3Bucket \
        --region $AWS_REGION 2>/dev/null || true
    
    # Add new permission
    echo "Adding S3 invocation permission..."
    aws lambda add-permission \
        --function-name $LAMBDA_FUNCTION_NAME \
        --statement-id AllowExecutionFromS3Bucket \
        --action "lambda:InvokeFunction" \
        --principal s3.amazonaws.com \
        --source-arn "arn:aws:s3:::$S3_BUCKET" \
        --source-account $AWS_ACCOUNT_ID \
        --region $AWS_REGION
    
    echo -e "${GREEN}✓ Lambda permission added${NC}"
    
    # Configure S3 notification
    echo -e "\nConfiguring S3 bucket notification..."
    
    # Get Lambda ARN
    LAMBDA_ARN=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION --query Configuration.FunctionArn --output text)
    
    cat > s3-notification-config.json << EOF
{
    "LambdaFunctionConfigurations": [
        {
            "Id": "NanodropEmailTrigger",
            "LambdaFunctionArn": "$LAMBDA_ARN",
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "prefix",
                            "Value": "incoming/"
                        }
                    ]
                }
            }
        }
    ]
}
EOF
    
    aws s3api put-bucket-notification-configuration \
        --bucket $S3_BUCKET \
        --notification-configuration file://s3-notification-config.json
    
    echo -e "${GREEN}✓ S3 notification configured${NC}"
    rm -f s3-notification-config.json
}

# Function to test end-to-end
test_end_to_end() {
    echo -e "\n${YELLOW}6. Testing End-to-End S3 Trigger...${NC}"
    
    # Create test file
    echo "Test email content for S3 trigger debug" > test-email.txt
    
    # Upload to S3
    echo "Uploading test file to S3..."
    aws s3 cp test-email.txt s3://$S3_BUCKET/incoming/test-$(date +%s).txt
    
    echo -e "${GREEN}✓ Test file uploaded${NC}"
    echo ""
    echo "Check CloudWatch logs to see if Lambda was triggered:"
    echo -e "${BLUE}aws logs tail /aws/lambda/$LAMBDA_FUNCTION_NAME --follow --region $AWS_REGION${NC}"
    
    rm -f test-email.txt
}

# Main debugging flow
main() {
    echo -e "${BLUE}Starting S3 trigger debugging...${NC}\n"
    
    # Run checks
    check_s3_bucket
    check_lambda_permissions
    test_lambda_invocation
    
    # Ask if user wants to fix
    echo -e "\n${YELLOW}Issues found with S3 trigger configuration.${NC}"
    read -p "Do you want to fix the S3 trigger? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        fix_s3_trigger
        
        # Test after fix
        read -p "Do you want to test the trigger? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            test_end_to_end
        fi
    fi
    
    echo -e "\n${GREEN}Debugging complete!${NC}"
    echo ""
    echo "Additional debugging commands:"
    echo "- View Lambda logs: aws logs tail /aws/lambda/$LAMBDA_FUNCTION_NAME --follow"
    echo "- List S3 objects: aws s3 ls s3://$S3_BUCKET/incoming/"
    echo "- Check SES setup: aws ses describe-active-receipt-rule-set"
}

# Run main
main