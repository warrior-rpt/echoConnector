import json
from typing import Dict
from common.clients import get_bedrock_client
from config.environment import Config

class BedrockService:
    @staticmethod
    def analyze_incident(alarm: Dict, runbook_context: str) -> Dict:
        """Call Bedrock to analyze the incident"""
        client = get_bedrock_client()
        ai_config = Config.get_ai_config()
        
        prompt = f"""You are EchoConnector's incident analyzer. A CloudWatch alarm has fired.

ALARM DETAILS:
- Name: {alarm.get('AlarmName')}
- Service: {alarm.get('Namespace')}
- Metric: {alarm.get('MetricName')}
- Threshold: {alarm.get('Threshold')}
- Current State: {alarm.get('StateValue')}
- Reason: {alarm.get('StateReason', 'N/A')}

RUNBOOK CONTEXT:
{runbook_context[:2000]}

Provide a JSON response with root_cause, impact, confidence, and suggested_fixes.
Respond ONLY with valid JSON.
"""
        
        try:
            response = client.invoke_model(
                modelId=ai_config['model_id'],
                body=json.dumps({
                    "anthropic_version": ai_config['anthropic_version'],
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            
            result = json.loads(response['body'].read())
            content = result['content'][0]['text'].strip()
            
            # Simple JSON cleaner
            if content.startswith('```json'): content = content[7:]
            if content.startswith('```'): content = content[3:]
            if content.endswith('```'): content = content[:-3]
            
            return json.loads(content.strip())
            
        except Exception as e:
            print(f"Bedrock error: {e}")
            return BedrockService._get_fallback_analysis(alarm)

    @staticmethod
    def _get_fallback_analysis(alarm: Dict) -> Dict:
        return {
            'root_cause': f"Alarm {alarm.get('AlarmName')} triggered.",
            'impact': 'Unknown impact',
            'confidence': 'low',
            'suggested_fixes': [{'title': 'Check console', 'steps': ['Review logs']}]
        }
