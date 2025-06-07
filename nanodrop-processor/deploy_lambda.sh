#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check for OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not found in .env file"
    exit 1
fi

# Configuration
AWS_REGION="us-west-2"
LAMBDA_FUNCTION_NAME="nanodrop-processor"
ECR_REPOSITORY_NAME="nanodrop-processor"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🚀 Deploying Nanodrop Lambda Function"
echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"

# Create ECR repository if it doesn't exist
echo "📦 Creating ECR repository..."
aws ecr create-repository --repository-name $ECR_REPOSITORY_NAME --region $AWS_REGION 2>/dev/null || echo "Repository already exists"

# Get login token and login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t $ECR_REPOSITORY_NAME .

# Tag image
docker tag $ECR_REPOSITORY_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest

# Push image to ECR
echo "📤 Pushing image to ECR..."
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest

# Create Lambda execution role if it doesn't exist
echo "👤 Creating Lambda execution role..."
aws iam create-role --role-name nanodrop-lambda-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' 2>/dev/null || echo "Role already exists"

# Attach policies to the role
echo "📋 Attaching policies..."
aws iam attach-role-policy --role-name nanodrop-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name nanodrop-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam attach-role-policy --role-name nanodrop-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonSESFullAccess

# Wait for role to be ready
echo "⏳ Waiting for role to propagate..."
sleep 10

# Create or update Lambda function
echo "🎯 Creating Lambda function..."
if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo "Function exists, updating configuration for container image..."
    # Update package type to Image if it's currently Zip
    aws lambda update-function-configuration \
        --function-name $LAMBDA_FUNCTION_NAME \
        --region $AWS_REGION \
        --timeout 60 \
        --memory-size 512 \
        --environment Variables={OPENAI_API_KEY=$OPENAI_API_KEY} \
        2>/dev/null || true
    
    # Wait for function to be ready for code update
    echo "⏳ Waiting for function to be ready..."
    aws lambda wait function-updated --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION
    
    # Update the code
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest \
        --region $AWS_REGION
else
    # Create new function with Image package type
    aws lambda create-function \
        --function-name $LAMBDA_FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:latest \
        --role arn:aws:iam::$AWS_ACCOUNT_ID:role/nanodrop-lambda-role \
        --region $AWS_REGION \
        --timeout 60 \
        --memory-size 512 \
        --environment Variables={OPENAI_API_KEY=$OPENAI_API_KEY}
fi

# Add S3 trigger
echo "🔗 Adding S3 trigger..."
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --principal s3.amazonaws.com \
    --statement-id AllowExecutionFromS3Bucket \
    --action "lambda:InvokeFunction" \
    --source-arn arn:aws:s3:::nanodrop-emails-seminalcapital \
    --source-account $AWS_ACCOUNT_ID \
    2>/dev/null || echo "Permission already exists"

# Configure S3 bucket notification
echo "📢 Configuring S3 notifications..."
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
    --bucket nanodrop-emails-seminalcapital \
    --notification-configuration file://notification.json

rm notification.json

echo "✅ Deployment complete!"
echo ""
echo "📧 Email nanodrop@seminalcapital.net with a photo to test!"
echo "🔍 Check CloudWatch logs: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logGroup:group=/aws/lambda/$LAMBDA_FUNCTION_NAME"