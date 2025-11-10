#!/bin/bash

# Development Lambda deployment script - separate environment for testing
# Based on production deploy_lambda.sh but with -dev naming

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[DEV]${NC} $1"
}

log_error() {
    echo -e "${RED}[DEV ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[DEV WARNING]${NC} $1"
}

# Remove older DEV images automatically to keep the repo clean.
cleanup_ecr_images() {
    local keep_count=${ECR_IMAGES_TO_KEEP:-3}
    log_info "Cleaning up old DEV ECR images (keeping $keep_count most recent)..."

    local digest_output
    if ! digest_output=$(aws ecr describe-images \
        --repository-name $ECR_REPOSITORY_NAME \
        --region $AWS_REGION \
        --query 'sort_by(imageDetails,& imagePushedAt)[*].imageDigest' \
        --output text 2>/dev/null); then
        log_warning "Unable to list DEV ECR images; skipping cleanup"
        return
    fi

    if [ -z "$digest_output" ] || [ "$digest_output" == "None" ]; then
        log_info "No DEV images available for cleanup"
        return
    fi

    local sanitized_output
    sanitized_output=$(printf "%s\n" "$digest_output" | tr '\t' '\n' | sed '/^$/d')

    local digest_array=()
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        digest_array+=("$line")
    done <<< "$sanitized_output"

    local total=${#digest_array[@]}

    if [ "$total" -le "$keep_count" ]; then
        log_info "DEV repository has $total image(s); nothing to delete"
        return
    fi

    local delete_count=$((total - keep_count))
    log_info "Deleting $delete_count old DEV image(s) from ECR..."

    for ((i=0; i<delete_count; i++)); do
        local digest="${digest_array[$i]}"
        if aws ecr batch-delete-image \
            --repository-name $ECR_REPOSITORY_NAME \
            --region $AWS_REGION \
            --image-ids imageDigest=$digest >/dev/null; then
            log_info "Deleted old DEV image $digest"
        else
            log_warning "Failed to delete DEV image $digest"
        fi
    done
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites for DEV environment..."
    
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
    
    # Check .env file (look in current directory or parent)
    if [ -f .env ]; then
        ENV_FILE=".env"
    elif [ -f ../.env ]; then
        ENV_FILE="../.env"
    else
        log_error ".env file not found. Create it with OPENAI_API_KEY=your-key"
        exit 1
    fi
    
    # Load and check OPENAI_API_KEY
    export $(cat $ENV_FILE | grep -v '^#' | xargs)
    if [ -z "$OPENAI_API_KEY" ]; then
        log_error "OPENAI_API_KEY not found in .env file"
        exit 1
    fi
    
    log_info "All prerequisites met ✓"
}

# DEV Configuration - everything gets -dev suffix
AWS_REGION="${AWS_REGION:-us-west-2}"
LAMBDA_FUNCTION_NAME="nanodrop-processor-dev"
ECR_REPOSITORY_NAME="nanodrop-processor-dev"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
S3_BUCKET="nanodrop-emails-dev-seminalcapital"

# Main deployment function
deploy_lambda() {
    log_info "Starting DEV Lambda deployment..."
    log_info "Region: $AWS_REGION"
    log_info "Account: $AWS_ACCOUNT_ID"
    log_info "Function: $LAMBDA_FUNCTION_NAME"
    log_info "Bucket: $S3_BUCKET"
    
    # Step 1: Create S3 bucket first (needed for SES)
    create_s3_bucket
    
    # Step 2: Create ECR repository
    log_info "Creating ECR repository..."
    if aws ecr describe-repositories --repository-names $ECR_REPOSITORY_NAME --region $AWS_REGION &> /dev/null; then
        log_warning "ECR repository already exists"
    else
        aws ecr create-repository --region $AWS_REGION --repository-name $ECR_REPOSITORY_NAME
        log_info "ECR repository created ✓"
    fi
    
    # Step 3: Docker login
    log_info "Logging into ECR..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Step 4: Build Docker image
    log_info "Building Docker image for ARM64 architecture..."
    export DOCKER_BUILDKIT=0
    docker build -t $ECR_REPOSITORY_NAME . || {
        log_error "Docker build failed"
        exit 1
    }
    log_info "Docker image built ✓"
    
    # Step 5: Tag and push image
    log_info "Tagging Docker image..."
    docker tag $ECR_REPOSITORY_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest
    
    log_info "Pushing image to ECR..."
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest || {
        log_error "Docker push failed"
        exit 1
    }
    log_info "Image pushed to ECR ✓"
    
    # Step 6: Create/Update IAM role
    create_iam_role
    
    # Step 7: Deploy Lambda function
    deploy_function

    # Step 7.5: Clean up older images now that the new one is live
    cleanup_ecr_images

    # Step 8: Configure S3 trigger
    configure_s3_trigger
    
    # Step 9: Setup SES email routing (manual step reminder)
    setup_ses_routing
    
    log_info "DEV deployment complete! ✅"
    log_info ""
    log_info "📧 To test: Email nanodrop-dev@seminalcapital.net with a photo"
    log_info "🔍 CloudWatch logs: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logGroup:group:/aws/lambda/$LAMBDA_FUNCTION_NAME"
    log_info "📊 S3 bucket: https://s3.console.aws.amazon.com/s3/buckets/$S3_BUCKET"
}

# Create S3 bucket for dev environment
create_s3_bucket() {
    log_info "Setting up S3 bucket for DEV..."
    
    if aws s3 ls "s3://$S3_BUCKET" &> /dev/null; then
        log_warning "S3 bucket already exists"
    else
        # Create bucket
        if [ "$AWS_REGION" = "us-east-1" ]; then
            aws s3 mb s3://$S3_BUCKET
        else
            aws s3 mb s3://$S3_BUCKET --region $AWS_REGION
        fi
        log_info "S3 bucket created ✓"
    fi
    
    # Create incoming folder
    aws s3api put-object --bucket $S3_BUCKET --key incoming/ --body /dev/null 2>/dev/null || true
    log_info "S3 bucket configured ✓"
}

# Create IAM role for Lambda (dev-specific)
create_iam_role() {
    log_info "Setting up IAM role for DEV..."
    
    ROLE_NAME="nanodrop-lambda-role-dev"
    
    # Create trust policy
    cat > trust-policy-dev.json << EOF
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
    if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
        log_warning "IAM role already exists"
    else
        aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://trust-policy-dev.json
        log_info "IAM role created ✓"
    fi
    
    # Attach policies
    log_info "Attaching IAM policies..."
    aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true
    
    # Create custom policy for S3 and SES (dev-specific)
    cat > lambda-policy-dev.json << EOF
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
    aws iam put-role-policy --role-name $ROLE_NAME --policy-name nanodrop-lambda-policy-dev --policy-document file://lambda-policy-dev.json
    
    # Clean up temp files
    rm -f trust-policy-dev.json lambda-policy-dev.json
    
    # Wait for role propagation
    log_info "Waiting for IAM role to propagate..."
    sleep 10
}

# Deploy Lambda function
deploy_function() {
    log_info "Deploying DEV Lambda function..."
    
    ROLE_NAME="nanodrop-lambda-role-dev"
    FUNCTION_EXISTS=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>&1 || echo "not found")
    
    if [[ $FUNCTION_EXISTS == *"not found"* ]]; then
        # Create new function
        log_info "Creating new DEV Lambda function..."
        aws lambda create-function \
            --function-name $LAMBDA_FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest \
            --role arn:aws:iam::$AWS_ACCOUNT_ID:role/$ROLE_NAME \
            --region $AWS_REGION \
            --timeout 120 \
            --memory-size 512 \
            --architectures arm64 \
            --environment Variables={OPENAI_API_KEY=$OPENAI_API_KEY,ENVIRONMENT=development} || {
                log_error "Failed to create Lambda function"
                exit 1
            }
        log_info "DEV Lambda function created ✓"
    else
        # Update existing function
        log_info "Updating existing DEV Lambda function configuration..."
        aws lambda update-function-configuration \
            --function-name $LAMBDA_FUNCTION_NAME \
            --region $AWS_REGION \
            --timeout 120 \
            --memory-size 512 \
            --environment Variables={OPENAI_API_KEY=$OPENAI_API_KEY,ENVIRONMENT=development} || {
                log_warning "Failed to update configuration"
            }
        
        # Wait for configuration update
        log_info "Waiting for configuration update..."
        aws lambda wait function-updated --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION
        
        # Update code
        log_info "Updating DEV Lambda function code..."
        aws lambda update-function-code \
            --function-name $LAMBDA_FUNCTION_NAME \
            --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest \
            --region $AWS_REGION || {
                log_error "Failed to update Lambda code"
                exit 1
            }
        log_info "DEV Lambda function updated ✓"
    fi
}

# Configure S3 trigger
configure_s3_trigger() {
    log_info "Configuring S3 trigger for DEV..."
    
    # Add Lambda permission for S3
    aws lambda add-permission \
        --function-name $LAMBDA_FUNCTION_NAME \
        --principal s3.amazonaws.com \
        --statement-id AllowExecutionFromS3Bucket-dev \
        --action "lambda:InvokeFunction" \
        --source-arn arn:aws:s3:::$S3_BUCKET \
        --source-account $AWS_ACCOUNT_ID \
        2>/dev/null || log_warning "S3 permission already exists"
    
    # Configure S3 bucket notification
    cat > notification-dev.json << EOF
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
        --notification-configuration file://notification-dev.json || {
            log_error "Failed to configure S3 notifications"
            log_warning "Make sure the S3 bucket '$S3_BUCKET' exists and you have permission to modify it"
        }
    
    rm -f notification-dev.json
    log_info "S3 trigger configured ✓"
}

# Setup SES routing (instructions for manual step)
setup_ses_routing() {
    log_info "SES Setup Instructions:"
    log_info "1. Go to SES Console: https://console.aws.amazon.com/ses/"
    log_info "2. Create email receiving rule for nanodrop-dev@seminalcapital.net"
    log_info "3. Route to S3 bucket: $S3_BUCKET with prefix: incoming/"
    log_info ""
    log_info "Or use AWS CLI:"
    log_info "aws ses put-receipt-rule --rule-set-name default-rule-set --rule '{\"Name\":\"nanodrop-dev-rule\",\"Recipients\":[\"nanodrop-dev@seminalcapital.net\"],\"Actions\":[{\"S3Action\":{\"BucketName\":\"$S3_BUCKET\",\"ObjectKeyPrefix\":\"incoming/\"}}]}'"
}

# Test deployment
test_deployment() {
    log_info "Testing DEV Lambda deployment..."
    
    # Create test event
    cat > test-event-dev.json << EOF
{
    "Records": [{
        "s3": {
            "bucket": {"name": "$S3_BUCKET"},
            "object": {"key": "incoming/test-email-dev"}
        }
    }]
}
EOF
    
    # Invoke Lambda function
    log_info "Invoking DEV Lambda function with test event..."
    aws lambda invoke \
        --function-name $LAMBDA_FUNCTION_NAME \
        --payload file://test-event-dev.json \
        --region $AWS_REGION \
        response-dev.json
    
    # Check response
    if [ -f response-dev.json ]; then
        log_info "Lambda response:"
        cat response-dev.json
        rm -f response-dev.json
    fi
    
    rm -f test-event-dev.json
}

# Main execution
main() {
    check_prerequisites
    deploy_lambda
    
    # Ask if user wants to test
    read -p "Do you want to test the DEV deployment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        test_deployment
    fi
}

# Run main function
main "$@"
