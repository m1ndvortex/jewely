# Celery Scaling Guide for Production VPS

## Current Configuration (Starter - 100-200 Customers)

### VPS Requirements
- **Minimum RAM:** 4 GB
- **Recommended RAM:** 6 GB
- **CPU Cores:** 2-4 vCPUs

### Resource Allocation (4GB VPS)
```
Component            Memory      CPU      Purpose
─────────────────────────────────────────────────────────────
Operating System     500 MB      -        Linux overhead
PostgreSQL           512 MB      500m     Database
Redis                256 MB      200m     Cache + Celery broker
Django (2 pods)      1.5 GB      800m     Web application
Celery Worker (1)    512 MB      400m     Background tasks
Celery Beat (1)      200 MB      200m     Task scheduler
Monitoring           300 MB      200m     Prometheus/Grafana
─────────────────────────────────────────────────────────────
TOTAL                3.8 GB      2.3 CPU  Comfortable fit
BUFFER               200 MB      -        Emergency headroom
```

### Celery Configuration
- **Replicas:** 1 pod
- **Processes per pod:** 2 (prefork)
- **Total capacity:** 2 concurrent tasks
- **Memory per pod:** 512 MB request, 768 MB limit
- **CPU per pod:** 400m request, 800m limit

## Scaling Path by Customer Count

### Stage 1: 0-200 Customers (Current)
```yaml
replicas: 1
concurrency: 2
memory: 512Mi / 768Mi
cpu: 400m / 800m
VPS: 4 GB RAM
Total Celery Memory: ~500-600 MB
```

**When to scale:** CPU consistently > 70% OR task queue backs up

### Stage 2: 200-400 Customers
```yaml
replicas: 1  # Keep 1 pod
concurrency: 4  # Increase processes
memory: 768Mi / 1Gi
cpu: 600m / 1000m (need to increase LimitRange)
VPS: 6 GB RAM
Total Celery Memory: ~800 MB - 1 GB
```

**Changes needed:**
```bash
# Update deployment
kubectl edit deployment celery-worker -n jewelry-shop
# Change: --concurrency=4
# Update resources: memory 768Mi/1Gi, cpu 600m/1000m

# Update LimitRange
kubectl edit limitrange jewelry-shop-limits -n jewelry-shop
# Set: max cpu: 2 (from 1)
```

### Stage 3: 400-800 Customers
```yaml
replicas: 2  # HPA will auto-scale
concurrency: 4
memory: 768Mi / 1Gi
cpu: 600m / 1000m
VPS: 8 GB RAM (upgrade!)
Total Celery Memory: ~1.6-2 GB
```

**Auto-scaling:** HPA will automatically add second pod when CPU > 70%

### Stage 4: 800-1500 Customers
```yaml
replicas: 3  # HPA will auto-scale
concurrency: 4
memory: 1Gi / 1.5Gi
cpu: 800m / 1500m
VPS: 12-16 GB RAM or move to multi-server
Total Celery Memory: ~3-4.5 GB
```

**Consider:** Separate Celery server at this point

### Stage 5: 1500+ Customers (Enterprise)
- **Dedicated Celery server(s)**
- **Separate Redis for Celery**
- **Multiple worker types** (fast queue, slow queue)
- **Geographic distribution**

## Monitoring Indicators

### When to Scale UP (Add Resources)

**CPU Indicators:**
```bash
# Check CPU usage
kubectl top pods -n jewelry-shop -l component=celery-worker

# If consistently > 70%, scale up
```

**Queue Indicators:**
```python
# In Django shell
from celery.app.control import Inspect
i = Inspect()
print(i.active())  # Tasks currently processing
print(i.scheduled())  # Tasks waiting to run
print(i.reserved())  # Tasks assigned to workers

# If queue length > 100 for more than 5 minutes, scale up
```

**Task Timing:**
- If tasks take > 2x expected time to complete
- If high-priority tasks wait > 30 seconds
- If customer-facing features feel slow

### When to Scale DOWN (Reduce Resources)

**Indicators:**
- CPU < 30% for 1+ hours
- Queue always empty
- Customer count decreased

**How to scale down:**
```bash
# HPA will automatically reduce replicas
# Or manually reduce concurrency:
kubectl edit deployment celery-worker -n jewelry-shop
# Change: --concurrency=2 (from 4)
```

## Cost Optimization Tips

### 1. Use HPA (Included in this config)
Auto-scaling means you only use resources when needed.

### 2. Optimize Task Execution
```python
# Bad: Load all customers
customers = Customer.objects.all()  # Loads 200+ objects

# Good: Chunk processing
customers = Customer.objects.filter(active=True).iterator(chunk_size=100)
```

### 3. Use Task Routing
```python
# Fast tasks (< 1 second)
@app.task(queue='fast')
def send_notification():
    pass

# Slow tasks (> 10 seconds)
@app.task(queue='slow')
def generate_report():
    pass
```

Then run separate workers:
```yaml
# Fast worker (many concurrent)
args: ["--concurrency=8", "-Q", "fast,celery"]

# Slow worker (fewer concurrent)
args: ["--concurrency=2", "-Q", "slow,backups"]
```

### 4. Off-Peak Scaling
Schedule heavy tasks (backups, reports) during off-peak hours:
```python
# In celery.py beat_schedule
"daily-reports": {
    "schedule": crontab(hour=2, minute=0),  # 2 AM
}
```

## VPS Provider Recommendations

### Budget Option (Starting)
- **DigitalOcean Droplet:** $24/month (4GB RAM, 2 vCPU)
- **Hetzner Cloud:** €9.50/month (4GB RAM, 2 vCPU)
- **Vultr:** $18/month (4GB RAM, 2 vCPU)

### Growth Path
- **200-400 customers:** 6GB RAM droplet (~$36/month)
- **400-800 customers:** 8GB RAM droplet (~$48/month)
- **800+ customers:** 16GB RAM or separate servers

## Troubleshooting

### Issue: Workers keep crashing
**Solution:**
```bash
# Check if hitting memory limits
kubectl describe pod -n jewelry-shop <celery-pod>
# Look for: OOMKilled (Out Of Memory)

# If OOMKilled, increase memory:
kubectl edit deployment celery-worker -n jewelry-shop
# Change: memory limits to 1Gi
```

### Issue: Tasks timing out
**Solution:**
```bash
# Increase task timeout in config/celery.py
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes (was 300)
CELERY_TASK_SOFT_TIME_LIMIT = 540  # 9 minutes
```

### Issue: Queue backs up during peak hours
**Solution:**
```bash
# Temporarily increase concurrency
kubectl scale deployment celery-worker --replicas=2 -n jewelry-shop

# Or increase processes:
kubectl edit deployment celery-worker -n jewelry-shop
# Change: --concurrency=4 (from 2)
```

## Performance Testing

### Load Test Command
```bash
# Generate 1000 test tasks
kubectl exec -it <django-pod> -n jewelry-shop -- python manage.py shell
```

```python
from apps.notifications.tasks import send_email_task
from datetime import datetime

# Create 1000 tasks
for i in range(1000):
    send_email_task.delay(
        subject=f"Load Test {i}",
        message=f"Test message {i}",
        recipient="test@example.com"
    )
    if i % 100 == 0:
        print(f"Queued {i} tasks...")

print("All tasks queued!")
```

### Monitor Performance
```bash
# Watch task processing rate
watch -n 2 'kubectl exec <celery-pod> -n jewelry-shop -- \
  celery -A config inspect stats | grep "total"'

# Expected: 10-20 tasks/second for email tasks
```

## Current Status (After Applying Changes)

✅ **Configured for:** 100-200 customers on 4-6GB VPS  
✅ **Auto-scaling:** Enabled (1-3 pods based on load)  
✅ **Memory usage:** ~500-600 MB for Celery  
✅ **Room to grow:** Can scale to 800+ customers with VPS upgrade  
✅ **Production ready:** Prefork pool with proper shared memory  

## Next Steps

1. **Apply the configuration** (already done by assistant)
2. **Monitor for 24-48 hours** to establish baseline
3. **Set up alerts** in Grafana:
   - CPU > 80% for 10 minutes
   - Memory > 90% for 5 minutes
   - Queue length > 50 for 15 minutes
4. **Review weekly** and adjust based on growth

## Questions?

**Q: Can I reduce to 1 process (concurrency=1)?**  
A: Not recommended. With 1 process, if one task hangs, everything stops. 2 processes = redundancy.

**Q: When should I move Celery to separate server?**  
A: When total RAM usage > 80% consistently, or when you reach 800-1000 customers.

**Q: What if I grow faster than expected?**  
A: HPA will auto-scale to 3 pods. If that's not enough, manually increase concurrency or upgrade VPS.

**Q: Can I use cheaper 2GB VPS?**  
A: Not recommended for production. 2GB doesn't leave enough buffer for PostgreSQL + Django + Celery.
