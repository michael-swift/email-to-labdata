#!/bin/bash

# Improved Lambda deployment script with better error handling and debugging

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi
    
    # Check .env file
    if [ ! -f .env ]; then
        log_error ".env file not found. Create it with OPENAI_API_KEY=your-key"
        exit 1
    fi
    
    # Load and check OPENAI_API_KEY
    export $(cat .env | grep -v '^#' | xargs)
    if [ -z "$OPENAI_API_KEY" ]; then
        log_error "OPENAI_API_KEY not found in .env file"
        exit 1
    fi
    
    log_info "All prerequisites met ✓"
}

# Configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
LAMBDA_FUNCTION_NAME="nanodrop-processor"
ECR_REPOSITORY_NAME="nanodrop-processor"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
S3_BUCKET="nanodrop-emails-seminalcapital"

# Main deployment function
deploy_lambda() {
    log_info "Starting Lambda deployment..."
    log_info "Region: $AWS_REGION"
    log_info "Account: $AWS_ACCOUNT_ID"
    
    # Step 1: Create ECR repository
    log_info "Creating ECR repository..."
    if aws ecr describe-repositories --repository-names $ECR_REPOSITORY_NAME --region $AWS_REGION &> /dev/null; then
        log_warning "ECR repository already exists"
    else
        aws ecr create-repository --region $AWS_REGION --repository-name $ECR_REPOSITORY_NAME --region $AWS_REGION
        log_info "ECR repository created ✓"
    fi
    
    # Step 2: Docker login
    log_info "Logging into ECR..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Step 3: Build Docker image
    log_info "Building Docker image for ARM64 architecture..."
    # Use legacy builder for Lambda compatibility
    export DOCKER_BUILDKIT=0
    docker build -t $ECR_REPOSITORY_NAME . || {
        log_error "Docker build failed"
        exit 1
    }
    log_info "Docker image built ✓"
    
    # Step 4: Tag and push image
    log_info "Tagging Docker image..."
    docker tag $ECR_REPOSITORY_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest
    
    log_info "Pushing image to ECR..."
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest || {
        log_error "Docker push failed"
        exit 1
    }
    log_info "Image pushed to ECR ✓"
    
    # Step 5: Create/Update IAM role
    create_iam_role
    
    # Step 6: Deploy Lambda function
    deploy_function
    
    # Step 7: Configure S3 trigger
    configure_s3_trigger
    
    log_info "Deployment complete! ✅"
    log_info ""
    log_info "📧 Email nanodrop@seminalcapital.net with a photo to test!"
    log_info "🔍 CloudWatch logs: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logGroup:group=/aws/lambda/$LAMBDA_FUNCTION_NAME"
}

# Create IAM role for Lambda
create_iam_role() {
    log_info "Setting up IAM role..."
    
    # Create trust policy
    cat > trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
}
EOF
    
    # Create role
    if aws iam get-role --role-name nanodrop-lambda-role &> /dev/null; then
        log_warning "IAM role already exists"
    else
        aws iam create-role --role-name nanodrop-lambda-role --assume-role-policy-document file://trust-policy.json
        log_info "IAM role created ✓"
    fi
    
    # Attach policies
    log_info "Attaching IAM policies..."
    aws iam attach-role-policy --role-name nanodrop-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true
    
    # Create custom policy for S3 and SES
    cat > lambda-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::$S3_BUCKET",
                "arn:aws:s3:::$S3_BUCKET/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail"
            ],
            "Resource": "*"
        }
    ]
}
EOF
    
    # Create and attach custom policy
    aws iam put-role-policy --role-name nanodrop-lambda-role --policy-name nanodrop-lambda-policy --policy-document file://lambda-policy.json
    
    # Clean up temp files
    rm -f trust-policy.json lambda-policy.json
    
    # Wait for role propagation
    log_info "Waiting for IAM role to propagate..."
    sleep 10
}

# Deploy Lambda function
deploy_function() {
    log_info "Deploying Lambda function..."
    
    FUNCTION_EXISTS=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>&1 || echo "not found")
    
    if [[ $FUNCTION_EXISTS == *"not found"* ]]; then
        # Create new function
        log_info "Creating new Lambda function..."
        aws lambda create-function \
            --function-name $LAMBDA_FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest \
            --role arn:aws:iam::$AWS_ACCOUNT_ID:role/nanodrop-lambda-role \
            --region $AWS_REGION \
            --timeout 60 \
            --memory-size 512 \
            --architectures arm64 \
            --environment Variables={OPENAI_API_KEY=$OPENAI_API_KEY} || {
                log_error "Failed to create Lambda function"
                exit 1
            }
        log_info "Lambda function created ✓"
    else
        # Update existing function
        log_info "Updating existing Lambda function configuration..."
        aws lambda update-function-configuration \
            --function-name $LAMBDA_FUNCTION_NAME \
            --region $AWS_REGION \
            --timeout 60 \
            --memory-size 512 \
            --environment Variables={OPENAI_API_KEY=$OPENAI_API_KEY} || {
                log_warning "Failed to update configuration"
            }
        
        # Wait for configuration update
        log_info "Waiting for configuration update..."
        aws lambda wait function-updated --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION
        
        # Update code
        log_info "Updating Lambda function code..."
        aws lambda update-function-code \
            --function-name $LAMBDA_FUNCTION_NAME \
            --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest \
            --region $AWS_REGION || {
                log_error "Failed to update Lambda code"
                exit 1
            }
        log_info "Lambda function updated ✓"
    fi
}

# Configure S3 trigger
configure_s3_trigger() {
    log_info "Configuring S3 trigger..."
    
    # Add Lambda permission for S3
    aws lambda add-permission \
        --function-name $LAMBDA_FUNCTION_NAME \
        --principal s3.amazonaws.com \
        --statement-id AllowExecutionFromS3Bucket \
        --action "lambda:InvokeFunction" \
        --source-arn arn:aws:s3:::$S3_BUCKET \
        --source-account $AWS_ACCOUNT_ID \
        2>/dev/null || log_warning "S3 permission already exists"
    
    # Configure S3 bucket notification
    cat > notification.json << EOF
{
    "LambdaFunctionConfigurations": [{
        "LambdaFunctionArn": "arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$LAMBDA_FUNCTION_NAME",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
            "Key": {
                "FilterRules": [{
                    "Name": "prefix",
                    "Value": "incoming/"
                }]
            }
        }
    }]
}
EOF
    
    aws s3api put-bucket-notification-configuration \
        --bucket $S3_BUCKET \
        --notification-configuration file://notification.json || {
            log_error "Failed to configure S3 notifications"
            log_warning "Make sure the S3 bucket '$S3_BUCKET' exists and you have permission to modify it"
        }
    
    rm -f notification.json
    log_info "S3 trigger configured ✓"
}

# Test deployment
test_deployment() {
    log_info "Testing Lambda deployment..."
    
    # Create test event
    cat > test-event.json << EOF
{
    "Records": [{
        "s3": {
            "bucket": {"name": "$S3_BUCKET"},
            "object": {"key": "incoming/test-email"}
        }
    }]
}
EOF
    
    # Invoke Lambda function
    log_info "Invoking Lambda function with test event..."
    aws lambda invoke \
        --function-name $LAMBDA_FUNCTION_NAME \
        --payload file://test-event.json \
        --region $AWS_REGION \
        response.json
    
    # Check response
    if [ -f response.json ]; then
        log_info "Lambda response:"
        cat response.json
        rm -f response.json
    fi
    
    rm -f test-event.json
}

# Main execution
main() {
    check_prerequisites
    deploy_lambda
    
    # Ask if user wants to test
    read -p "Do you want to test the deployment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        test_deployment
    fi
}

# Run main function
main "$@"