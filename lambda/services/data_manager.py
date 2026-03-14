import boto3
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
from common.clients import get_s3_client, get_dynamodb_resource, get_bedrock_client
from config.environment import RUNBOOKS_BUCKET, INCIDENTS_TABLE_NAME

class DataManager:
    @staticmethod
    def get_runbook(alarm: Dict) -> Optional[str]:
        """Fetch runbook from S3 based on alarm namespace/metric"""
        s3 = get_s3_client()
        namespace = alarm.get('Namespace', 'AWS/Generic').lower().replace('aws/', '')
        metric = alarm.get('MetricName', 'default').lower().replace(' ', '-')
        
        # Try specific runbook
        key = f"{namespace}/{metric}.md"
        try:
            response = s3.get_object(Bucket=RUNBOOKS_BUCKET, Key=key)
            return response['Body'].read().decode('utf-8')
        except Exception:
            # Fallback to service default
            try:
                response = s3.get_object(Bucket=RUNBOOKS_BUCKET, Key=f"{namespace}/default.md")
                return response['Body'].read().decode('utf-8')
            except Exception:
                return None

    @staticmethod
    def save_incident(alarm: Dict, analysis: Dict, severity: str) -> str:
        """Persist incident to DynamoDB"""
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(INCIDENTS_TABLE_NAME)
        
        incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')}"
        incident = {
            'incidentId': incident_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'severity': severity,
            'status': 'new',
            'service': alarm.get('Namespace', 'Unknown').replace('AWS/', ''),
            'alarmName': alarm.get('AlarmName', 'Unknown'),
            'aiAnalysis': analysis,
            'createdAt': int(datetime.utcnow().timestamp()),
            'updatedAt': int(datetime.utcnow().timestamp())
        }
        
        table.put_item(Item=incident)
        return incident_id

    @staticmethod
    def batch_get_incidents(incident_ids: List[str]) -> List[Dict]:
        """Fetch multiple incidents using single BatchGet (10x faster)"""
        if not incident_ids: return []
        dynamodb = get_dynamodb_resource()
        keys = [{'incidentId': inc_id} for inc_id in incident_ids[:100]]
        try:
            response = dynamodb.batch_get_item(RequestItems={INCIDENTS_TABLE_NAME: {'Keys': keys}})
            return response.get('Responses', {}).get(INCIDENTS_TABLE_NAME, [])
        except Exception as e:
            print(f"Batch get error: {e}")
            return []

    @staticmethod
    def query_incidents_with_pagination(severity: str, limit: int = 20, last_key: Optional[Dict] = None) -> Dict:
        """Paginated query by severity"""
        table = get_dynamodb_resource().Table(INCIDENTS_TABLE_NAME)
        try:
            kwargs = {
                'IndexName': 'severity-timestamp-index',
                'KeyConditionExpression': Key('severity').eq(severity),
                'ScanIndexForward': False,
                'Limit': limit
            }
            if last_key: kwargs['ExclusiveStartKey'] = last_key
            response = table.query(**kwargs)
            items = response.get('Items', [])
            lek = response.get('LastEvaluatedKey')
            return {'items': items, 'count': len(items), 'has_more': lek is not None, 'last_evaluated_key': lek}
        except Exception as e:
            print(f"Paginated query error: {e}")
            return {'items': [], 'count': 0, 'has_more': False, 'last_evaluated_key': None}

    @staticmethod
    def transition_incident_status(incident_id: str, new_status: str, notes: Optional[str] = None) -> bool:
        """State machine for incident status transitions"""
        table = get_dynamodb_resource().Table(INCIDENTS_TABLE_NAME)
        transitions = {'new': ['investigating', 'resolved', 'ignored'], 'investigating': ['resolved', 'ignored', 'new'], 'resolved': ['investigating', 'new'], 'ignored': ['new', 'investigating']}
        try:
            incident = table.get_item(Key={'incidentId': incident_id}).get('Item')
            if not incident: return False
            current_status = incident.get('status', 'new')
            if new_status not in transitions.get(current_status, []): return False
            
            update_expr = "SET #status = :s, updatedAt = :u"
            vals = {":s": new_status, ":u": int(datetime.utcnow().timestamp())}
            if notes:
                update_expr += ", resolutionNotes = :n"
                vals[":n"] = notes
            if new_status == 'resolved':
                update_expr += ", resolvedAt = :r"
                vals[":r"] = int(datetime.utcnow().timestamp())
                
            table.update_item(Key={'incidentId': incident_id}, UpdateExpression=update_expr, ExpressionAttributeNames={"#status": "status"}, ExpressionAttributeValues=vals)
            return True
        except Exception as e:
            print(f"Transition error: {e}")
            return False

    @staticmethod
    def get_incident_statistics(hours: int = 24) -> Dict:
        """Consolidated statistics for dashboarding"""
        table = get_dynamodb_resource().Table(INCIDENTS_TABLE_NAME)
        threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + 'Z'
        stats = {'total_count': 0, 'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}, 'avg_resolution_time_minutes': 0.0}
        total_sec, resolved_count = 0.0, 0
        try:
            for sev in stats['by_severity'].keys():
                resp = table.query(IndexName='severity-timestamp-index', KeyConditionExpression=Key('severity').eq(sev) & Key('timestamp').gt(threshold))
                items = resp.get('Items', [])
                stats['by_severity'][sev] = len(items)
                stats['total_count'] += len(items)
                for item in items:
                    if item.get('status') == 'resolved' and 'resolvedAt' in item and 'createdAt' in item:
                        total_sec += float(item['resolvedAt'] - item['createdAt'])
                        resolved_count += 1
            if resolved_count > 0:
                stats['avg_resolution_time_minutes'] = round((total_sec / resolved_count) / 60.0, 2)
            return stats
        except Exception as e:
            print(f"Stats error: {e}")
            return stats

    @staticmethod
    def determine_severity(alarm: Dict) -> str:
        """Simple logic to determine severity"""
        name = alarm.get('AlarmName', '').upper()
        if any(w in name for w in ['CRIT', 'FATAL', 'URGENT']): return 'CRITICAL'
        if any(w in name for w in ['WARN', 'HIGH', 'ERROR']): return 'HIGH'
        return 'MEDIUM'
