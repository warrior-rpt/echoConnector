import json
from datetime import datetime
from typing import Dict
from config.environment import Config

class SlackService:
    @staticmethod
    def send_notification(incident_id: str, alarm: Dict, analysis: Dict, severity: str):
        webhook_url = Config.get_slack_webhook()
        if not webhook_url:
            print("Slack webhook not configured, skipping notification.")
            return

        message = {
            'text': f"[{severity}] Incident Detected: {incident_id}",
            'blocks': [
                {
                    'type': 'header',
                    'text': {'type': 'plain_text', 'text': f"🚨 {severity} INCIDENT"}
                },
                {
                    'type': 'section',
                    'fields': [
                        {'type': 'mrkdwn', 'text': f"*Incident:*\n{incident_id}"},
                        {'type': 'mrkdwn', 'text': f"*Alarm:*\n{alarm.get('AlarmName')}"}
                    ]
                },
                {
                    'type': 'section',
                    'text': {'type': 'mrkdwn', 'text': f"*Root Cause:*\n{analysis.get('root_cause', 'N/A')}"}
                }
            ]
        }
        
        # Log instead of request for now as per original code pattern
        print(f"Propagating to Slack: {webhook_url[:15]}...")
        print(json.dumps(message, indent=2))
