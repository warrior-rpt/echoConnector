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

Use the included deployment script to package and push the enterprise structure to AWS:

```bash
chmod +x deploy-lambda.sh
./deploy-lambda.sh
```

The script automatically:
1. Detects your AWS account and region.
2. Finds the active `echo-runbooks` S3 bucket.
3. Packages the entire modular directory structure.
4. Updates the Lambda code and environment configuration.

---
*Developed for the Hackathon 2026 - EchoConnector Project.*
