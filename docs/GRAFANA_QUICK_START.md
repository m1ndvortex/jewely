# Grafana Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Start Grafana

```bash
# Start all services including Grafana
docker-compose up -d

# Wait for Grafana to be healthy (about 30 seconds)
docker-compose ps grafana
```

### 2. Access Grafana

Open your browser to: **http://localhost:3000**

**Default Login**:
- Username: `admin`
- Password: `admin`

⚠️ **Important**: Change the password on first login!

### 3. View Dashboards

Click **Dashboards** → **Browse** to see all available dashboards:

1. **System Overview** - Quick health check
2. **Application Performance** - Django metrics
3. **Database Performance** - PostgreSQL monitoring
4. **Infrastructure Health** - System resources

### 4. Explore Metrics

Each dashboard updates every 30 seconds automatically. You can:
- Change time range (top right)
- Zoom into specific time periods
- Click on legends to show/hide metrics
- Hover over graphs for detailed values

---

## 📊 Dashboard Overview

### System Overview
**Best for**: Daily health checks

**Key Metrics**:
- CPU Usage (should be <80%)
- Memory Usage (should be <85%)
- Disk Usage (should be <90%)
- Database Connections
- HTTP Requests/sec
- Response Times

**When to check**: Every morning, after deployments

### Application Performance
**Best for**: Performance optimization

**Key Metrics**:
- Error Rate (should be <1%)
- Response Time p95 (should be <500ms)
- Slow Endpoints
- Exception Types

**When to check**: When investigating performance issues

### Database Performance
**Best for**: Database tuning

**Key Metrics**:
- Active Connections (should be <80)
- Cache Hit Ratio (should be >90%)
- Transactions/sec
- Database Size

**When to check**: When database is slow

### Infrastructure Health
**Best for**: Capacity planning

**Key Metrics**:
- System Resources (CPU, Memory, Disk, Network)
- Redis Performance
- Service Status (all should be green)

**When to check**: Weekly reviews, capacity planning

---

## 🔔 Setting Up Alerts

### Quick Alert Setup

1. **Edit a Panel**:
   - Click panel title → Edit
   - Go to "Alert" tab
   - Click "Create alert rule from this panel"

2. **Configure Alert**:
   - Name: "High CPU Usage"
   - Condition: `avg() OF query(A, 5m) IS ABOVE 80`
   - Evaluation: Every 1m for 5m

3. **Add Notification**:
   - Go to Alerting → Notification channels
   - Add Email, Slack, or SMS
   - Test notification

### Recommended Alerts

1. **High CPU** (>80% for 5 minutes)
2. **High Memory** (>85% for 5 minutes)
3. **High Error Rate** (>5% for 2 minutes)
4. **Slow Response Time** (p95 >500ms for 5 minutes)
5. **Service Down** (any service down for 1 minute)

---

## 🛠️ Common Tasks

### Change Time Range

Click the time picker (top right) and select:
- Last 5 minutes
- Last 15 minutes
- Last 1 hour (default)
- Last 6 hours
- Last 24 hours
- Custom range

### Refresh Dashboard

- Auto-refresh: Enabled (30 seconds)
- Manual refresh: Click refresh icon (top right)
- Change refresh rate: Click dropdown next to refresh icon

### Export Dashboard

1. Open dashboard
2. Click share icon (top right)
3. Go to "Export" tab
4. Click "Save to file"
5. Download JSON file

### Import Dashboard

1. Go to Dashboards → Import
2. Upload JSON file or paste JSON
3. Select Prometheus data source
4. Click "Import"

---

## 🔍 Troubleshooting

### No Data in Dashboards

**Check Prometheus**:
```bash
# Is Prometheus running?
docker-compose ps prometheus

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets
```

**Check Data Source**:
1. Go to Configuration → Data Sources
2. Click "Prometheus"
3. Click "Test" button
4. Should show "Data source is working"

### Grafana Won't Start

```bash
# Check logs
docker-compose logs grafana

# Restart Grafana
docker-compose restart grafana

# Check port 3000 is not in use
sudo lsof -i :3000
```

### Dashboard Errors

**"No data"**:
- Check time range (might be too far in past)
- Check Prometheus is collecting metrics
- Verify metric name is correct

**"Query timeout"**:
- Reduce time range
- Simplify query
- Check Prometheus performance

---

## 📚 Learn More

- **Full Documentation**: See `docs/GRAFANA_DASHBOARDS.md`
- **Prometheus Metrics**: See `docs/PROMETHEUS_MONITORING.md`
- **Official Docs**: https://grafana.com/docs/

---

## 🎯 Quick Tips

1. **Start with System Overview** - Best for daily checks
2. **Use time range selector** - Focus on relevant time periods
3. **Hover for details** - Get exact values and timestamps
4. **Set up alerts** - Get notified of issues automatically
5. **Create custom dashboards** - Tailor to your needs
6. **Use variables** - Make dashboards dynamic
7. **Share dashboards** - Export and share with team

---

## 🚨 When to Check Dashboards

### Daily
- System Overview (morning check)
- Service Health Status

### After Deployments
- Application Performance
- Error Rate
- Response Times

### When Issues Occur
- All dashboards
- Drill down from overview to specific areas

### Weekly Reviews
- Infrastructure Health
- Database Performance
- Capacity planning metrics

---

## 💡 Pro Tips

1. **Keyboard Shortcuts**:
   - `d` + `h` = Go to home dashboard
   - `d` + `s` = Open search
   - `t` + `z` = Zoom out time range
   - `Esc` = Exit fullscreen

2. **Panel Shortcuts**:
   - Click panel title → View
   - `v` = Toggle legend
   - `e` = Edit panel
   - `i` = Inspect panel data

3. **Best Practices**:
   - Keep dashboards focused (8-12 panels max)
   - Use consistent time ranges
   - Add descriptions to panels
   - Use meaningful names
   - Tag dashboards for organization

---

## ✅ Checklist

- [ ] Grafana is running (`docker-compose ps grafana`)
- [ ] Can access http://localhost:3000
- [ ] Changed default password
- [ ] Verified Prometheus data source works
- [ ] Viewed all 4 dashboards
- [ ] Set up at least one alert
- [ ] Bookmarked Grafana URL
- [ ] Read full documentation

---

**Need Help?** Check `docs/GRAFANA_DASHBOARDS.md` for detailed documentation.

**Ready to monitor!** 🎉
