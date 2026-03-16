# RDS - High CPU Utilization

## Problem Description
RDS database experiencing high CPU (>80%), causing slow queries and application timeouts.

## Symptoms
- CloudWatch alarm: `rds-high-cpu` firing
- CPU Utilization metric > 80%
- Query latency increased (p99 > 500ms)
- Application experiencing database timeouts
- Users reporting slow page loads

## Quick Diagnosis Steps

### Step 1: Check Current CPU Level
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=orders-db-prod \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average Maximum
```

**What to look for:**
- Current CPU percentage
- Duration of high CPU
- Pattern (spike vs sustained load)

### Step 2: Check Performance Insights for Slow Queries
1. Go to AWS Console → RDS → Performance Insights
2. Select database: `orders-db-prod`
3. Time range: Last 1 hour
4. Look at "Top SQL" section

**What to look for:**
- Queries consuming most DB time
- Queries with high average latency
- Sequential scans (indicates missing indexes)

### Step 3: Check Connection Count
```sql
-- Connect to RDS and run:
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
SELECT count(*) FROM pg_stat_activity;
```

**What to look for:**
- Active connections near max (400 for db.r6g.2xlarge)
- Many idle connections consuming resources

## Common Causes & Solutions

### Cause 1: Missing Database Index ⭐ MOST COMMON
**Symptoms:**
- Sequential scans in EXPLAIN output
- Query scanning entire table
- CPU spikes during peak traffic

**How to identify:**
```sql
-- Check query plan
EXPLAIN ANALYZE SELECT * FROM orders WHERE status = 'pending';

-- Check existing indexes
SELECT * FROM pg_indexes WHERE tablename = 'orders';
```

**Solution:**
```sql
-- Create index (CONCURRENTLY = no table lock)
CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);

-- Verify index created
\d orders
```

**Expected Result:**
- CPU drops from 94% to ~30% within 5 minutes
- Query time drops from 800ms to <10ms

**Risk:** Low - Index creation uses ~10-15% additional CPU temporarily

**Our Experience:**
- Used this 3 times on orders-db-prod
- Always successful, no downtime
- Index creation takes 7-8 minutes for 10M rows

---

### Cause 2: Long-Running or Stuck Query
**Symptoms:**
- Performance Insights shows queries > 10 seconds
- Locks or blocking queries visible
- CPU high but not at max

**How to identify:**
```sql
-- Find long-running queries
SELECT 
    pid, 
    now() - pg_stat_activity.query_start AS duration, 
    query,
    state
FROM pg_stat_activity 
WHERE state = 'active' 
ORDER BY duration DESC;
```

**Solution:**
```sql
-- Kill the problematic query (replace 12345 with actual PID)
SELECT pg_terminate_backend(12345);
```

**Expected Result:**
- Immediate CPU drop
- Other queries proceed normally

**Risk:** Medium - May interrupt legitimate operations

---

### Cause 3: Undersized Instance
**Symptoms:**
- CPU consistently >70% even during normal traffic
- Instance hasn't been resized in 6+ months
- Traffic has increased significantly

**How to identify:**
- Check CloudWatch CPU over last 30 days
- Compare current traffic vs 3 months ago

**Solution:**
```bash
# 1. Create snapshot first (safety!)
aws rds create-db-snapshot \
  --db-instance-identifier orders-db-prod \
  --db-snapshot-identifier orders-db-pre-resize-$(date +%Y%m%d)

# 2. Modify instance class
aws rds modify-db-instance \
  --db-instance-identifier orders-db-prod \
  --db-instance-class db.r6g.4xlarge \
  --apply-immediately
```

**Expected Result:**
- 5-10 minute downtime during restart
- CPU drops to ~40% after resize
- More headroom for growth

**Risk:** High - Brief downtime, 2x cost increase

**When We Did This:**
- Upgraded from db.r6g.xlarge to db.r6g.2xlarge in Feb 2024
- Downtime was exactly 7 minutes
- No data loss, clean restart

---

## Prevention

### 1. Proactive Monitoring
```bash
# Create alarm for sustained high CPU
aws cloudwatch put-metric-alarm \
  --alarm-name rds-sustained-high-cpu \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 3 \
  --threshold 70 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=DBInstanceIdentifier,Value=orders-db-prod
```

### 2. Regular Performance Reviews
- Review Performance Insights weekly
- Identify slow queries before they become critical
- Add indexes proactively

### 3. Code Review Requirements
- All database queries must be reviewed
- Require EXPLAIN output for new queries
- Check for N+1 query patterns

## Past Incidents

### Incident: 2024-02-15
- **Problem:** CPU at 97%, same symptoms
- **Root Cause:** Missing index on orders.created_at
- **Solution:** Added index, CPU dropped to 35%
- **Lesson:** Always check Performance Insights first

### Incident: 2023-11-22 (Black Friday)
- **Problem:** CPU at 88% during traffic spike
- **Root Cause:** Undersized instance + missing indexes
- **Solution:** Added 3 indexes + scaled to db.r6g.2xlarge
- **Lesson:** Prepare for traffic spikes ahead of time

## Related Resources
- AWS RDS Performance Insights: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html
- PostgreSQL Index Optimization: https://www.postgresql.org/docs/current/indexes.html
- Our Team Slack: #database-alerts

---
**Last Updated:** 2026-03-11  
**Owner:** Database Team  
**Applies To:** orders-db-prod (PostgreSQL 15)
