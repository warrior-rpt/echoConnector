#!/usr/bin/env python3
"""
incident_dashboard.py
A CLI utility to view incident metrics running directly against DynamoDB or generating JSON.
"""

import os
import sys
import json
import boto3
import argparse
from datetime import datetime, timedelta
from collections import Counter

# Set up paths for local imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Note: Configuring session BEFORE importing data_helpers_advanced
# because it initializes a resource at the top level.
try:
    boto3.setup_default_session(profile_name='Hack', region_name='us-east-1')
except Exception:
    pass 

from data_helpers_advanced import get_incident_statistics, get_incidents_table
from boto3.dynamodb.conditions import Key

def draw_bar(count: int, total: int, max_width: int = 50) -> str:
    """Helper to draw a simple text-based progress bar."""
    if total == 0:
        return ""
    proportion = float(count) / float(total)
    num_blocks = int(round(proportion * max_width))
    return '█' * num_blocks

def fetch_detailed_metrics(time_range_hours: int) -> dict:
    """
    Combines the basic `get_incident_statistics` with deeper insights (status/service aggregations)
    for dashboarding.
    """
    # 1. Grab base statistics from data_helpers_advanced
    base_stats = get_incident_statistics(time_range_hours=time_range_hours)
    
    threshold_time = datetime.utcnow() - timedelta(hours=time_range_hours)
    threshold_iso = threshold_time.isoformat() + 'Z'
    
    # 2. Iterate manually through the same GSI mapping to calculate additional groupings
    status_counts = {'new': 0, 'investigating': 0, 'resolved': 0, 'ignored': 0}
    service_counter = Counter()
    unresolved_count = 0
    
    # Needs to loop since we're organizing by severity in our Global Secondary Index
    try:
        incidents_table = get_incidents_table()
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            response = incidents_table.query(
                IndexName='severity-timestamp-index',
                KeyConditionExpression=Key('severity').eq(severity) & Key('timestamp').gt(threshold_iso)
            )
            for item in response.get('Items', []):
                # Count status
                status = item.get('status', 'new')
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts[status] = 1
                
                if status != 'resolved' and status != 'ignored':
                    unresolved_count += 1
                
                # Count services
                service_counter[item.get('service', 'Unknown')] += 1
                
    except Exception as e:
        print(f"Error querying DynamoDB in dashboard: {str(e)}", file=sys.stderr)
        
    base_stats['unresolved_count'] = unresolved_count
    base_stats['by_status'] = status_counts
    base_stats['services'] = service_counter.most_common(5) # Get top 5
    
    return base_stats

def print_text_dashboard(metrics: dict, hours: int):
    """
    Renders the metrics to stdout in a pretty text format.
    """
    total = metrics['total_count']
    dt_now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    print("=" * 70)
    print(f"{'ECHOCONNECTOR INCIDENT DASHBOARD':^70}")
    print("=" * 70)
    print()
    print(f"📅 Time Range: Last {hours} hours")
    print(f"📊 Generated: {dt_now}")
    print()
    
    print("=" * 70)
    print("OVERALL METRICS")
    print("=" * 70)
    unresolved_pct = (metrics['unresolved_count'] / total * 100) if total > 0 else 0
    print(f"Total Incidents:     {total}")
    print(f"Unresolved:          {metrics['unresolved_count']} ({unresolved_pct:.1f}%)")
    print(f"Avg Resolution Time: {metrics['avg_resolution_time_minutes']} minutes")
    print()
    
    print("=" * 70)
    print("SEVERITY BREAKDOWN")
    print("=" * 70)
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = metrics['by_severity'].get(sev, 0)
        pct = (count / total * 100) if total > 0 else 0
        bar = draw_bar(count, total)
        print(f"{sev:<10}: {count:4d} ({pct:5.1f}%) {bar}")
    print()
    
    print("=" * 70)
    print("STATUS BREAKDOWN")
    print("=" * 70)
    for stat in ['new', 'investigating', 'resolved', 'ignored']:
        count = metrics['by_status'].get(stat, 0)
        pct = (count / total * 100) if total > 0 else 0
        bar = draw_bar(count, total)
        print(f"{stat:<13}: {count:4d} ({pct:5.1f}%) {bar}")
    print()
    
    print("=" * 70)
    print("TOP 5 FAILING SERVICES")
    print("=" * 70)
    if not metrics['services']:
        print("No services reporting incidents.")
    else:
        for idx, (svc, count) in enumerate(metrics['services'], 1):
            pct = (count / total * 100) if total > 0 else 0
            print(f"{idx}. {svc:<30}: {count:4d} incidents ({pct:4.1f}%)")
    print()
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="EchoConnector Incident Dashboard")
    parser.add_argument("--hours", type=int, default=24, help="Time range in hours to query incidents from")
    parser.add_argument("--format", choices=['text', 'json'], default='text', help="Output format")
    
    args = parser.parse_args()
    
    # Note: Make sure AWS_PROFILE or other env credentials are set prior to running this.
    # We will assume `--profile Hack` needs to be active if run locally without lambda context.
    try:
        boto3.setup_default_session(profile_name='Hack')
    except Exception:
        pass # Ignore if not run locally or if profile doesn't exist
        
    metrics = fetch_detailed_metrics(args.hours)
    
    if args.format == 'json':
        # Translate the collection Counter logic slightly to be standard JSON
        metrics['services'] = [{"service": s, "count": c} for s, c in metrics['services']]
        print(json.dumps(metrics, indent=4))
    else:
        print_text_dashboard(metrics, args.hours)

if __name__ == "__main__":
    main()
