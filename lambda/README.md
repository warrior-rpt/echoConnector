# Echo Watchman Lambda

This directory contains the enterprise-grade implementation of the **Echo Watchman** Lambda function. It is architected for scalability, modularity, and ease of maintenance during the hackathon.

## 🏗️ Project Structure

The project follows a modular service-oriented architecture:

```text
lambda/
├── watchman_lambda.py      # Clean entry point (Lambda Handler)
├── core/
│   └── engine.py           # Process orchestration & workflow logic
├── services/
│   ├── cloudwatch.py       # Alarm polling and management
│   ├── bedrock.py          # AI analysis via Bedrock
│   ├── slack.py            # Incident notifications
│   └── data_manager.py     # Unified DynamoDB & S3 data operations
├── config/
│   └── environment.py      # Env var & Secrets Manager management
└── common/
    └── clients.py          # Centralized AWS Client factory
```

## 🛠️ Components

- **`core/engine.py`**: The "brain" of the operation. It coordinates the flow between polling alarms, retrieving runbooks, generating AI analysis, and sending notifications.
- **`services/bedrock.py`**: Interfaces with Amazon Bedrock to provide intelligent incident analysis and suggested fixes.
- **`services/data_manager.py`**: Handles all persistent data operations, including fetching runbooks from S3 and saving incident logs to DynamoDB.
- **`config/environment.py`**: Centrally manages all configuration and secrets (Slack webhooks, AI model settings) with smart caching to optimize performance.
- **`common/clients.py`**: Ensures consistent AWS client initialization across all modules.

## 🚀 Deployment

There are two ways to deploy this Lambda. **SAM (Serverless Application Model)** is the preferred production method as it manages resources like EventBridge schedules and IAM policies automatically.

### 1. Production Deployment (Recommended)
Use AWS SAM to build and deploy the entire stack:

```bash
# Build the project (uses container to ensure compatibility)
sam build --use-container

# Deploy to AWS using a specific profile
sam deploy --profile YOUR_PROFILE_NAME
```

### 2. Manual/Development Script (Deprecated)
A lightweight script is provided for rapid code updates. **It now includes automatic integration testing** to ensure no regressions are pushed.

```bash
chmod +x deploy-lambda.sh

# Deploy using default 'Hack' profile (Includes Integration Tests!)
./deploy-lambda.sh
```

## 🧪 Integration Testing
A comprehensive integration suite is available in `scripts/test_integration.py`. It verifies:
- **Data Integrity**: Creation, batch retrieval, and querying of incidents.
- **State Machine**: Correct handling of status transitions and validation logic.
- **Analytics**: Verification of statistics generation and severity determination.

To run tests manually:
```bash
export AWS_PROFILE=YOUR_PROFILE
python3 scripts/test_integration.py
```

> [!WARNING]
> The manual script `deploy-lambda.sh` only updates the code of a pre-existing Lambda. It does not manage triggers, environment variables, or permissions. This method is kept **temporarily** for development speed and will be removed in favor of SAM.

The script:
1. Detects your AWS account and region.
2. Finds the active `echo-runbooks` S3 bucket.
3. Packages the modular directory structure.
4. Updates the Lambda code binary.

---
*Developed for the Hackathon 2026 - EchoConnector Project.*
