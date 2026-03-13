"""
data_helpers.py
Lambda helper functions for S3 runbooks and DynamoDB incidents

This is Member 3's core contribution - data layer functions
"""

import json
import boto3
from datetime import datetime
from typing import Dict, List, Optional

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables (set these in Lambda configuration)
import os
RUNBOOKS_BUCKET = os.environ.get('RUNBOOKS_BUCKET', 'echo-runbooks-xxxxx')
INCIDENTS_TABLE = os.environ.get('INCIDENTS_TABLE', 'echo-incidents')

# Get DynamoDB table
incidents_table = dynamodb.Table(INCIDENTS_TABLE)


# ============================================================================
# S3 RUNBOOK FUNCTIONS
# ============================================================================

def get_runbook(service: str, problem: str) -> Optional[str]:
    """
    Retrieve runbook from S3 based on service and problem type
    
    Args:
        service: AWS service (e.g., 'rds', 'lambda', 'ecs')
        problem: Problem type (e.g., 'high-cpu', 'high-errors')
    
    Returns:
        Runbook content as string, or None if not found
    
    Example:
        runbook = get_runbook('rds', 'high-cpu')
    """
    key = f"aws/{service}/{problem}.md"
    
    try:
        response = s3.get_object(Bucket=RUNBOOKS_BUCKET, Key=key)
        runbook_content = response['Body'].read().decode('utf-8')
        
        print(f"Retrieved runbook: {key}")
        return runbook_content
        
    except s3.exceptions.NoSuchKey:
        print(f"Runbook not found: {key}")
        return None
    except Exception as e:
        print(f"Error retrieving runbook: {str(e)}")
        return None


def get_relevant_runbook(alarm_data: Dict) -> Optional[str]:
    """
    Automatically determine and retrieve relevant runbook based on alarm data
    
    Args:
        alarm_data: CloudWatch alarm data
    
    Returns:
        Runbook content or None
    
    Example:
        alarm = {
            'Namespace': 'AWS/RDS',
            'AlarmName': 'rds-high-cpu'
        }
        runbook = get_relevant_runbook(alarm)
    """
    # Extract service from namespace
    namespace = alarm_data.get('Namespace', '')
    service = namespace.replace('AWS/', '').lower()
    
    # Determine problem type from alarm name
    alarm_name = alarm_data.get('AlarmName', '').lower()
    
    # Simple keyword matching
    if 'cpu' in alarm_name:
        problem = 'high-cpu'
    elif 'error' in alarm_name or 'fail' in alarm_name:
        problem = 'high-errors'
    elif 'memory' in alarm_name or 'oom' in alarm_name:
        problem = 'task-failures'
    else:
        problem = 'general'
    
    return get_runbook(service, problem)


def list_all_runbooks() -> List[str]:
    """
    List all available runbooks in S3
    
    Returns:
        List of runbook S3 keys
    """
    try:
        response = s3.list_objects_v2(Bucket=RUNBOOKS_BUCKET, Prefix='aws/')
        
        if 'Contents' not in response:
            return []
        
        runbooks = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.md')]
        print(f"Found {len(runbooks)} runbooks")
        return runbooks
        
    except Exception as e:
        print(f"Error listing runbooks: {str(e)}")
        return []


# ============================================================================
# DYNAMODB INCIDENT FUNCTIONS
# ============================================================================

def save_incident(
    alarm_data: Dict,
    ai_analysis: Dict,
    severity: str = 'MEDIUM'
) -> str:
    """
    Save incident to DynamoDB
    
    Args:
        alarm_data: CloudWatch alarm data
        ai_analysis: Bedrock analysis result
        severity: CRITICAL, HIGH, MEDIUM, LOW
    
    Returns:
        Incident ID
    
    Example:
        incident_id = save_incident(
            alarm_data=alarm,
            ai_analysis=bedrock_response,
            severity='CRITICAL'
        )
    """
    # Generate incident ID
    incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    
    # Extract key information
    service = alarm_data.get('Namespace', 'Unknown').replace('AWS/', '')
    resource = 'Unknown'
    if alarm_data.get('Dimensions'):
        resource = alarm_data['Dimensions'][0].get('Value', 'Unknown')
    
    # Build incident record
    incident = {
        'incidentId': incident_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'severity': severity,
        'status': 'new',
        
        # Service information
        'service': service,
        'resource': resource,
        'alarmName': alarm_data.get('AlarmName', 'Unknown'),
        'metricName': alarm_data.get('MetricName', 'Unknown'),
        
        # AI Analysis
        'aiAnalysis': ai_analysis,
        
        # Metadata
        'createdAt': int(datetime.utcnow().timestamp()),
        'updatedAt': int(datetime.utcnow().timestamp()),
    }
    
    try:
        incidents_table.put_item(Item=incident)
        print(f"Saved incident: {incident_id}")
        return incident_id
        
    except Exception as e:
        print(f"Error saving incident: {str(e)}")
        raise


def get_incident(incident_id: str) -> Optional[Dict]:
    """
    Retrieve incident by ID
    
    Args:
        incident_id: Incident ID to retrieve
    
    Returns:
        Incident data or None
    """
    try:
        response = incidents_table.get_item(Key={'incidentId': incident_id})
        return response.get('Item')
        
    except Exception as e:
        print(f"Error retrieving incident: {str(e)}")
        return None


def query_incidents_by_severity(
    severity: str,
    limit: int = 10
) -> List[Dict]:
    """
    Query incidents by severity level
    
    Args:
        severity: CRITICAL, HIGH, MEDIUM, LOW
        limit: Maximum number of incidents to return
    
    Returns:
        List of incidents
    
    Example:
        critical_incidents = query_incidents_by_severity('CRITICAL', limit=5)
    """
    try:
        response = incidents_table.query(
            IndexName='severity-timestamp-index',
            KeyConditionExpression='severity = :sev',
            ExpressionAttributeValues={':sev': severity},
            ScanIndexForward=False,  # Most recent first
            Limit=limit
        )
        
        incidents = response.get('Items', [])
        print(f"Found {len(incidents)} {severity} incidents")
        return incidents
        
    except Exception as e:
        print(f"Error querying incidents: {str(e)}")
        return []


def update_incident_status(incident_id: str, status: str) -> bool:
    """
    Update incident status
    
    Args:
        incident_id: Incident ID
        status: new, investigating, resolved, ignored
    
    Returns:
        True if successful
    """
    try:
        incidents_table.update_item(
            Key={'incidentId': incident_id},
            UpdateExpression='SET #status = :status, updatedAt = :updated',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': status,
                ':updated': int(datetime.utcnow().timestamp())
            }
        )
        print(f"Updated incident {incident_id} status to {status}")
        return True
        
    except Exception as e:
        print(f"Error updating incident: {str(e)}")
        return False


def get_recent_incidents(limit: int = 20) -> List[Dict]:
    """
    Get most recent incidents (all severities)
    
    Args:
        limit: Maximum number to return
    
    Returns:
        List of incidents sorted by timestamp (newest first)
    """
    try:
        response = incidents_table.scan(Limit=limit)
        incidents = response.get('Items', [])
        
        # Sort by timestamp (newest first)
        incidents.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        print(f"Retrieved {len(incidents)} recent incidents")
        return incidents[:limit]
        
    except Exception as e:
        print(f"Error scanning incidents: {str(e)}")
        return []


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def determine_severity(alarm_data: Dict) -> str:
    """
    Automatically determine incident severity based on alarm data
    
    Args:
        alarm_data: CloudWatch alarm data
    
    Returns:
        Severity level: CRITICAL, HIGH, MEDIUM, LOW
    """
    alarm_name = alarm_data.get('AlarmName', '').lower()
    metric_name = alarm_data.get('MetricName', '').lower()
    
    # CRITICAL conditions
    if 'critical' in alarm_name:
        return 'CRITICAL'
    if 'cpu' in metric_name or 'error' in metric_name:
        # Check threshold
        threshold = alarm_data.get('Threshold', 0)
        if threshold >= 90:
            return 'CRITICAL'
        elif threshold >= 70:
            return 'HIGH'
    
    # HIGH conditions
    if 'high' in alarm_name:
        return 'HIGH'
    if 'timeout' in alarm_name or 'latency' in metric_name:
        return 'HIGH'
    
    # MEDIUM (default)
    return 'MEDIUM'


def format_incident_summary(incident: Dict) -> str:
    """
    Format incident as human-readable summary
    
    Args:
        incident: Incident data from DynamoDB
    
    Returns:
        Formatted string
    """
    return f"""
Incident: {incident['incidentId']}
Severity: {incident['severity']}
Service: {incident['service']} ({incident['resource']})
Status: {incident['status']}
Time: {incident['timestamp']}
Alarm: {incident['alarmName']}
    """.strip()


# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_data_layer():
    """
    Test all data layer functions
    Run this to verify everything works
    """
    print("Testing Data Layer Functions...\n")
    
    # Test 1: List runbooks
    print("Test 1: List all runbooks")
    runbooks = list_all_runbooks()
    print(f"   Found: {len(runbooks)} runbooks\n")
    
    # Test 2: Get specific runbook
    print("Test 2: Get RDS high-cpu runbook")
    runbook = get_runbook('rds', 'high-cpu')
    if runbook:
        print(f"   Retrieved runbook ({len(runbook)} characters)\n")
    else:
        print("   Runbook not found\n")
    
    # Test 3: Get runbook based on alarm
    print("Test 3: Auto-detect runbook from alarm")
    test_alarm = {
        'Namespace': 'AWS/RDS',
        'AlarmName': 'rds-high-cpu',
        'MetricName': 'CPUUtilization',
        'Threshold': 80,
        'Dimensions': [{'Name': 'DBInstanceIdentifier', 'Value': 'test-db'}]
    }
    runbook = get_relevant_runbook(test_alarm)
    print(f"   Detected runbook: {'Found' if runbook else 'Not found'}\n")
    
    # Test 4: Determine severity
    print("Test 4: Determine severity")
    severity = determine_severity(test_alarm)
    print(f"   Severity: {severity}\n")
    
    # Test 5: Save test incident
    print("Test 5: Save test incident")
    test_analysis = {
        'root_cause': 'High CPU due to unindexed query',
        'impact': 'Slow response times',
        'confidence': 'high',
        'suggested_fixes': [
            {
                'title': 'Add database index',
                'steps': ['CREATE INDEX...'],
                'risk': 'low'
            }
        ]
    }
    
    try:
        incident_id = save_incident(test_alarm, test_analysis, severity)
        print(f"   Saved: {incident_id}\n")
        
        # Test 6: Retrieve incident
        print("Test 6: Retrieve incident")
        incident = get_incident(incident_id)
        if incident:
            print(f"   Retrieved: {incident['incidentId']}\n")
        
        # Test 7: Update status
        print("Test 7: Update incident status")
        update_incident_status(incident_id, 'resolved')
        print("   Status updated\n")
        
        # Test 8: Query by severity
        print("Test 8: Query incidents by severity")
        incidents = query_incidents_by_severity(severity, limit=5)
        print(f"   Found: {len(incidents)} {severity} incidents\n")
        
    except Exception as e:
        print(f"   Error: {str(e)}\n")
    
    print("All tests complete!")


if __name__ == '__main__':
    # Run tests if executed directly
    test_data_layer()
