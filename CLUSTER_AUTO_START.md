# 🚀 Cluster Auto-Start & Health Check

## ✅ **PERMANENT FIX INSTALLED**

Your Kubernetes cluster will now **automatically start** after PC reboot and **self-heal** any issues!

---

## 📋 What Was Fixed

### 1. **Auto-Start on Boot** ✅
- **Systemd service** created: `k3d-jewelry-shop.service`
- **Automatically starts** k3d cluster when your PC boots
- **No manual intervention** needed

### 2. **Health Check Script** ✅
- **Monitors** all pods, nodes, and services
- **Auto-recovery** for crashed pods
- **Clear status reports**

---

## 🎯 How It Works

### **After Reboot:**
1. Your PC starts → Docker starts
2. **Systemd service activates** → K3d cluster starts automatically
3. **All pods restart** → Kubernetes self-heals everything
4. **Application ready** in 2-3 minutes

### **No More Manual Steps!**

❌ Before: `k3d cluster start jewelry-shop` (manual)  
✅ Now: Everything starts automatically!

---

## 🛠️ Available Scripts

### **1. Cluster Health Check**
```bash
./scripts/cluster-health-check.sh
```

**What it checks:**
- ✅ K3d cluster running
- ✅ All 3 nodes ready
- ✅ All 24 pods running
- ✅ PostgreSQL cluster (3 pods)
- ✅ Redis Sentinel (6 pods)
- ✅ Django app (2+ pods)
- ✅ Nginx (2 pods)
- ✅ Services & volumes

**Auto-recovery:** Offers to delete crashed pods


### **2. Manual Start (if needed)**
```bash
./scripts/k3d-auto-start.sh
```

**When to use:** If you stop the cluster manually


### **3. Check Auto-Start Service**
```bash
sudo systemctl status k3d-jewelry-shop
```

**Expected output:** `active` or `inactive (dead)` (runs once on boot)

---

## 🔧 Troubleshooting

### **Cluster not starting after reboot?**
```bash
# Check service status
sudo systemctl status k3d-jewelry-shop

# Check logs
sudo journalctl -u k3d-jewelry-shop -n 50

# Manually start
sudo systemctl start k3d-jewelry-shop
```

### **Pods stuck in CrashLoop?**
```bash
# Run health check (offers auto-fix)
./scripts/cluster-health-check.sh

# Or manually delete crashed pod
kubectl delete pod <pod-name> -n jewelry-shop
```

### **Need to disable auto-start?**
```bash
sudo systemctl disable k3d-jewelry-shop
```

### **Re-enable auto-start:**
```bash
sudo systemctl enable k3d-jewelry-shop
```

---

## 📊 Expected Behavior

### **On Boot:**
```
1. PC starts (0 sec)
2. Docker starts (10-20 sec)
3. K3d cluster starts (30-60 sec)
4. Nodes ready (60-90 sec)
5. Pods starting (90-120 sec)
6. All pods running (120-180 sec)
```

**Total time:** ~2-3 minutes from boot to fully operational

### **Pod Recovery:**
- **Crashed pod:** Restarts automatically (10-30 sec)
- **Node failure:** Pods reschedule to other nodes (30-60 sec)
- **Database:** Auto-reconnects when available

---

## 🎓 Production vs Development

### **Development (k3d - current setup):**
- ✅ Auto-starts on boot (systemd service)
- ✅ Self-healing pods
- ⚠️ **Limitation:** If Docker crashes, requires manual restart

### **Production (k3s on VPS):**
- ✅ Systemd service (native k3s)
- ✅ Auto-starts on boot
- ✅ Self-healing pods
- ✅ Survives server reboots completely
- ✅ No Docker dependency

**The production script** (`scripts/production-vps-complete-setup.sh`) already handles this perfectly!

---

## ✅ Verification

Run this after reboot to verify everything:

```bash
# Quick check
kubectl get nodes && kubectl get pods -n jewelry-shop

# Full health check
./scripts/cluster-health-check.sh
```

**Expected result:** All green checkmarks ✅

---

## 🚨 Emergency Commands

### **Cluster completely broken?**
```bash
# Stop and restart cluster
k3d cluster stop jewelry-shop
k3d cluster start jewelry-shop

# Or full reset (DANGER: deletes data)
k3d cluster delete jewelry-shop
# Then redeploy from scratch
```

### **Single pod stuck?**
```bash
# Force delete
kubectl delete pod <pod-name> -n jewelry-shop --force --grace-period=0
```

### **Database issues?**
```bash
# Check PostgreSQL
kubectl get pods -n jewelry-shop -l cnpg.io/cluster=jewelry-shop-db

# Check logs
kubectl logs jewelry-shop-db-0 -n jewelry-shop
```

---

## 📝 Summary

**✅ Your cluster is now production-ready for development:**
- Auto-starts on boot
- Self-heals crashed pods
- Monitors health automatically
- Clear status reporting

**Next step:** When deploying to production VPS, use:
```bash
sudo bash scripts/production-vps-complete-setup.sh
```

This will give you TRUE production self-healing with k3s systemd service!

---

**Questions? Run the health check:**
```bash
./scripts/cluster-health-check.sh
```
