# Lambda - High Error Rate

## Problem Description
Lambda function experiencing elevated error rate (>5% of invocations failing).

## Symptoms
- CloudWatch alarm: `lambda-high-errors` firing
- Error metric > 5%
- Throttling or timeout errors in logs
- Users seeing 5xx errors from API
- Application degradation

## Quick Diagnosis Steps

### Step 1: Check Error Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=checkout-processor \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

### Step 2: Check CloudWatch Logs for Error Details
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/checkout-processor \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '10 minutes ago' +%s000) \
  --limit 20
```

### Step 3: Check X-Ray Traces
1. Go to AWS X-Ray console
2. Filter by function: `checkout-processor`
3. Filter by: Error traces
4. Look for common error patterns

## Common Causes & Solutions

### Cause 1: DynamoDB Throttling ⭐ MOST COMMON
**Symptoms:**
- Errors: "ProvisionedThroughputExceededException"
- X-Ray shows retries to DynamoDB
- Happens during traffic spikes

**How to identify:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=orders
```

**Solution:**
```bash
# Switch to on-demand billing (auto-scales)
aws dynamodb update-table \
  --table-name orders \
  --billing-mode PAY_PER_REQUEST
```

**Expected Result:**
- Errors drop to 0 immediately
- No more throttling
- Slightly higher cost but better availability

**Risk:** Low - Just a billing mode change

---

### Cause 2: Timeout (Function Exceeding Max Duration)
**Symptoms:**
- Logs show: "Task timed out after 30.00 seconds"
- Happens on specific operations (e.g., large reports)

**How to identify:**
```bash
# Check duration metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=checkout-processor \
  --statistics Maximum \
  --period 300
```

**Solution:**
```bash
# Increase timeout to 60 seconds
aws lambda update-function-configuration \
  --function-name checkout-processor \
  --timeout 60
```

**Expected Result:**
- Long-running operations complete successfully
- Timeout errors stop

**Risk:** Low - Just configuration change

---

### Cause 3: Memory Exhaustion (OOM Error)
**Symptoms:**
- Logs show: "Runtime exited with error: signal: killed"
- CloudWatch shows MaxMemoryUsed near allocated memory
- Happens when processing large payloads

**How to identify:**
Check memory usage in CloudWatch Logs Insights:
```
fields @timestamp, @message, @memorySize, @maxMemoryUsed
| filter @type = "REPORT"
| stats max(@maxMemoryUsed) as maxMemory, avg(@maxMemoryUsed) as avgMemory
```

**Solution:**
```bash
# Increase memory from 256MB to 512MB
# (Also increases CPU proportionally)
aws lambda update-function-configuration \
  --function-name checkout-processor \
  --memory-size 512
```

**Expected Result:**
- OOM errors stop
- Function may also run faster (more CPU)

**Risk:** Low - Increases cost slightly (~2x)

---

### Cause 4: External API Failure (Dependency Down)
**Symptoms:**
- Errors from specific external service
- X-Ray shows HTTP 5xx from downstream API
- Timeout errors when calling external service

**How to identify:**
Look in X-Ray for failed external calls

**Solution (Code Change Required):**
```python
import time
from functools import wraps

def retry_with_backoff(retries=3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        raise
                    wait = 2 ** attempt  # Exponential backoff
                    time.sleep(wait)
            return None
        return wrapper
    return decorator

@retry_with_backoff(retries=3)
def call_payment_api():
    # API call with automatic retry
    response = requests.post('https://payment-api.com/charge')
    return response.json()
```

**Expected Result:**
- Transient failures are retried automatically
- Errors only occur on persistent failures

**Risk:** Medium - Requires code deployment

---

## Prevention

### 1. Set Up Proper Monitoring
```bash
# Create alarm for error rate
aws cloudwatch put-metric-alarm \
  --alarm-name lambda-error-rate-high \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=checkout-processor
```

### 2. Enable X-Ray Tracing
```bash
aws lambda update-function-configuration \
  --function-name checkout-processor \
  --tracing-config Mode=Active
```

### 3. Use Reserved Concurrency (Prevent Runaway Costs)
```bash
aws lambda put-function-concurrency \
  --function-name checkout-processor \
  --reserved-concurrent-executions 100
```

## Past Incidents

### Incident: 2024-01-10
- **Problem:** 25% error rate on checkout-processor
- **Root Cause:** DynamoDB throttling during flash sale
- **Solution:** Switched to on-demand billing
- **Lesson:** Use on-demand for unpredictable traffic

### Incident: 2023-12-05
- **Problem:** OOM errors during report generation
- **Root Cause:** Memory set to 256MB, reports needed 400MB
- **Solution:** Increased to 512MB
- **Lesson:** Monitor memory usage in production

## Related Resources
- AWS Lambda Best Practices: https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html
- Our Team: #lambda-alerts

---
**Last Updated:** 2026-03-11  
**Owner:** Backend Team  
**Applies To:** checkout-processor, order-processor functions
