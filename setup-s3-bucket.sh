#!/bin/bash
# setup-s3-bucket.sh
# Creates S3 bucket for EchoConnector runbooks

set -e  # Exit on error

echo "🪣 Setting up S3 bucket for runbooks..."

# Configuration
BUCKET_NAME="echo-runbooks-$(date +%s)"  # Unique name with timestamp
REGION="us-east-1"

# Create bucket
echo "Creating bucket: $BUCKET_NAME"
aws s3 mb s3://$BUCKET_NAME --region $REGION

# Enable versioning
echo "Enabling versioning..."
aws s3api put-bucket-versioning \
    --bucket $BUCKET_NAME \
    --versioning-configuration Status=Enabled

# Create local directory structure
echo "Creating directory structure..."
mkdir -p runbooks/aws/rds
mkdir -p runbooks/aws/lambda
mkdir -p runbooks/aws/ecs

echo ""
echo "✅ S3 bucket created successfully!"
echo "📝 Bucket name: $BUCKET_NAME"
echo ""
echo "⚠️  IMPORTANT: Save this bucket name!"
echo "   You'll need it for:"
echo "   - Lambda environment variable: RUNBOOKS_BUCKET=$BUCKET_NAME"
echo "   - Uploading runbooks: aws s3 sync runbooks/ s3://$BUCKET_NAME/"
echo ""
echo "Next: Create runbook files in runbooks/ directory, then upload them"
