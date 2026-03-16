# ECS - Task Failures

## Problem Description
ECS tasks failing to start or crashing repeatedly, preventing service from reaching desired count.

## Symptoms
- Tasks stuck in STOPPED state
- CloudWatch alarm: `ecs-task-failures` firing
- Service not reaching desired task count
- Application unavailable or degraded
- Health check failures

## Quick Diagnosis Steps

### Step 1: Check Task Exit Code and Reason
```bash
# Get recent stopped tasks
aws ecs list-tasks \
  --cluster production-cluster \
  --desired-status STOPPED \
  --max-results 10

# Get details of stopped task
aws ecs describe-tasks \
  --cluster production-cluster \
  --tasks <task-arn>
```

**Look for:**
- `exitCode`: 0 = normal, 1 = error, 137 = OOM killed
- `stoppedReason`: Why the task stopped

### Step 2: Check Container Logs
```bash
aws logs tail /ecs/web-service --follow --since 10m
```

### Step 3: Check Service Events
```bash
aws ecs describe-services \
  --cluster production-cluster \
  --services web-service \
  --query 'services[0].events[0:10]'
```

## Common Causes & Solutions

### Cause 1: Out of Memory (OOM) ⭐ MOST COMMON
**Symptoms:**
- Exit code: 137
- Container killed shortly after start
- Memory metric at 100% before crash

**How to identify:**
```bash
# Check memory usage
aws cloudwatch get-metric-statistics \
  --namespace ECS/ContainerInsights \
  --metric-name MemoryUtilized \
  --dimensions Name=ServiceName,Value=web-service
```

**Solution:**
```bash
# Increase task memory in task definition
aws ecs register-task-definition \
  --family web-service \
  --memory 1024 \
  --cpu 512 \
  --container-definitions file://container-def.json

# Update service to use new task definition
aws ecs update-service \
  --cluster production-cluster \
  --service web-service \
  --task-definition web-service:NEW_REVISION
```

**Expected Result:**
- Tasks stay running
- No more OOM kills
- Stable task count

**Risk:** Low - Just increased memory allocation

**Our Experience:**
- Increased from 512MB to 1024MB for Node.js app
- Solved OOM crashes completely
- Cost increase: ~$15/month

---

### Cause 2: Application Crash on Startup
**Symptoms:**
- Exit code: 1
- Container starts then immediately crashes
- Error logs show application errors

**How to identify:**
Check logs for startup errors:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/web-service \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '5 minutes ago' +%s000)
```

**Common Application Errors:**
- Missing environment variables
- Database connection failure
- Required file/config missing
- Port already in use

**Solution:**
Fix the application bug identified in logs, then deploy new image.

**Expected Result:**
- Tasks start successfully
- Application runs normally

**Risk:** Medium - Requires code/config fix

---

### Cause 3: Health Check Failures
**Symptoms:**
- Tasks start, run for 1-2 minutes, then stop
- Service events show: "Task failed container health checks"
- Application is actually running but health check failing

**How to identify:**
```bash
# Check health check configuration
aws ecs describe-task-definition \
  --task-definition web-service \
  --query 'taskDefinition.containerDefinitions[0].healthCheck'
```

**Solution:**
```json
// Fix health check in task definition
{
  "healthCheck": {
    "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
    "interval": 30,
    "timeout": 5,
    "retries": 3,
    "startPeriod": 60  // Increase this if app takes time to start
  }
}
```

**Expected Result:**
- Health checks pass
- Tasks remain running

**Risk:** Low - Configuration change only

---

### Cause 4: Insufficient CPU/Memory in Cluster
**Symptoms:**
- Service events: "Unable to place task, insufficient resources"
- Tasks pending, not starting
- Cluster has no available capacity

**How to identify:**
```bash
# Check cluster capacity
aws ecs describe-clusters \
  --clusters production-cluster \
  --include STATISTICS
```

**Solution:**
Either:
1. Scale up cluster capacity (add EC2 instances)
2. Reduce resource requirements of tasks
3. Switch to Fargate (auto-scaling)

**For Fargate:**
```bash
aws ecs update-service \
  --cluster production-cluster \
  --service web-service \
  --launch-type FARGATE
```

**Expected Result:**
- Tasks can be scheduled
- Service reaches desired count

**Risk:** Medium - May increase costs

---

## Prevention

### 1. Set Up CloudWatch Alarms
```bash
# Alert on task failure rate
aws cloudwatch put-metric-alarm \
  --alarm-name ecs-task-failure-rate \
  --metric-name TaskFailureRate \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.1 \
  --comparison-operator GreaterThanThreshold
```

### 2. Enable Container Insights
```bash
aws ecs update-cluster-settings \
  --cluster production-cluster \
  --settings name=containerInsights,value=enabled
```

### 3. Use Larger startPeriod for Health Checks
Give applications enough time to initialize (60-120 seconds)

### 4. Test Task Definition Locally
```bash
# Run task definition locally with Docker Compose
docker-compose -f ecs-params.yml up
```

## Past Incidents

### Incident: 2024-03-01
- **Problem:** Tasks crashing with exit code 137
- **Root Cause:** Memory set to 512MB, app needed 800MB
- **Solution:** Increased to 1024MB
- **Lesson:** Monitor memory usage in production

### Incident: 2024-01-20
- **Problem:** Health checks failing
- **Root Cause:** startPeriod too short (30s), app needs 60s
- **Solution:** Increased startPeriod to 90s
- **Lesson:** Account for slow app initialization

## Related Resources
- ECS Troubleshooting: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/troubleshooting.html
- Our Team: #ecs-alerts

---
**Last Updated:** 2026-03-11  
**Owner:** Platform Team  
**Applies To:** production-cluster ECS services
