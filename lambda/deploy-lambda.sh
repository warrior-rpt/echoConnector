#!/bin/bash

# EchoConnector Lambda Deployer
# Automatically packages and deploys watchman_lambda.py and its dependencies

# --- CONFIGURATION ---
FUNCTION_NAME="echo-watchman"
HANDLER="watchman_lambda.lambda_handler"
RUNTIME="python3.12"
INCIDENTS_TABLE="echo-incidents"
SLACK_WEBHOOK_SECRET="echo/slack-webhook"
AI_CONFIG_SECRET="echo/ai-config"

# --- PROFILE CONFIGURATION ---
AWS_PROFILE=${1:-"Hack"}
echo "Using AWS Profile: $AWS_PROFILE"

# --- INTEGRATION TESTING ---
echo "Running pre-deployment integration tests..."
export AWS_PROFILE="$AWS_PROFILE"
export PYTHONPATH="$PYTHONPATH:$(pwd)"
python3 ../scripts/test_integration.py

if [ $? -ne 0 ]; then
    echo "❌ Integration tests failed. Aborting deployment."
    exit 1
fi
echo "✅ Integration tests passed."

# --- DETECT ACCOUNT & REGION ---
echo "Checking AWS environment..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile "$AWS_PROFILE")
REGION=$(aws configure get region --profile "$AWS_PROFILE")
REGION=${REGION:-us-east-1}

if [ -z "$ACCOUNT_ID" ]; then
    echo "Error: Could not detect AWS Account ID. Are your credentials set?"
    exit 1
fi

# --- FIND S3 BUCKET ---
# We look for the most recent echo-runbooks bucket
RUNBOOKS_BUCKET=$(aws s3 ls --profile "$AWS_PROFILE" | grep echo-runbooks | awk '{print $3}' | tail -n 1)

if [ -z "$RUNBOOKS_BUCKET" ]; then
    echo "Warning: Could not find an echo-runbooks bucket automatically."
    echo "Please enter the bucket name manually (e.g., echo-runbooks-1710172800):"
    read RUNBOOKS_BUCKET
else
    echo "Found bucket: $RUNBOOKS_BUCKET"
fi

# --- PACKAGING ---
echo "Packaging Lambda function..."
cd "$(dirname "$0")" # Ensure we are in the script's directory (lambda/)

# Create a temporary ZIP
ZIP_NAME="deploy_package.zip"
rm -f "$ZIP_NAME"

# Add core files and subdirectories
zip -r -q "$ZIP_NAME" . -x "*.zip" "*.sh" "__pycache__/*" "*/__pycache__/*" "*.vmdk" ".DS_Store"

echo "Package created: $(du -sh $ZIP_NAME | awk '{print $1}')"

# --- DEPLOYMENT ---
echo "Deploying to AWS ($REGION)..."

# Check if function exists
aws lambda get-function --function-name "$FUNCTION_NAME" --profile "$AWS_PROFILE" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "Function exists. Updating code..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_NAME" \
        --profile "$AWS_PROFILE"
    
    echo "Waiting for function update to complete..."
    aws lambda wait function-updated \
        --function-name "$FUNCTION_NAME" \
        --profile "$AWS_PROFILE"
    
    echo "Updating configuration..."

    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --environment "Variables={RUNBOOKS_BUCKET=$RUNBOOKS_BUCKET,INCIDENTS_TABLE=$INCIDENTS_TABLE,SLACK_WEBHOOK_SECRET=$SLACK_WEBHOOK_SECRET,AI_CONFIG_SECRET=$AI_CONFIG_SECRET}" \
        --profile "$AWS_PROFILE"
else
    echo "Function not found. Creating new function..."
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/EchoWatchmanRole"
    
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --zip-file "fileb://$ZIP_NAME" \
        --timeout 60 \
        --memory-size 256 \
        --environment "Variables={RUNBOOKS_BUCKET=$RUNBOOKS_BUCKET,INCIDENTS_TABLE=$INCIDENTS_TABLE,SLACK_WEBHOOK_SECRET=$SLACK_WEBHOOK_SECRET,AI_CONFIG_SECRET=$AI_CONFIG_SECRET}" \
        --profile "$AWS_PROFILE"
fi


if [ $? -eq 0 ]; then
    echo "Deployment successful!"
    rm "$ZIP_NAME"
else
    echo "Deployment failed."
    exit 1
fi
