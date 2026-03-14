import json
from core.engine import WatchmanEngine
from services.cloudwatch import CloudWatchService

def lambda_handler(event, context):
    """
    Enterprise Entry Point for Watchman Lambda
    """
    try:
        incidents = WatchmanEngine.run_scan()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'incidents_processed': len(incidents),
                'incident_ids': incidents
            })
        }
    except Exception as e:
        print(f"Watchman Fatal Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# --- CLI / Testing utilities moved to localized static methods or simple calls ---

if __name__ == '__main__':
    print("EchoConnector Watchman - Local Execution Mode")
    # Example: Triggering a test
    # CloudWatchService.set_alarm_state('echo-test-high-cpu', 'ALARM', 'Manual trigger')
    result = lambda_handler({}, None)
    print(f"\nResult: {json.dumps(result, indent=2)}")

