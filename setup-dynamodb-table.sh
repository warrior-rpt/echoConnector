#!/bin/bash
# setup-dynamodb-table.sh
# Creates DynamoDB table for storing incidents

set -e

echo "🗄️  Creating DynamoDB table for incidents..."

TABLE_NAME="echo-incidents"
REGION="us-east-1"

# Create table
aws dynamodb create-table \
    --table-name $TABLE_NAME \
    --attribute-definitions \
        AttributeName=incidentId,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
        AttributeName=severity,AttributeType=S \
    --key-schema \
        AttributeName=incidentId,KeyType=HASH \
    --global-secondary-indexes \
        "[
            {
                \"IndexName\": \"severity-timestamp-index\",
                \"KeySchema\": [
                    {\"AttributeName\":\"severity\",\"KeyType\":\"HASH\"},
                    {\"AttributeName\":\"timestamp\",\"KeyType\":\"RANGE\"}
                ],
                \"Projection\": {\"ProjectionType\":\"ALL\"}
            }
        ]" \
    --billing-mode PAY_PER_REQUEST \
    --region $REGION

echo "Waiting for table to be created..."
aws dynamodb wait table-exists --table-name $TABLE_NAME --region $REGION

echo ""
echo "✅ DynamoDB table created successfully!"
echo "📝 Table name: $TABLE_NAME"
echo "   Region: $REGION"
echo "   Billing mode: On-Demand (auto-scaling)"
echo ""
echo "Table schema:"
echo "  - Primary Key: incidentId (String)"
echo "  - GSI: severity-timestamp-index (for querying by severity)"
echo ""
echo "⚠️  Save this table name for Lambda environment variable:"
echo "   INCIDENTS_TABLE=$TABLE_NAME"
