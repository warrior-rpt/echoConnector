from typing import List, Dict
from common.clients import get_cloudwatch_client

class CloudWatchService:
    @staticmethod
    def get_firing_alarms() -> List[Dict]:
        """Poll CloudWatch for alarms in ALARM state"""
        client = get_cloudwatch_client()
        try:
            response = client.describe_alarms(StateValue='ALARM')
            return response.get('MetricAlarms', [])
        except Exception as e:
            print(f"Error polling CloudWatch: {e}")
            return []

    @staticmethod
    def set_alarm_state(alarm_name: str, state: str, reason: str):
        """Set state for testing purposes"""
        client = get_cloudwatch_client()
        try:
            client.set_alarm_state(
                AlarmName=alarm_name,
                StateValue=state,
                StateReason=reason
            )
            return True
        except Exception as e:
            print(f"Error setting alarm state: {e}")
            return False
