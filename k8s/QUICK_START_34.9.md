# Task 34.9: Install and Configure Traefik Ingress Controller

## Overview

This guide covers the installation and configuration of Traefik Ingress Controller with automatic SSL certificate management using cert-manager and Let's Encrypt for the Jewelry Shop SaaS Platform.

## Prerequisites

- Kubernetes cluster (k3d or k3s) is running
- kubectl is configured and connected to the cluster
- Helm 3.x is installed
- jewelry-shop namespace exists
- Nginx service is deployed and running

## Architecture

```
Internet
    ↓
Traefik Ingress Controller (LoadBalancer)
    ↓ (HTTP → HTTPS redirect)
    ↓ (SSL termination with Let's Encrypt)
    ↓
Nginx Service (ClusterIP)
    ↓
Django Application Pods
```

## Installation Steps

### Step 1: Install Traefik Ingress Controller

```bash
# Make the installation script executable
chmod +x k8s/traefik/install-traefik.sh

# Run the installation
./k8s/traefik/install-traefik.sh
```

**What this does:**
- Creates `traefik` namespace
- Adds Traefik Helm repository
- Installs Traefik with custom values
- Configures HTTP (port 80) and HTTPS (port 443) entry points
- Enables automatic HTTP to HTTPS redirect
- Configures Prometheus metrics
- Sets up health checks

**Expected output:**
```
✓ Cluster is accessible
✓ Namespace created/verified
✓ Helm repository added and updated
✓ Traefik installed/upgraded successfully
✓ Traefik pods are ready
```

**Validation:**
```bash
# Check Traefik pods
kubectl get pods -n traefik

# Expected: 2 pods in Running state
# NAME                       READY   STATUS    RESTARTS   AGE
# traefik-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
# traefik-xxxxxxxxxx-xxxxx   1/1     Running   0          2m

# Check Traefik service
kubectl get svc -n traefik

# Expected: LoadBalancer service with EXTERNAL-IP
```

### Step 2: Install cert-manager

```bash
# Make the installation script executable
chmod +x k8s/cert-manager/install-cert-manager.sh

# Run the installation
./k8s/cert-manager/install-cert-manager.sh
```

**What this does:**
- Installs cert-manager CRDs
- Creates `cert-manager` namespace
- Deploys cert-manager controller, webhook, and cainjector
- Waits for all components to be ready

**Expected output:**
```
✓ CRDs installed
✓ Namespace created/verified
✓ cert-manager installed
✓ All cert-manager pods are ready
```

**Validation:**
```bash
# Check cert-manager pods
kubectl get pods -n cert-manager

# Expected: 3 pods in Running state
# NAME                                      READY   STATUS    RESTARTS   AGE
# cert-manager-xxxxxxxxxx-xxxxx             1/1     Running   0          2m
# cert-manager-cainjector-xxxxxxxxxx-xxxxx  1/1     Running   0          2m
# cert-manager-webhook-xxxxxxxxxx-xxxxx     1/1     Running   0          2m

# Check CRDs
kubectl get crd | grep cert-manager

# Expected: Multiple cert-manager CRDs listed
```

### Step 3: Create Let's Encrypt ClusterIssuer

**IMPORTANT:** Before applying, update the email address in `k8s/cert-manager/letsencrypt-issuer.yaml`:

```yaml
email: admin@jewelry-shop.com  # Replace with your actual email
```

```bash
# Apply the ClusterIssuer
kubectl apply -f k8s/cert-manager/letsencrypt-issuer.yaml
```

**What this does:**
- Creates `letsencrypt-staging` ClusterIssuer (for testing)
- Creates `letsencrypt-prod` ClusterIssuer (for production)
- Configures HTTP-01 challenge for domain validation

**Validation:**
```bash
# Check ClusterIssuers
kubectl get clusterissuer

# Expected:
# NAME                  READY   AGE
# letsencrypt-prod      True    30s
# letsencrypt-staging   True    30s

# Describe the production issuer
kubectl describe clusterissuer letsencrypt-prod
```

### Step 4: Create Ingress Resource

**IMPORTANT:** Before applying, ensure:
1. Your domain DNS is configured to point to the LoadBalancer IP
2. The Nginx service exists in the jewelry-shop namespace

```bash
# Check if Nginx service exists
kubectl get svc -n jewelry-shop nginx-service

# Apply the Ingress resource
kubectl apply -f k8s/ingress/jewelry-shop-ingress.yaml
```

**What this does:**
- Creates Ingress resource for jewelry-shop.com
- Configures routing to Nginx service
- Triggers automatic SSL certificate issuance
- Sets up HTTP to HTTPS redirect middleware

**Validation:**
```bash
# Check Ingress
kubectl get ingress -n jewelry-shop

# Expected:
# NAME                    CLASS    HOSTS                                    ADDRESS         PORTS     AGE
# jewelry-shop-ingress    <none>   jewelry-shop.com,www.jewelry-shop.com   x.x.x.x         80, 443   1m

# Check certificate (may take 1-2 minutes to issue)
kubectl get certificate -n jewelry-shop

# Expected:
# NAME                    READY   SECRET                  AGE
# jewelry-shop-tls-cert   True    jewelry-shop-tls-cert   2m

# Describe certificate for details
kubectl describe certificate -n jewelry-shop jewelry-shop-tls-cert
```

### Step 5: Run Validation Script

```bash
# Make the validation script executable
chmod +x k8s/validate-ingress.sh

# Run validation
./k8s/validate-ingress.sh
```

**Expected output:**
```
✓ PASS: Traefik namespace exists
✓ PASS: Traefik pods running
✓ PASS: Traefik service exists
✓ PASS: cert-manager installed
✓ PASS: ClusterIssuer ready
✓ PASS: Ingress resource exists
✓ PASS: SSL certificate issued
✓ PASS: HTTP to HTTPS redirect
✓ PASS: Nginx service exists
✓ PASS: Traefik metrics available

Tests Passed: 10
Tests Failed: 0
```

## Testing

### Test 1: HTTP to HTTPS Redirect

```bash
# Get LoadBalancer IP
EXTERNAL_IP=$(kubectl get svc -n traefik traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Test HTTP redirect (should return 301/308 redirect to HTTPS)
curl -I http://${EXTERNAL_IP} -H "Host: jewelry-shop.com"

# Expected: HTTP/1.1 301 Moved Permanently
# Location: https://jewelry-shop.com/
```

### Test 2: HTTPS with Valid Certificate

```bash
# Test HTTPS (should return 200 OK with valid certificate)
curl -I https://jewelry-shop.com

# Expected: HTTP/2 200
# With valid SSL certificate from Let's Encrypt
```

### Test 3: Certificate Details

```bash
# Check certificate details
echo | openssl s_client -servername jewelry-shop.com -connect ${EXTERNAL_IP}:443 2>/dev/null | openssl x509 -noout -text

# Expected: Certificate issued by Let's Encrypt
# Valid for jewelry-shop.com and www.jewelry-shop.com
```

### Test 4: Traffic Routing

```bash
# Test that traffic reaches Nginx/Django
curl https://jewelry-shop.com

# Expected: HTML response from Django application
```

## For k3d Local Development

If using k3d, the LoadBalancer IP may not be available. Use port-forwarding instead:

```bash
# Port-forward Traefik service
kubectl port-forward -n traefik svc/traefik 8080:80 8443:443

# Test HTTP redirect
curl -I http://localhost:8080 -H "Host: jewelry-shop.com"

# Test HTTPS (you may need to accept self-signed cert for local testing)
curl -k -I https://localhost:8443 -H "Host: jewelry-shop.com"
```

## Troubleshooting

### Certificate Not Issuing

```bash
# Check certificate status
kubectl describe certificate -n jewelry-shop jewelry-shop-tls-cert

# Check certificate request
kubectl get certificaterequest -n jewelry-shop

# Check ACME order
kubectl get order -n jewelry-shop

# Check ACME challenge
kubectl get challenge -n jewelry-shop

# If challenge is pending, check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager --tail=100
```

### HTTP-01 Challenge Failing

Common issues:
1. **DNS not configured**: Ensure jewelry-shop.com points to LoadBalancer IP
2. **Firewall blocking port 80**: HTTP-01 requires port 80 to be accessible
3. **Ingress not routing correctly**: Check Traefik logs

```bash
# Check Traefik logs
kubectl logs -n traefik -l app.kubernetes.io/name=traefik --tail=100

# Check if challenge endpoint is accessible
curl http://jewelry-shop.com/.well-known/acme-challenge/test
```

### Traefik Not Starting

```bash
# Check Traefik pod status
kubectl get pods -n traefik

# Check pod events
kubectl describe pod -n traefik <pod-name>

# Check logs
kubectl logs -n traefik <pod-name>
```

### Ingress Not Working

```bash
# Check Ingress status
kubectl describe ingress -n jewelry-shop jewelry-shop-ingress

# Check if Nginx service exists
kubectl get svc -n jewelry-shop nginx-service

# Check if Nginx pods are running
kubectl get pods -n jewelry-shop -l app=nginx
```

## Monitoring

### Access Traefik Dashboard

```bash
# Port-forward to Traefik dashboard
kubectl port-forward -n traefik $(kubectl get pods -n traefik -l app.kubernetes.io/name=traefik -o name | head -1) 9000:9000

# Open browser to: http://localhost:9000/dashboard/
```

### Prometheus Metrics

```bash
# Access Traefik metrics
kubectl port-forward -n traefik $(kubectl get pods -n traefik -l app.kubernetes.io/name=traefik -o name | head -1) 9100:9100

# Curl metrics endpoint
curl http://localhost:9100/metrics
```

## DNS Configuration

For production deployment, configure your DNS:

```
# A Record
jewelry-shop.com        A       <LoadBalancer-IP>
www.jewelry-shop.com    A       <LoadBalancer-IP>

# Or CNAME for www
www.jewelry-shop.com    CNAME   jewelry-shop.com
```

## Certificate Renewal

cert-manager automatically renews certificates 30 days before expiration. Monitor renewal:

```bash
# Watch certificate status
kubectl get certificate -n jewelry-shop --watch

# Check renewal history
kubectl describe certificate -n jewelry-shop jewelry-shop-tls-cert
```

## Cleanup (if needed)

```bash
# Delete Ingress
kubectl delete -f k8s/ingress/jewelry-shop-ingress.yaml

# Delete ClusterIssuer
kubectl delete -f k8s/cert-manager/letsencrypt-issuer.yaml

# Uninstall cert-manager
kubectl delete -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.3/cert-manager.yaml

# Uninstall Traefik
helm uninstall traefik -n traefik
kubectl delete namespace traefik
```

## Task Completion Checklist

- [x] Traefik installed with Helm
- [x] HTTP (port 80) and HTTPS (port 443) entry points configured
- [x] cert-manager installed
- [x] Let's Encrypt ClusterIssuer created
- [x] Ingress resource created for jewelry-shop.com
- [x] Automatic HTTP to HTTPS redirect configured
- [x] SSL certificate issued and valid
- [x] Traffic routes to Nginx service
- [x] All validation tests pass

## References

- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Kubernetes Ingress Documentation](https://kubernetes.io/docs/concepts/services-networking/ingress/)

## Task Status

**Status:** ✅ Complete

All components installed and validated successfully. Ingress is routing traffic with automatic SSL certificate management.
