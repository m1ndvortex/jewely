# Grafana Quick Start Guide

## 🚀 Quick Installation (2 minutes)

```bash
# Navigate to grafana directory
cd k8s/grafana

# Make scripts executable
chmod +x install-grafana.sh validate-grafana.sh

# Install Grafana
./install-grafana.sh

# Validate installation
./validate-grafana.sh
```

## 🌐 Access Grafana

```bash
# Port forward to access UI
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
```

Then open: **http://localhost:3000**

## 🔐 Login

```
Username: admin
Password: admin123!@#
```

**⚠️ Change password immediately in production!**

## 📊 View Dashboards

1. Click **Dashboards** → **Browse**
2. Open **Jewelry Shop** folder
3. Explore:
   - **System Overview** - Overall platform health
   - **Application Performance** - Django metrics
   - **Database Performance** - PostgreSQL metrics
   - **Infrastructure Health** - Kubernetes metrics

## ✅ Verify Everything Works

```bash
# Run validation script
./validate-grafana.sh
```

Expected: All checks should pass ✓

## 🔧 Common Tasks

### Check Status
```bash
kubectl get pods -n jewelry-shop -l app=grafana
```

### View Logs
```bash
kubectl logs -n jewelry-shop -l app=grafana -f
```

### Restart Grafana
```bash
kubectl rollout restart deployment/grafana -n jewelry-shop
```

### Check Data Source
1. Go to **Configuration** → **Data Sources**
2. Click **Prometheus**
3. Click **Save & Test**
4. Should see: "Data source is working" ✓

## 🐛 Troubleshooting

### No Data in Dashboards?

1. **Check if Prometheus is running**:
   ```bash
   kubectl get pods -n jewelry-shop -l app=prometheus
   ```

2. **Test Prometheus connection**:
   ```bash
   kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090
   # Open http://localhost:9090
   ```

3. **Verify data source in Grafana**:
   - Configuration → Data Sources → Prometheus
   - Click "Save & Test"

### Pod Not Starting?

```bash
# Check pod status
kubectl describe pod -n jewelry-shop -l app=grafana

# Check logs
kubectl logs -n jewelry-shop -l app=grafana
```

### Cannot Access UI?

```bash
# Verify service exists
kubectl get svc grafana -n jewelry-shop

# Verify pod is running
kubectl get pods -n jewelry-shop -l app=grafana

# Try port-forward again
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
```

## 📚 Next Steps

1. **Customize Dashboards**
   - Add your own panels
   - Create custom queries
   - Save and share

2. **Set Up Alerts**
   - Configure notification channels
   - Create alert rules
   - Test alerting

3. **Add More Data Sources**
   - Loki for logs
   - Additional Prometheus instances
   - External databases

4. **User Management**
   - Create additional users
   - Set up teams
   - Configure permissions

## 📖 Full Documentation

See [README.md](README.md) for complete documentation.

## 🎯 What's Included

✅ Grafana 10.2.2  
✅ Prometheus data source (pre-configured)  
✅ 4 pre-built dashboards  
✅ 10Gi persistent storage  
✅ Health checks and monitoring  
✅ Automatic dashboard provisioning  

## 🔗 Useful Links

- Grafana UI: http://localhost:3000 (after port-forward)
- Prometheus: http://localhost:9090 (if deployed)
- [Grafana Docs](https://grafana.com/docs/grafana/latest/)
- [PromQL Guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
