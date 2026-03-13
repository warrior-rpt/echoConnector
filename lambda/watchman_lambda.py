"""
watchman_lambda.py
Complete Production Watchman Lambda function

This demonstrates end-to-end flow:
1. Poll CloudWatch alarms
2. Get runbook from S3 (using Member 3's functions)
3. Call Bedrock for analysis (using Member 2's functions)
4. Save to DynamoDB (using Member 3's functions)
5. Send to Slack (using Member 4's functions)
"""

import json
import boto3
import os
from datetime import datetime
from typing import Dict, List

# Import Member 3's data helper functions
from data_helpers import (
    get_relevant_runbook,
    save_incident,
    determine_severity
)

# AWS clients
cloudwatch = boto3.client('cloudwatch')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
secrets = boto3.client('secretsmanager')

# Environment variables
SLACK_WEBHOOK_SECRET = os.environ.get('SLACK_WEBHOOK_SECRET', 'echo/slack-webhook')


def lambda_handler(event, context):
    """
    Main Lambda handler - Production Watchman
    Triggered by EventBridge every 60 seconds
    """
    print("Production Watchman - Starting scan...")
    
    try:
        # Step 1: Poll CloudWatch alarms
        alarms = get_firing_alarms()
        
        if not alarms:
            print("No alarms firing - all systems normal")
            return {
                'statusCode': 200,
                'body': json.dumps({'status': 'healthy', 'incidents': 0})
            }
        
        print(f"Found {len(alarms)} firing alarm(s)")
        
        # Step 2: Process each alarm
        incidents_processed = []
        
        for alarm in alarms:
            incident_id = process_alarm(alarm)
            if incident_id:
                incidents_processed.append(incident_id)
        
        print(f"Processed {len(incidents_processed)} incident(s)")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'incidents_detected',
                'count': len(incidents_processed),
                'incidents': incidents_processed
            })
        }
        
    except Exception as e:
        print(f"Error in Watchman: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def get_firing_alarms() -> List[Dict]:
    """
    Poll CloudWatch for alarms in ALARM state
    
    Returns:
        List of alarm data dictionaries
    """
    try:
        response = cloudwatch.describe_alarms(StateValue='ALARM')
        alarms = response.get('MetricAlarms', [])
        
        print(f"CloudWatch returned {len(alarms)} alarms")
        return alarms
        
    except Exception as e:
        print(f"Error polling CloudWatch: {str(e)}")
        return []


def process_alarm(alarm: Dict) -> str:
    """
    Process a single alarm:
    1. Get relevant runbook
    2. Call Bedrock for analysis
    3. Save to DynamoDB
    4. Send Slack notification
    
    Args:
        alarm: CloudWatch alarm data
    
    Returns:
        Incident ID or None if failed
    """
    alarm_name = alarm.get('AlarmName', 'Unknown')
    print(f"\nProcessing alarm: {alarm_name}")
    
    try:
        # Step 1: Get relevant runbook from S3
        # (Using Member 3's function)
        print("  Fetching runbook from S3...")
        runbook_context = get_relevant_runbook(alarm)
        
        if runbook_context:
            print(f"  Got runbook ({len(runbook_context)} chars)")
        else:
            print("  No runbook found, using generic analysis")
            runbook_context = "No specific runbook available for this alarm type."
        
        # Step 2: Call Bedrock for AI analysis
        # (This would use Member 2's function in real implementation)
        print("  Calling Bedrock for analysis...")
        ai_analysis = analyze_with_bedrock(alarm, runbook_context)
        print(f"  Bedrock analysis complete")
        
        # Step 3: Determine severity
        # (Using Member 3's function)
        severity = determine_severity(alarm)
        print(f"  Severity: {severity}")
        
        # Step 4: Save to DynamoDB
        # (Using Member 3's function)
        print("  Saving incident to DynamoDB...")
        incident_id = save_incident(alarm, ai_analysis, severity)
        print(f"  Saved: {incident_id}")
        
        # Step 5: Send Slack notification
        # (This would use Member 4's function in real implementation)
        print("  Sending Slack notification...")
        send_slack_notification(incident_id, alarm, ai_analysis, severity)
        print(f"  Notification sent")
        
        return incident_id
        
    except Exception as e:
        print(f"  Error processing alarm {alarm_name}: {str(e)}")
        return None


def analyze_with_bedrock(alarm: Dict, runbook_context: str) -> Dict:
    """
    Call Bedrock to analyze the incident
    
    This is a simplified version - Member 2 will build the full implementation
    
    Args:
        alarm: CloudWatch alarm data
        runbook_context: Runbook text from S3
    
    Returns:
        Analysis dictionary
    """
    # Build prompt
    prompt = f"""You are EchoConnector's incident analyzer. A CloudWatch alarm has fired.

ALARM DETAILS:
- Name: {alarm.get('AlarmName')}
- Service: {alarm.get('Namespace')}
- Metric: {alarm.get('MetricName')}
- Threshold: {alarm.get('Threshold')}
- Current State: {alarm.get('StateValue')}
- Reason: {alarm.get('StateReason', 'N/A')}

RUNBOOK CONTEXT:
{runbook_context[:2000]}  # Limit context to 2000 chars

Provide a JSON response with:
1. root_cause: 2-3 sentence explanation
2. impact: How this affects users/business
3. confidence: low/medium/high
4. suggested_fixes: Array of 2 fixes, each with:
   - title: Short description
   - steps: Array of commands/actions
   - expected_result: What should happen
   - risk: low/medium/high
   - confidence: low/medium/high

Respond ONLY with valid JSON, no markdown formatting.
"""
    
    try:
        # Call Bedrock using the new Inference Profile ID
        response = bedrock.invoke_model(
            modelId='global.anthropic.claude-sonnet-4-6',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [{
                    "role": "user",
                    "content": prompt
                }]
            })
        )
        
        # Parse response
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        
        # Parse JSON from response (remove any markdown formatting)
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        
        analysis = json.loads(content)
        return analysis
        
    except Exception as e:
        print(f"Bedrock error: {str(e)}")
        # Return fallback analysis
        return {
            'root_cause': f"Alarm {alarm.get('AlarmName')} triggered due to {alarm.get('MetricName')} exceeding threshold",
            'impact': 'Service degradation possible',
            'confidence': 'medium',
            'suggested_fixes': [
                {
                    'title': 'Investigate in AWS Console',
                    'steps': ['Open CloudWatch', 'Review metrics', 'Check logs'],
                    'expected_result': 'Identify root cause',
                    'risk': 'low',
                    'confidence': 'high'
                }
            ]
        }


def send_slack_notification(
    incident_id: str,
    alarm: Dict,
    analysis: Dict,
    severity: str
):
    """
    Send notification to Slack
    
    This is a simplified version - Member 4 will build the full implementation
    
    Args:
        incident_id: Incident ID
        alarm: CloudWatch alarm data
        analysis: Bedrock analysis
        severity: Incident severity
    """
    try:
        # Get webhook URL from Secrets Manager
        secret_response = secrets.get_secret_value(SecretId=SLACK_WEBHOOK_SECRET)
        webhook_url = secret_response['SecretString']
        
        # Build simple message (Member 4 will make this fancy)
        severity_label = {
            'CRITICAL': '[CRITICAL]',
            'HIGH': '[HIGH]',
            'MEDIUM': '[MEDIUM]',
            'LOW': '[LOW]'
        }
        
        message = {
            'text': f"{severity_label.get(severity, '[INCIDENT]')} {severity} Incident Detected",
            'blocks': [
                {
                    'type': 'header',
                    'text': {
                        'type': 'plain_text',
                        'text': f"{severity_label.get(severity)} {severity} INCIDENT"
                    }
                },
                {
                    'type': 'section',
                    'fields': [
                        {'type': 'mrkdwn', 'text': f"*Incident:*\n{incident_id}"},
                        {'type': 'mrkdwn', 'text': f"*Service:*\n{alarm.get('Namespace')}"},
                        {'type': 'mrkdwn', 'text': f"*Alarm:*\n{alarm.get('AlarmName')}"},
                        {'type': 'mrkdwn', 'text': f"*Time:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"}
                    ]
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"*Root Cause:*\n{analysis.get('root_cause', 'Analyzing...')}"
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"*Suggested Fix:*\n{analysis.get('suggested_fixes', [{}])[0].get('title', 'See runbook')}"
                    }
                }
            ]
        }
        
        # Send to Slack (would use requests library in real implementation)
        # For now, just log it
        print(f"  Would send to Slack: {webhook_url[:30]}...")
        print(f"  Message: {json.dumps(message, indent=2)}")
        
    except Exception as e:
        print(f"  Slack notification error: {str(e)}")


# ============================================================================
# TESTING FUNCTIONS
# ============================================================================

def create_test_alarm():
    """
    Create a test CloudWatch alarm for testing
    """
    try:
        cloudwatch.put_metric_alarm(
            AlarmName='echo-test-high-cpu',
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=1,
            MetricName='CPUUtilization',
            Namespace='AWS/RDS',
            Period=60,
            Statistic='Average',
            Threshold=80.0,
            ActionsEnabled=False,
            AlarmDescription='EchoConnector test alarm',
            Dimensions=[
                {
                    'Name': 'DBInstanceIdentifier',
                    'Value': 'test-database-prod'
                }
            ]
        )
        print("Test alarm created: echo-test-high-cpu")
        return True
    except Exception as e:
        print(f"Error creating test alarm: {str(e)}")
        return False


def trigger_test_alarm():
    """
    Trigger the test alarm for demo purposes
    """
    try:
        cloudwatch.set_alarm_state(
            AlarmName='echo-test-high-cpu',
            StateValue='ALARM',
            StateReason='Manual trigger for EchoConnector demo'
        )
        print("Test alarm triggered!")
        print("   Run the Lambda function now to see it detect the alarm")
        return True
    except Exception as e:
        print(f"Error triggering alarm: {str(e)}")
        return False


def reset_test_alarm():
    """
    Reset the test alarm back to OK state
    """
    try:
        cloudwatch.set_alarm_state(
            AlarmName='echo-test-high-cpu',
            StateValue='OK',
            StateReason='Reset after demo'
        )
        print("Test alarm reset to OK")
        return True
    except Exception as e:
        print(f"Error resetting alarm: {str(e)}")
        return False


# For local testing
if __name__ == '__main__':
    print("EchoConnector Watchman - Local Test\n")
    
    # Simulate Lambda invocation
    event = {}
    context = None
    
    result = lambda_handler(event, context)
    print(f"\nResult: {json.dumps(result, indent=2)}")
