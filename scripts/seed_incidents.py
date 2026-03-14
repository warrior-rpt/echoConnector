#!/usr/bin/env python3
import boto3
import random
import time
from datetime import datetime, timedelta

# Set up session
boto3.setup_default_session(profile_name='Hack', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('echo-incidents')

SERVICES = ['RDS', 'Lambda', 'ECS', 'ApiGateway', 'DynamoDB', 'S3']
SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
STATUSES = ['new', 'investigating', 'resolved', 'ignored']

def seed_data(count=15):
    print(f"Seeding {count} incidents into echo-incidents...")
    
    for i in range(count):
        service = random.choice(SERVICES)
        severity = random.choice(SEVERITIES)
        status = random.choice(STATUSES)
        
        # Random time in the last 24 hours
        offset = random.randint(0, 24 * 60)
        timestamp = (datetime.utcnow() - timedelta(minutes=offset))
        ts_iso = timestamp.isoformat() + 'Z'
        ts_unix = int(timestamp.timestamp())
        
        incident_id = f"INC-SEED-{ts_unix}-{i}"
        
        item = {
            'incidentId': incident_id,
            'timestamp': ts_iso,
            'severity': severity,
            'status': status,
            'service': service,
            'resource': f"test-resource-{i}",
            'alarmName': f"alarm-{service.lower()}-test",
            'createdAt': ts_unix,
            'updatedAt': ts_unix
        }
        
        if status == 'resolved':
            item['resolvedAt'] = ts_unix + random.randint(300, 3600)
            
        table.put_item(Item=item)
    
    print("Seeding complete!")

if __name__ == "__main__":
    seed_data()
