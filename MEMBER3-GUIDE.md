# Member 3: Data & Storage Lead - Complete Guide

## 🎯 Your Mission
Build the data foundation for EchoConnector:
1. S3 bucket with runbooks
2. DynamoDB table for incidents
3. Lambda helper functions
4. Test everything end-to-end

---

## 📋 Prerequisites

### Required Tools
```bash
# Check you have these installed:
aws --version        # AWS CLI
python3 --version    # Python 3.9+
```

### AWS Permissions Needed
- S3: Create bucket, put/get objects
- DynamoDB: Create table, read/write items
- Lambda: Create/update functions
- IAM: Create roles (for Lambda)

---

## 🚀 Step-by-Step Implementation

### Step 1: Set Up S3 Bucket (15 minutes)

```bash
# Make script executable
chmod +x setup-s3-bucket.sh

# Run it
./setup-s3-bucket.sh

# IMPORTANT: Save the bucket name it prints!
# Example: echo-runbooks-1710172800
# You'll need this later
```

**What this does:**
- Creates S3 bucket with unique name
- Enables versioning
- Creates local directory structure

**Save this output:**
```
RUNBOOKS_BUCKET=echo-runbooks-XXXXXXXXXX
```

---

### Step 2: Create Sample Runbooks (Already Done!)

You already have 3 runbooks created:
- `runbooks/aws/rds/high-cpu.md`
- `runbooks/aws/lambda/high-errors.md`
- `runbooks/aws/ecs/task-failures.md`

**Upload them to S3:**
```bash
# Upload all runbooks
aws s3 sync runbooks/ s3://echo-runbooks-XXXXXXXXXX/

# Verify they were uploaded
aws s3 ls s3://echo-runbooks-XXXXXXXXXX/aws/ --recursive
```

**Expected output:**
```
aws/rds/high-cpu.md
aws/lambda/high-errors.md
aws/ecs/task-failures.md
```

---

### Step 3: Create DynamoDB Table (10 minutes)

```bash
# Make script executable
chmod +x setup-dynamodb-table.sh

# Run it
./setup-dynamodb-table.sh

# Wait for "Table created successfully"
```

**What this creates:**
- Table: `echo-incidents`
- Primary Key: `incidentId` (String)
- GSI: `severity-timestamp-index` (for queries)
- Billing: On-Demand (auto-scaling, no capacity planning!)

**Save this output:**
```
INCIDENTS_TABLE=echo-incidents
```

**Verify it worked:**
```bash
# Check table exists
aws dynamodb describe-table --table-name echo-incidents

# Should show: TableStatus: "ACTIVE"
```

---

### Step 4: Test Data Helper Functions (20 minutes)

The file `lambda/data_helpers.py` contains all your core functions.

**Set environment variables first:**
```bash
# Replace XXXXXXXXXX with your actual bucket name
export RUNBOOKS_BUCKET=echo-runbooks-XXXXXXXXXX
export INCIDENTS_TABLE=echo-incidents
```

**Test the functions:**
```bash
cd lambda
python3 data_helpers.py
```

**Expected output:**
```
🧪 Testing Data Layer Functions...

Test 1: List all runbooks
   Found: 3 runbooks

Test 2: Get RDS high-cpu runbook
   ✅ Retrieved runbook (XXXX characters)

Test 3: Auto-detect runbook from alarm
   Detected runbook: Found

Test 4: Determine severity
   Severity: HIGH

Test 5: Save test incident
   ✅ Saved: INC-20260311-142230

Test 6: Retrieve incident
   ✅ Retrieved: INC-20260311-142230

Test 7: Update incident status
   ✅ Status updated

Test 8: Query incidents by severity
   Found: 1 HIGH incidents

✅ All tests complete!
```

**If you see errors:**
- Check AWS credentials: `aws sts get-caller-identity`
- Verify bucket name is correct
- Verify table name is correct

---

### Step 5: Deploy Lambda Function (30 minutes)

**Create Lambda IAM role:**
```bash
# Create trust policy
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name EchoWatchmanRole \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Attach basic Lambda execution policy
aws iam attach-role-policy \
  --role-name EchoWatchmanRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

**Create custom policy for EchoConnector:**
```bash
cat > /tmp/echo-policy.json << 'EOF'
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
        "arn:aws:s3:::echo-runbooks-*",
        "arn:aws:s3:::echo-runbooks-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/echo-incidents*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:echo/*"
    }
  ]
}
EOF

# Create and attach policy
aws iam create-policy \
  --policy-name EchoConnectorPolicy \
  --policy-document file:///tmp/echo-policy.json

# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Attach policy to role
aws iam attach-role-policy \
  --role-name EchoWatchmanRole \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/EchoConnectorPolicy
```

**Create deployment package:**
```bash
cd lambda

# Create package directory
mkdir -p package

# Install dependencies (if needed later)
# pip install requests -t package/

# Copy your code
cp data_helpers.py package/
cp watchman_lambda.py package/

# Create ZIP
cd package
zip -r ../watchman-function.zip .
cd ..

# Verify ZIP contents
unzip -l watchman-function.zip
```

**Deploy Lambda function:**
```bash
# IMPORTANT: Replace XXXXXXXXXX with your actual bucket name!
aws lambda create-function \
  --function-name echo-watchman \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/EchoWatchmanRole \
  --handler watchman_lambda.lambda_handler \
  --zip-file fileb://watchman-function.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment "Variables={
    RUNBOOKS_BUCKET=echo-runbooks-XXXXXXXXXX,
    INCIDENTS_TABLE=echo-incidents,
    SLACK_WEBHOOK_SECRET=echo/slack-webhook
  }"
```

**Verify deployment:**
```bash
aws lambda get-function --function-name echo-watchman
```

---

### Step 6: Create Test Alarm (10 minutes)

**Create a test CloudWatch alarm:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name echo-test-rds-high-cpu \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --period 60 \
  --statistic Average \
  --threshold 80.0 \
  --actions-enabled false \
  --alarm-description "EchoConnector test alarm for demo" \
  --dimensions Name=DBInstanceIdentifier,Value=test-database-prod
```

**Verify alarm created:**
```bash
aws cloudwatch describe-alarms --alarm-names echo-test-rds-high-cpu
```

---

### Step 7: End-to-End Test! (15 minutes)

**Trigger the test alarm:**
```bash
aws cloudwatch set-alarm-state \
  --alarm-name echo-test-rds-high-cpu \
  --state-value ALARM \
  --state-reason "Manual trigger for EchoConnector demo"
```

**Invoke Lambda manually:**
```bash
aws lambda invoke \
  --function-name echo-watchman \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  response.json | base64 -d

# View response
cat response.json
```

**Expected response:**
```json
{
  "statusCode": 200,
  "body": "{\"status\":\"incidents_detected\",\"count\":1,\"incidents\":[\"INC-20260311-142530\"]}"
}
```

**Check DynamoDB to verify incident was saved:**
```bash
# Get the incident ID from response above
aws dynamodb get-item \
  --table-name echo-incidents \
  --key '{"incidentId":{"S":"INC-20260311-142530"}}'
```

**You should see:**
- Incident saved in DynamoDB ✅
- Runbook was retrieved from S3 ✅
- AI analysis included ✅
- Severity determined automatically ✅

**Reset the alarm:**
```bash
aws cloudwatch set-alarm-state \
  --alarm-name echo-test-rds-high-cpu \
  --state-value OK \
  --state-reason "Test complete"
```

---

## 📊 Verification Checklist

After completing all steps, verify:

- [ ] S3 bucket created
- [ ] 3 runbooks uploaded to S3
- [ ] DynamoDB table created
- [ ] Table has GSI for severity queries
- [ ] Lambda function deployed
- [ ] Lambda has correct environment variables
- [ ] Lambda has correct IAM permissions
- [ ] Test alarm created
- [ ] End-to-end test successful
- [ ] Incident saved in DynamoDB
- [ ] Can query incidents by severity

---

## 🐛 Troubleshooting

### "AccessDenied" error on S3
```bash
# Check bucket policy
aws s3api get-bucket-policy --bucket echo-runbooks-XXXXXXXXXX

# Fix: Add Lambda execution role to bucket policy
```

### "ResourceNotFoundException" on DynamoDB
```bash
# Verify table exists
aws dynamodb list-tables

# Check region
aws configure get region
```

### Lambda can't find runbook
```bash
# Check environment variable
aws lambda get-function-configuration --function-name echo-watchman

# Verify runbooks exist in S3
aws s3 ls s3://echo-runbooks-XXXXXXXXXX/aws/rds/
```

### Bedrock "AccessDenied"
```bash
# Enable Bedrock in your region (one-time setup)
# Go to: AWS Console → Bedrock → Model access → Enable Claude
```

---

## 📦 Deliverables for Team

**Hand off to other team members:**

1. **To Member 1 (Watchman Lead):**
   - `RUNBOOKS_BUCKET` environment variable
   - `INCIDENTS_TABLE` environment variable
   - `get_relevant_runbook()` function
   - `save_incident()` function

2. **To Member 2 (Bedrock Lead):**
   - Sample runbook format
   - Runbook S3 key structure
   - How to call `get_relevant_runbook(alarm_data)`

3. **To Member 4 (Slack Lead):**
   - Incident data schema in DynamoDB
   - How to query incidents: `query_incidents_by_severity()`

4. **To Member 5 (Presentation Lead):**
   - S3 bucket name for demo
   - DynamoDB table name
   - Test alarm name: `echo-test-rds-high-cpu`
   - Commands to trigger/reset test alarm

---

## 🎯 Success Criteria

You're done when:
1. ✅ S3 bucket has 3+ runbooks
2. ✅ DynamoDB table stores incidents
3. ✅ Lambda function can read runbooks
4. ✅ Lambda function can save incidents
5. ✅ End-to-end test passes
6. ✅ Team members have all the info they need

---

## 🚀 Next Steps

**Day 2:**
- Add 2 more runbooks (API Gateway, DynamoDB)
- Optimize DynamoDB queries
- Add incident status transitions

**Day 3:**
- Help team integrate your functions
- Test with real CloudWatch alarms
- Performance testing

**Day 4:**
- Final polish
- Documentation
- Support demo preparation

---

## 📞 Need Help?

**Common Questions:**

Q: How do I test without triggering real alarms?
A: Use the test alarm creation script, manually set state to ALARM

Q: How do I update a runbook?
A: Edit the .md file locally, run `aws s3 sync runbooks/ s3://BUCKET/`

Q: How do I see what's in DynamoDB?
A: `aws dynamodb scan --table-name echo-incidents --max-items 10`

Q: Can I use a different region?
A: Yes! Just change `--region` in all commands consistently

---

**You've got this! 🎉**

All the code is written, tested, and ready to deploy. Just follow the steps one by one.
