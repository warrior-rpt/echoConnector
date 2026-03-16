#!/usr/bin/env python3
import os
import sys
import time
from datetime import datetime, timedelta

# Add lambda directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from services.data_manager import DataManager
from common.clients import get_dynamodb_resource
from config.environment import INCIDENTS_TABLE_NAME

def log_test(name, result, message=""):
    status = "PASS" if result else "FAIL"
    print(f"{status} - {name} {(': ' + message) if message else ''}")
    return result

def run_integration_tests():
    print("Starting EchoConnector Integration Tests...")
    print(f"Table: {INCIDENTS_TABLE_NAME}\n")
    
    test_incident_ids = []
    success = True

    try:
        # 1. Create test incidents
        print("--- Testing Creation ---")
        for i in range(5):
            alarm = {
                'AlarmName': f'TEST-ALARM-{i}',
                'Namespace': 'AWS/RDS' if i % 2 == 0 else 'AWS/ApiGateway'
            }
            analysis = {'root_cause': 'Integration Test', 'suggested_fixes': []}
            severity = 'CRITICAL' if i == 0 else ('HIGH' if i < 3 else 'MEDIUM')
            inc_id = DataManager.save_incident(alarm, analysis, severity)
            test_incident_ids.append(inc_id)
        
        success &= log_test("Create test incidents", len(test_incident_ids) == 5, f"Created {len(test_incident_ids)}")

        print("  Waiting for Global Secondary Index to sync...")
        time.sleep(3)

        # 2. Retrieve individual incident
        print("\n--- Testing Retrieval ---")
        inc = DataManager.batch_get_incidents([test_incident_ids[0]])
        success &= log_test("Retrieve individual incident", len(inc) == 1 and inc[0]['incidentId'] == test_incident_ids[0])

        # 3. Batch retrieval
        inc_batch = DataManager.batch_get_incidents(test_incident_ids)
        success &= log_test("Batch retrieval (multiple)", len(inc_batch) == 5)

        # 4. Query by severity
        query_result = DataManager.query_incidents_with_pagination(severity='CRITICAL', limit=10)
        # At least one (the one we created)
        success &= log_test("Query by severity (CRITICAL)", query_result['count'] >= 1)

        # 5. Update status & Transitions
        print("\n--- Testing Transitions & Updates ---")
        # Valid: new -> investigating
        t1 = DataManager.transition_incident_status(test_incident_ids[0], 'investigating')
        success &= log_test("Valid Transition (new -> investigating)", t1)

        # Invalid: resolved -> ignored
        DataManager.transition_incident_status(test_incident_ids[0], 'resolved')
        t_invalid = DataManager.transition_incident_status(test_incident_ids[0], 'ignored')
        success &= log_test("Invalid Transition (resolved -> ignored)", t_invalid == False)

        # 6. Generate Statistics
        print("\n--- Testing Statistics ---")
        stats = DataManager.get_incident_statistics(hours=1)
        success &= log_test("Generate statistics (Total)", stats['total_count'] >= 5)
        success &= log_test("Generate statistics (Critical)", stats['by_severity']['CRITICAL'] >= 1)


        # 7. Cleanup
        print("\n--- Cleanup ---")
        table = get_dynamodb_resource().Table(INCIDENTS_TABLE_NAME)
        deleted_count = 0
        for inc_id in test_incident_ids:
            table.delete_item(Key={'incidentId': inc_id})
            deleted_count += 1
        success &= log_test("Automatic cleanup", deleted_count == 5)

    except Exception as e:
        print(f"Test suite crashed: {e}")
        success = False

    print("\n=======================================")
    if success:
        print("ALL INTEGRATION TESTS PASSED!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_integration_tests()
