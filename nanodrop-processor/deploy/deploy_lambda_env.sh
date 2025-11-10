#!/bin/bash

# Enhanced Lambda deployment script with environment support (prod/dev)

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_env() {
    ENV_UPPER=$(echo "$ENVIRONMENT" | tr '[:lower:]' '[:upper:]')
    echo -e "${BLUE}[$ENV_UPPER]${NC} $1"
}

# Remove older ECR images so we keep only a few recent layers per env.
cleanup_ecr_images() {
    local keep_count=${ECR_IMAGES_TO_KEEP:-3}
    log_info "Cleaning up old $ENVIRONMENT ECR images (keeping $keep_count most recent)..."

    local digest_output
    if ! digest_output=$(aws ecr describe-images \
        --repository-name $ECR_REPOSITORY_NAME \
        --region $AWS_REGION \
        --query 'sort_by(imageDetails,& imagePushedAt)[*].imageDigest' \
        --output text 2>/dev/null); then
        log_warning "Unable to list $ENVIRONMENT ECR images; skipping cleanup"
        return
    fi

    if [ -z "$digest_output" ] || [ "$digest_output" == "None" ]; then
        log_info "No $ENVIRONMENT images available for cleanup"
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
        log_info "$ENVIRONMENT repository has $total image(s); nothing to delete"
        return
    fi

    local delete_count=$((total - keep_count))
    log_info "Deleting $delete_count old $ENVIRONMENT image(s) from ECR..."

    for ((i=0; i<delete_count; i++)); do
        local digest="${digest_array[$i]}"
        if aws ecr batch-delete-image \
            --repository-name $ECR_REPOSITORY_NAME \
            --region $AWS_REGION \
            --image-ids imageDigest=$digest >/dev/null; then
            log_info "Deleted old $ENVIRONMENT image $digest"
        else
            log_warning "Failed to delete $ENVIRONMENT image $digest"
        fi
    done
}

# Usage function
usage() {
    echo "Usage: $0 [prod|dev]"
    echo "  prod - Deploy to production environment"
    echo "  dev  - Deploy to development environment"
    exit 1
}

# Check environment argument
if [ $# -ne 1 ]; then
    usage
fi

ENVIRONMENT=$1
if [[ ! "$ENVIRONMENT" =~ ^(prod|dev)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    usage
fi

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

# Environment-specific configuration
configure_environment() {
    AWS_REGION="${AWS_REGION:-us-west-2}"
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    if [ "$ENVIRONMENT" == "prod" ]; then
        LAMBDA_FUNCTION_NAME="nanodrop-processor"
        ECR_REPOSITORY_NAME="nanodrop-processor"
        S3_BUCKET="nanodrop-emails-seminalcapital"
        S3_PREFIX="incoming/"
        TABLE_PREFIX=""
        EMAIL_DOMAIN="@seminalcapital.net"
        SES_RULE_NAME="nanodrop-receipt"
    else
        LAMBDA_FUNCTION_NAME="nanodrop-processor-dev"
        ECR_REPOSITORY_NAME="nanodrop-processor-dev"
        S3_BUCKET="nanodrop-emails-seminalcapital"
        S3_PREFIX="dev/"
        TABLE_PREFIX="dev-"
        EMAIL_DOMAIN="-dev@seminalcapital.net"
        SES_RULE_NAME="nanodrop-dev-receipt"
    fi
    
    log_env "Configuration loaded"
    log_info "Lambda Function: $LAMBDA_FUNCTION_NAME"
    log_info "S3 Path: s3://$S3_BUCKET/$S3_PREFIX"
    log_info "Email suffix: $EMAIL_DOMAIN"
}

# Main deployment function
deploy_lambda() {
    log_env "Starting Lambda deployment..."
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
    
    # Step 5: Create DynamoDB tables
    create_dynamodb_tables
    
    # Step 6: Create/Update IAM role
    create_iam_role
    
    # Step 7: Deploy Lambda function
    deploy_function

    # Step 7.5: Clean up older images now that the new image is published
    cleanup_ecr_images

    # Step 8: Configure S3 trigger
    configure_s3_trigger
    
    # Step 9: Configure SES rule (if needed)
    configure_ses_rule
    
    log_env "Deployment complete! ✅"
    log_info ""
    log_info "📧 Email nanodrop$EMAIL_DOMAIN with a photo to test!"
    log_info "🔍 CloudWatch logs: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logGroup:group=/aws/lambda/$LAMBDA_FUNCTION_NAME"
}

# Create DynamoDB tables
create_dynamodb_tables() {
    log_info "Setting up DynamoDB tables..."
    
    # Create requests table
    REQUESTS_TABLE="${TABLE_PREFIX}nanodrop-requests"
    if aws dynamodb describe-table --table-name $REQUESTS_TABLE --region $AWS_REGION &> /dev/null; then
        log_warning "$REQUESTS_TABLE table already exists"
    else
        log_info "Creating $REQUESTS_TABLE table..."
        aws dynamodb create-table \
            --table-name $REQUESTS_TABLE \
            --attribute-definitions \
                AttributeName=request_id,AttributeType=S \
                AttributeName=user_email,AttributeType=S \
                AttributeName=timestamp,AttributeType=S \
            --key-schema \
                AttributeName=request_id,KeyType=HASH \
            --global-secondary-indexes \
                'IndexName=user-email-index,KeySchema=[{AttributeName=user_email,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
            --billing-mode PAY_PER_REQUEST \
            --region $AWS_REGION
        
        log_info "Waiting for $REQUESTS_TABLE table to be active..."
        aws dynamodb wait table-exists --table-name $REQUESTS_TABLE --region $AWS_REGION
        log_info "$REQUESTS_TABLE table created ✓"
    fi
    
    # Create user stats table
    USER_STATS_TABLE="${TABLE_PREFIX}nanodrop-user-stats"
    if aws dynamodb describe-table --table-name $USER_STATS_TABLE --region $AWS_REGION &> /dev/null; then
        log_warning "$USER_STATS_TABLE table already exists"
    else
        log_info "Creating $USER_STATS_TABLE table..."
        aws dynamodb create-table \
            --table-name $USER_STATS_TABLE \
            --attribute-definitions \
                AttributeName=user_email,AttributeType=S \
            --key-schema \
                AttributeName=user_email,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --region $AWS_REGION
        
        log_info "Waiting for $USER_STATS_TABLE table to be active..."
        aws dynamodb wait table-exists --table-name $USER_STATS_TABLE --region $AWS_REGION
        log_info "$USER_STATS_TABLE table created ✓"
    fi
}

# Create IAM role for Lambda
create_iam_role() {
    log_info "Setting up IAM role..."
    
    ROLE_NAME="nanodrop-lambda-role-$ENVIRONMENT"
    
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
    if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
        log_warning "IAM role already exists"
    else
        aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://trust-policy.json
        log_info "IAM role created ✓"
    fi
    
    # Attach policies
    log_info "Attaching IAM policies..."
    aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true
    
    # Create custom policy for S3, SES, and DynamoDB
    cat > lambda-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket",
                "s3:PutObject"
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
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": [
                "arn:aws:dynamodb:$AWS_REGION:$AWS_ACCOUNT_ID:table/${TABLE_PREFIX}nanodrop-requests",
                "arn:aws:dynamodb:$AWS_REGION:$AWS_ACCOUNT_ID:table/${TABLE_PREFIX}nanodrop-requests/index/*",
                "arn:aws:dynamodb:$AWS_REGION:$AWS_ACCOUNT_ID:table/${TABLE_PREFIX}nanodrop-user-stats"
            ]
        }
    ]
}
EOF
    
    # Create and attach custom policy
    aws iam put-role-policy --role-name $ROLE_NAME --policy-name nanodrop-lambda-policy-$ENVIRONMENT --policy-document file://lambda-policy.json
    
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
    
    ROLE_NAME="nanodrop-lambda-role-$ENVIRONMENT"
    
    # Environment variables - handle empty TABLE_PREFIX for prod
    if [ -z "$TABLE_PREFIX" ]; then
        ENV_VARS="OPENAI_API_KEY=$OPENAI_API_KEY,ENVIRONMENT=$ENVIRONMENT,S3_PREFIX=$S3_PREFIX"
    else
        ENV_VARS="OPENAI_API_KEY=$OPENAI_API_KEY,ENVIRONMENT=$ENVIRONMENT,S3_PREFIX=$S3_PREFIX,TABLE_PREFIX=$TABLE_PREFIX"
    fi
    
    if [[ $FUNCTION_EXISTS == *"not found"* ]]; then
        # Create new function
        log_info "Creating new Lambda function..."
        aws lambda create-function \
            --function-name $LAMBDA_FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest \
            --role arn:aws:iam::$AWS_ACCOUNT_ID:role/$ROLE_NAME \
            --region $AWS_REGION \
            --timeout 120 \
            --memory-size 512 \
            --architectures arm64 \
            --environment Variables={$ENV_VARS} || {
                log_error "Failed to create Lambda function"
                exit 1
            }
        log_info "Lambda function created ✓"
        
        # Wait for function to be active
        log_info "Waiting for Lambda function to be active..."
        aws lambda wait function-active --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION
    else
        # Update existing function
        log_info "Updating existing Lambda function configuration..."
        aws lambda update-function-configuration \
            --function-name $LAMBDA_FUNCTION_NAME \
            --region $AWS_REGION \
            --timeout 120 \
            --memory-size 512 \
            --role arn:aws:iam::$AWS_ACCOUNT_ID:role/$ROLE_NAME \
            --environment Variables={$ENV_VARS} || {
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
        --statement-id AllowExecutionFromS3Bucket-$ENVIRONMENT \
        --action "lambda:InvokeFunction" \
        --source-arn arn:aws:s3:::$S3_BUCKET \
        --source-account $AWS_ACCOUNT_ID \
        2>/dev/null || log_warning "S3 permission already exists"
    
    # Get existing bucket notification configuration
    aws s3api get-bucket-notification-configuration --bucket $S3_BUCKET > existing-notification.json 2>/dev/null || echo '{}' > existing-notification.json
    
    # Create new Lambda configuration
    NEW_CONFIG=$(cat << EOF
{
    "Id": "nanodrop-$ENVIRONMENT",
    "LambdaFunctionArn": "arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$LAMBDA_FUNCTION_NAME",
    "Events": ["s3:ObjectCreated:*"],
    "Filter": {
        "Key": {
            "FilterRules": [{
                "Name": "prefix",
                "Value": "$S3_PREFIX"
            }]
        }
    }
}
EOF
)
    
    # Update configuration using Python to merge configurations
    python3 << EOF
import json
import sys

with open('existing-notification.json', 'r') as f:
    config = json.load(f)

if 'LambdaFunctionConfigurations' not in config:
    config['LambdaFunctionConfigurations'] = []

# Remove existing configuration for this environment
config['LambdaFunctionConfigurations'] = [
    c for c in config['LambdaFunctionConfigurations'] 
    if c.get('Id') != 'nanodrop-$ENVIRONMENT'
]

# Add new configuration
new_config = $NEW_CONFIG
config['LambdaFunctionConfigurations'].append(new_config)

with open('notification.json', 'w') as f:
    json.dump(config, f, indent=2)
EOF
    
    aws s3api put-bucket-notification-configuration \
        --bucket $S3_BUCKET \
        --notification-configuration file://notification.json || {
            log_error "Failed to configure S3 notifications"
            log_warning "Make sure the S3 bucket '$S3_BUCKET' exists and you have permission to modify it"
        }
    
    rm -f notification.json existing-notification.json
    log_info "S3 trigger configured ✓"
}

# Configure SES rule
configure_ses_rule() {
    log_info "Configuring SES rule..."
    
    # Check if rule set exists
    RULE_SET_EXISTS=$(aws ses describe-active-receipt-rule-set 2>&1 || echo "not found")
    
    if [[ $RULE_SET_EXISTS == *"not found"* ]]; then
        log_warning "No active SES rule set found. You'll need to configure SES manually."
        log_info "To set up email receiving:"
        log_info "1. Verify your domain in SES"
        log_info "2. Create a receipt rule set"
        log_info "3. Add a rule to save emails to S3 bucket: $S3_BUCKET/$S3_PREFIX"
        log_info "4. Set the rule to trigger Lambda: $LAMBDA_FUNCTION_NAME"
        return
    fi
    
    # Create S3 action
    S3_ACTION=$(cat << EOF
{
    "BucketName": "$S3_BUCKET",
    "ObjectKeyPrefix": "$S3_PREFIX"
}
EOF
)
    
    # Create Lambda action  
    LAMBDA_ACTION=$(cat << EOF
{
    "FunctionArn": "arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$LAMBDA_FUNCTION_NAME",
    "InvocationType": "Event"
}
EOF
)
    
    log_info "SES rule configuration:"
    log_info "  Rule name: $SES_RULE_NAME"
    log_info "  Recipient: nanodrop$EMAIL_DOMAIN"
    log_info "  S3 path: s3://$S3_BUCKET/$S3_PREFIX"
    log_info "  Lambda: $LAMBDA_FUNCTION_NAME"
    
    # Note: Actually creating/updating SES rules is complex and depends on existing setup
    # For now, just provide instructions
    if [ "$ENVIRONMENT" == "dev" ]; then
        log_warning "For development environment, you need to manually add a new SES rule:"
        log_info "1. Go to SES console: https://console.aws.amazon.com/ses/home?region=$AWS_REGION#receipt-rules:"
        log_info "2. Add a new rule named: $SES_RULE_NAME"
        log_info "3. Recipient: nanodrop-dev@yourdomain.com"
        log_info "4. Actions:"
        log_info "   - Save to S3: $S3_BUCKET/$S3_PREFIX"
        log_info "   - Invoke Lambda: $LAMBDA_FUNCTION_NAME"
    fi
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
            "object": {"key": "${S3_PREFIX}test-email"}
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
    log_env "Deploying to $ENVIRONMENT environment"
    
    check_prerequisites
    configure_environment
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
