#!/bin/bash

# Alertmanager Installation Script for Jewelry SaaS Platform
# Per Requirement 24 - Configure alerting with Alertmanager
# Task 35.4 - Set up Alertmanager, define alert rules, configure routing

set -e

echo "========================================="
echo "Alertmanager Installation for Jewelry SaaS"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if namespace exists
echo "Checking namespace..."
if ! kubectl get namespace jewelry-shop &> /dev/null; then
    echo -e "${RED}Error: jewelry-shop namespace does not exist${NC}"
    echo "Please create the namespace first: kubectl create namespace jewelry-shop"
    exit 1
fi
echo -e "${GREEN}✓ Namespace exists${NC}"
echo ""

# Step 1: Create secrets (if not already exists)
echo "Step 1: Creating Alertmanager secrets..."
if kubectl get secret alertmanager-secrets -n jewelry-shop &> /dev/null; then
    echo -e "${YELLOW}⚠ Secrets already exist, skipping creation${NC}"
    echo "To update secrets, delete them first: kubectl delete secret alertmanager-secrets -n jewelry-shop"
else
    # Prompt for credentials
    echo ""
    echo "Please provide the following credentials:"
    echo ""
    
    read -p "SMTP Password (for email alerts): " -s SMTP_PASSWORD
    echo ""
    
    read -p "Slack Webhook URL (e.g., https://hooks.slack.com/services/...): " SLACK_WEBHOOK
    echo ""
    
    read -p "PagerDuty Service Key: " PAGERDUTY_KEY
    echo ""
    
    # Generate random webhook token
    WEBHOOK_TOKEN=$(openssl rand -hex 32)
    echo "Generated webhook token: $WEBHOOK_TOKEN"
    echo ""
    
    # Create secret
    kubectl create secret generic alertmanager-secrets \
        --from-literal=smtp-password="$SMTP_PASSWORD" \
        --from-literal=slack-webhook-url="$SLACK_WEBHOOK" \
        --from-literal=pagerduty-service-key="$PAGERDUTY_KEY" \
        --from-literal=alert-webhook-token="$WEBHOOK_TOKEN" \
        --namespace=jewelry-shop
    
    echo -e "${GREEN}✓ Secrets created${NC}"
fi
echo ""

# Step 2: Apply RBAC
echo "Step 2: Applying RBAC configuration..."
kubectl apply -f alertmanager-rbac.yaml
echo -e "${GREEN}✓ RBAC configured${NC}"
echo ""

# Step 3: Apply ConfigMap
echo "Step 3: Applying Alertmanager configuration..."
kubectl apply -f alertmanager-configmap.yaml
echo -e "${GREEN}✓ ConfigMap applied${NC}"
echo ""

# Step 4: Apply alert rules to Prometheus
echo "Step 4: Applying Prometheus alert rules..."
kubectl apply -f prometheus-alert-rules.yaml
echo -e "${GREEN}✓ Alert rules applied${NC}"
echo ""

# Step 5: Update Prometheus configuration
echo "Step 5: Updating Prometheus configuration..."
kubectl apply -f ../prometheus/prometheus-configmap.yaml
echo -e "${GREEN}✓ Prometheus config updated${NC}"
echo ""

# Step 6: Update Prometheus deployment
echo "Step 6: Updating Prometheus deployment..."
kubectl apply -f ../prometheus/prometheus-deployment.yaml
echo -e "${GREEN}✓ Prometheus deployment updated${NC}"
echo ""

# Step 7: Deploy Alertmanager
echo "Step 7: Deploying Alertmanager..."
kubectl apply -f alertmanager-deployment.yaml
echo -e "${GREEN}✓ Alertmanager deployed${NC}"
echo ""

# Step 8: Wait for Alertmanager to be ready
echo "Step 8: Waiting for Alertmanager pods to be ready..."
kubectl wait --for=condition=ready pod -l app=alertmanager -n jewelry-shop --timeout=300s
echo -e "${GREEN}✓ Alertmanager is ready${NC}"
echo ""

# Step 9: Reload Prometheus configuration
echo "Step 9: Reloading Prometheus configuration..."
PROMETHEUS_POD=$(kubectl get pods -n jewelry-shop -l app=prometheus -o jsonpath='{.items[0].metadata.name}')
if [ -n "$PROMETHEUS_POD" ]; then
    kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget --post-data="" -O- http://localhost:9090/-/reload
    echo -e "${GREEN}✓ Prometheus configuration reloaded${NC}"
else
    echo -e "${YELLOW}⚠ Prometheus pod not found, skipping reload${NC}"
fi
echo ""

# Display status
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Alertmanager Status:"
kubectl get pods -n jewelry-shop -l app=alertmanager
echo ""
echo "Alertmanager Service:"
kubectl get svc -n jewelry-shop -l app=alertmanager
echo ""

# Display access information
echo "========================================="
echo "Access Information"
echo "========================================="
echo ""
echo "Alertmanager UI:"
echo "  Port-forward: kubectl port-forward -n jewelry-shop svc/alertmanager 9093:9093"
echo "  Then access: http://localhost:9093"
echo ""
echo "Prometheus UI (to view alerts):"
echo "  Port-forward: kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090"
echo "  Then access: http://localhost:9090/alerts"
echo ""

# Display next steps
echo "========================================="
echo "Next Steps"
echo "========================================="
echo ""
echo "1. Verify Alertmanager is receiving alerts from Prometheus:"
echo "   kubectl logs -n jewelry-shop -l app=alertmanager -f"
echo ""
echo "2. Test alert routing by triggering a test alert:"
echo "   kubectl exec -n jewelry-shop \$PROMETHEUS_POD -- wget --post-data='' http://localhost:9090/-/reload"
echo ""
echo "3. View active alerts in Prometheus:"
echo "   Open http://localhost:9090/alerts (after port-forward)"
echo ""
echo "4. View Alertmanager UI:"
echo "   Open http://localhost:9093 (after port-forward)"
echo ""
echo "5. Configure alert receivers:"
echo "   - Update email addresses in alertmanager-configmap.yaml"
echo "   - Update Slack channels in alertmanager-configmap.yaml"
echo "   - Update PagerDuty routing in alertmanager-configmap.yaml"
echo ""
echo "6. Run validation script:"
echo "   ./validate-alertmanager.sh"
echo ""

echo -e "${GREEN}Installation completed successfully!${NC}"
