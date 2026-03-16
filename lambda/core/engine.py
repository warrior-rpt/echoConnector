from typing import Dict, List
from services.cloudwatch import CloudWatchService
from services.bedrock import BedrockService
from services.slack import SlackService
from services.data_manager import DataManager

class WatchmanEngine:
    @staticmethod
    def run_scan() -> List[str]:
        """Polls alarms and processes any that are firing"""
        print("Starting Watchman scan...")
        alarms = CloudWatchService.get_firing_alarms()
        
        if not alarms:
            print("No alarms firing.")
            return []
        
        incidents = []
        for alarm in alarms:
            incident_id = WatchmanEngine.process_single_alarm(alarm)
            if incident_id:
                incidents.append(incident_id)
        
        return incidents

    @staticmethod
    def process_single_alarm(alarm: Dict) -> str:
        """Logic for processing a single alarm entity"""
        name = alarm.get('AlarmName', 'Unknown')
        print(f"Processing incident for: {name}")
        
        try:
            # 1. Runbook retrieval
            runbook = DataManager.get_runbook(alarm) or "No runbook found."
            
            # 2. AI Analysis
            analysis = BedrockService.analyze_incident(alarm, runbook)
            
            # 3. Severity
            severity = DataManager.determine_severity(alarm)
            
            # 4. Persistence
            incident_id = DataManager.save_incident(alarm, analysis, severity)
            
            # 5. Notification
            SlackService.send_notification(incident_id, alarm, analysis, severity)
            
            return incident_id
        except Exception as e:
            print(f"Failed to process alarm {name}: {e}")
            return None
