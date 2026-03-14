# DynamoDB - Throttling

## Problem Description
DynamoDB table experiencing read or write requests exceeding the provisioned throughput, resulting in dropped requests.

## Symptoms
- CloudWatch alarm: `dynamodb-throttled-requests` firing
- `ProvisionedThroughputExceededException` errors in the application logs
- Slow application performance as clients retry exponentially
- Dropped requests across clients

## Quick Diagnosis Steps

### Step 1: Check Throttled Requests Metric
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ThrottledRequests \
  --dimensions Name=TableName,Value=my-table \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

### Step 2: Correlate With Operations (Read vs. Write)
Determine if the throttling is happening during Read or Write operations.

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ReadThrottleEvents \
  --dimensions Name=TableName,Value=my-table
```

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name WriteThrottleEvents \
  --dimensions Name=TableName,Value=my-table
```

### Step 3: Check Logs for Application Errors
Query CloudWatch Logs Insights or APM tools for instances of `ProvisionedThroughputExceededException` to see exactly which parts of the application are blocked.

---

## Common Causes & Solutions

### Cause 1: Spiky Workloads Below Auto-Scaling Response ⭐ MOST COMMON
**Symptoms:**
- The table is set to provisioned capacity, but traffic bursts are too fast for Auto Scaling to respond.
- Regular burst traffic causes brief but severe throttling.

**Solution:**
Switch the table to on-demand billing.
```bash
# Switch to on-demand billing (auto-scales)
aws dynamodb update-table \
  --table-name my-table \
  --billing-mode PAY_PER_REQUEST
```

**Expected Result:**
- Throttling drops to 0 almost immediately.
- Temporary increase in cost, but full availability is restored.

---

### Cause 2: Unoptimized Read Traffic
**Symptoms:**
- Mostly `ReadThrottleEvents`.
- Repeated identical read operations from the app instead of cache.

**Solution:**
Enable caching by inserting DAX (DynamoDB Accelerator) or configuring application-level caching (Redis/Memcached).
Alternatively, increase the provisioned read capacity manually if you don't use On-Demand yet:
```bash
aws application-autoscaling put-scaling-policy \
  --service-namespace dynamodb \
  --resource-id table/my-table \
  --scalable-dimension dynamodb:table:ReadCapacityUnits \
  ... # Set higher capacity rules
```

**Expected Result:**
- Throttling dissipates as read capacity covers the volume.

---

## Prevention

### 1. Enable Auto Scaling with Lower Target Usage
Ensure your auto-scaling policies target 70% utilization, giving them enough headroom to scale-out before throttling occurs.

### 2. Monitor Consumed vs Provisioned Capacity
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name High-DynamoDB-Utilization \
  ... # Monitor when Consumed > 80% of Provisioned
```

## Related Resources
- AWS DynamoDB Capacity Tuning: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ProvisionedThroughput.html

---
**Last Updated:** 2026-03-14  
**Owner:** Database Team
