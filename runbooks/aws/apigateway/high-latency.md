# API Gateway - High Latency

## Problem Description
API Gateway endpoints are experiencing elevated response times (>2s for p99 latency), which may lead to upstream timeouts and poor client experience.

## Symptoms
- CloudWatch alarm: `apigateway-high-latency` firing
- IntegrationLatency metric elevated
- Latency metric elevated
- Client timeouts (504 Gateway Timeout errors)
- Increased 5xx errors

## Quick Diagnosis Steps

### Step 1: Check Latency Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=my-api \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics p99
```

### Step 2: Correlate with Integration Latency
Compare `Latency` (overall request handling time) with `IntegrationLatency` (time spent in the backend system like Lambda). If IntegrationLatency is high, the backend is slow.

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name IntegrationLatency \
  --dimensions Name=ApiName,Value=my-api \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average
```

### Step 3: Check X-Ray Traces
1. Go to AWS X-Ray console
2. Filter by service: `my-api`
3. Look at the service map to find which downstream service is slow.

## Common Causes & Solutions

### Cause 1: Backend Integration is Slow (e.g., Lambda Cold Starts or Slow DB) ⭐ MOST COMMON
**Symptoms:**
- `IntegrationLatency` metric closely matches the total `Latency`.
- X-Ray shows most time spent in Lambda or DynamoDB.

**Solution:**
Address the backend issue. For Lambda, you can increase memory (which increases CPU) to improve execution speed or provision concurrency to reduce cold starts.
```bash
aws lambda put-function-concurrency \
  --function-name my-backend-function \
  --reserved-concurrent-executions 50
```

**Expected Result:**
- API Gateway latency drops as backend response time improves.

---

### Cause 2: Unoptimized Payload Sizes
**Symptoms:**
- Very large request or response payloads being sent.
- High difference between `Latency` and `IntegrationLatency`.

**Solution:**
Enable caching on API Gateway if the responses are static. Apply gzip compression.
```bash
# Enable compression on API Gateway
aws apigateway update-rest-api \
  --rest-api-id abcdef123 \
  --patch-operations op=replace,path=/minimumCompressionSize,value=1024
```

**Expected Result:**
- Faster data transfer times, reducing overall latency.

---

## Prevention

### 1. Enable API Logging and X-Ray
```bash
aws apigateway update-stage \
  --rest-api-id abcdef123 \
  --stage-name prod \
  --patch-operations op=replace,path=/*/*/tracingEnabled,value=true
```

## Related Resources
- AWS API Gateway Admin Guide: https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html

---
**Last Updated:** 2026-03-14  
**Owner:** API Team
