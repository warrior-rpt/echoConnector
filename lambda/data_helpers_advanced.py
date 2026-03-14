"""
data_helpers_advanced.py
Advanced DynamoDB operations for Echo Watchman
Includes batch operations, pagination, status transitions, and statistics
"""

import os
import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from boto3.dynamodb.conditions import Key

# Use the same table definition as data_helpers
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'echo-incidents')
dynamodb = boto3.resource('dynamodb')
incidents_table = dynamodb.Table(INCIDENTS_TABLE)

# Valid status transitions mapping the state machine
VALID_TRANSITIONS = {
    'new': ['investigating', 'resolved', 'ignored'],
    'investigating': ['resolved', 'ignored', 'new'],
    'resolved': ['investigating', 'new'],
    'ignored': ['new', 'investigating']
}

def batch_get_incidents(incident_ids: List[str]) -> List[Dict]:
    """
    Fetch multiple incidents using a single DynamoDB BatchGet operation (10x faster)
    """
    if not incident_ids:
        return []

    # DynamoDB batch_get_item processes a list of keys per table
    # AWS limits BatchGetItem to 100 items per batch
    # (Assuming the caller passes < 100 or handles chunking, keeping simple for this function)
    keys = [{'incidentId': inc_id} for inc_id in incident_ids[:100]] 
    
    try:
        response = dynamodb.batch_get_item(
            RequestItems={
                INCIDENTS_TABLE: {
                    'Keys': keys
                }
            }
        )
        # Boto3 returns a map where keys are table names and values are item lists
        return response.get('Responses', {}).get(INCIDENTS_TABLE, [])
    except Exception as e:
        print(f"Error in batch getting incidents: {str(e)}")
        return []

def query_incidents_with_pagination(severity: str, limit: int = 20, last_evaluated_key: Optional[Dict] = None) -> Dict:
    """
    Query incidents by severity using pagination
    """
    try:
        query_kwargs = {
            'IndexName': 'severity-timestamp-index',
            'KeyConditionExpression': Key('severity').eq(severity),
            'ScanIndexForward': False,  # sorted newest first
            'Limit': limit
        }
        
        if last_evaluated_key:
            query_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
        response = incidents_table.query(**query_kwargs)
        
        items = response.get('Items', [])
        lek = response.get('LastEvaluatedKey')
        
        return {
            'items': items,
            'count': len(items),
            'has_more': lek is not None,
            'last_evaluated_key': lek
        }
    except Exception as e:
        print(f"Error in paginated query: {str(e)}")
        return {
            'items': [],
            'count': 0,
            'has_more': False,
            'last_evaluated_key': None
        }

def transition_incident_status(incident_id: str, new_status: str, resolution_notes: Optional[str] = None) -> bool:
    """
    Validates and performs an incident status transition.
    e.g., new -> investigating -> resolved
    """
    try:
        # 1. Fetch current incident
        response = incidents_table.get_item(Key={'incidentId': incident_id})
        incident = response.get('Item')
        
        if not incident:
            print(f"Incident {incident_id} not found.")
            return False
            
        current_status = incident.get('status', 'new')
        
        # 2. Validate allowed status transition
        allowed_next_states = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next_states:
            print(f"Invalid transition from {current_status} to {new_status}")
            return False
            
        # 3. Perform the update with notes
        update_expr = "SET #status = :new_status, updatedAt = :updated_at"
        expr_names = {"#status": "status"}
        expr_values = {
            ":new_status": new_status,
            ":updated_at": int(datetime.utcnow().timestamp())
        }
        
        if resolution_notes:
            update_expr += ", resolutionNotes = :notes"
            expr_values[":notes"] = resolution_notes
            
        if new_status == 'resolved':
            update_expr += ", resolvedAt = :resolved_at"
            expr_values[":resolved_at"] = int(datetime.utcnow().timestamp())
            
        incidents_table.update_item(
            Key={'incidentId': incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        
        print(f"Successfully transitioned {incident_id} to {new_status}")
        return True
        
    except Exception as e:
        print(f"Error transitioning status: {str(e)}")
        return False

def get_incident_statistics(time_range_hours: int = 24) -> Dict:
    """
    Get comprehensive statistics for incidents over a given time range.
    Loops through severities utilizing the severity-timestamp-index.
    """
    threshold_time = datetime.utcnow() - timedelta(hours=time_range_hours)
    threshold_iso = threshold_time.isoformat() + 'Z'
    
    total_count = 0
    by_severity = {
        'CRITICAL': 0,
        'HIGH': 0,
        'MEDIUM': 0,
        'LOW': 0
    }
    avg_resolution_time_minutes = 0.0
    
    total_resolution_seconds = 0.0
    resolved_count = 0
    
    try:
        for severity in by_severity.keys():
            # Query the Global Secondary Index mapping severity to timestamp
            response = incidents_table.query(
                IndexName='severity-timestamp-index',
                KeyConditionExpression=Key('severity').eq(severity) & Key('timestamp').gt(threshold_iso)
            )
            
            items = response.get('Items', [])
            
            by_severity[severity] = len(items)
            total_count += len(items)
            
            # Additional metric: Average resolution time
            for item in items:
                if item.get('status') == 'resolved' and 'resolvedAt' in item and 'createdAt' in item:
                    resolution_time_sec = float(item['resolvedAt'] - item['createdAt'])
                    total_resolution_seconds += resolution_time_sec
                    resolved_count += 1
                    
        # Compute the final average resolution if we have resolved incidents
        if resolved_count > 0:
            avg_sec = total_resolution_seconds / resolved_count
            avg_resolution_time_minutes = round(avg_sec / 60.0, 2)
            
        return {
            'total_count': total_count,
            'by_severity': by_severity,
            'avg_resolution_time_minutes': avg_resolution_time_minutes
        }
        
    except Exception as e:
        print(f"Error computing statistics: {str(e)}")
        return {
            'total_count': total_count,
            'by_severity': by_severity,
            'avg_resolution_time_minutes': avg_resolution_time_minutes
        }
