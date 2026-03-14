import os
import json
from common.clients import get_secrets_client

# Environment Variable names
SLACK_WEBHOOK_SECRET_ID = os.environ.get('SLACK_WEBHOOK_SECRET', 'echo/slack-webhook')
AI_CONFIG_SECRET_ID = os.environ.get('AI_CONFIG_SECRET', 'echo/ai-config')
RUNBOOKS_BUCKET = os.environ.get('RUNBOOKS_BUCKET', 'echo-runbooks-xxxxx')
INCIDENTS_TABLE_NAME = os.environ.get('INCIDENTS_TABLE', 'echo-incidents')

class Config:
    _ai_config = None
    _slack_webhook = None

    @classmethod
    def get_ai_config(cls):
        if cls._ai_config is None:
            try:
                secrets = get_secrets_client()
                response = secrets.get_secret_value(SecretId=AI_CONFIG_SECRET_ID)
                cls._ai_config = json.loads(response['SecretString'])
            except Exception as e:
                print(f"Error fetching AI config: {e}")
                # Fallback structure but empty
                cls._ai_config = {"model_id": "", "anthropic_version": ""}
        return cls._ai_config

    @classmethod
    def get_slack_webhook(cls):
        if cls._slack_webhook is None:
            try:
                secrets = get_secrets_client()
                response = secrets.get_secret_value(SecretId=SLACK_WEBHOOK_SECRET_ID)
                cls._slack_webhook = response['SecretString']
            except Exception as e:
                print(f"Error fetching Slack webhook: {e}")
                cls._slack_webhook = ""
        return cls._slack_webhook
