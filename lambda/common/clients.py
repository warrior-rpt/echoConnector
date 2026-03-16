import boto3
import os

# Get region from env or default to us-east-1
REGION = os.environ.get('AWS_REGION', 'us-east-1')

def get_cloudwatch_client():
    return boto3.client('cloudwatch', region_name=REGION)

def get_bedrock_client():
    return boto3.client('bedrock-runtime', region_name='us-east-1')

def get_secrets_client():
    return boto3.client('secretsmanager', region_name=REGION)

def get_s3_client():
    return boto3.client('s3', region_name=REGION)

def get_dynamodb_resource():
    return boto3.resource('dynamodb', region_name=REGION)
