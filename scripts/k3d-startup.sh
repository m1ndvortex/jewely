#!/bin/bash
# ============================================================================
# k3d Jewelry Shop Cluster Startup Script
# ============================================================================
# This script handles k3d cluster recovery after PC restart with proper
# PgBouncer configuration and pod cleanup.
#
# Usage:
#   ./scripts/k3d-startup.sh
#
# Or add to your shell profile (~/.bashrc or ~/.zshrc):
#   alias jewelry-start="~/kiro/jewely/scripts/k3d-startup.sh"
# ============================================================================

set -e

echo "========================================="
echo "k3d Jewelry Shop Cluster Startup"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Start k3d cluster
echo "${YELLOW}Step 1/6:${NC} Starting k3d cluster..."
k3d cluster stop jewelry-shop 2>/dev/null || true
k3d cluster start jewelry-shop

# Wait for cluster to be ready
echo "Waiting for cluster nodes to be ready..."
kubectl wait --for=condition=ready node --all --timeout=5m

echo "${GREEN}✓${NC} Cluster started"
echo ""

# Step 2: Clean up stuck pods
echo "${YELLOW}Step 2/6:${NC} Cleaning up stuck pods..."
kubectl delete pods -n jewelry-shop --field-selector=status.phase=Unknown --force --grace-period=0 2>/dev/null || true
kubectl delete pods -n jewelry-shop --field-selector=status.phase=Failed --force --grace-period=0 2>/dev/null || true

echo "${GREEN}✓${NC} Cleanup complete"
echo ""

# Step 3: Wait for PostgreSQL to be ready
echo "${YELLOW}Step 3/6:${NC} Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l application=spilo -n jewelry-shop --timeout=5m

# Reset pooler user password (in case it was corrupted)
echo "Resetting pooler user password..."
POOLER_PASS=$(kubectl get secret -n jewelry-shop pooler.jewelry-shop-db.credentials.postgresql.acid.zalan.do -o jsonpath='{.data.password}' | base64 -d)
kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- psql -U postgres -c "ALTER USER pooler WITH PASSWORD '$POOLER_PASS';" > /dev/null

echo "${GREEN}✓${NC} PostgreSQL ready"
echo ""

# Step 4: Restart PgBouncer pods
echo "${YELLOW}Step 4/6:${NC} Restarting PgBouncer pods..."
kubectl delete pod -n jewelry-shop -l application=db-connection-pooler 2>/dev/null || true
sleep 5

# Wait for new PgBouncer pods
kubectl wait --for=condition=ready pod -l application=db-connection-pooler -n jewelry-shop --timeout=2m

# Apply custom PgBouncer configuration
echo "Applying custom PgBouncer configuration..."
PGBOUNCER_PODS=$(kubectl get pods -n jewelry-shop -l application=db-connection-pooler -o name | sed 's/pod\///')

for POD in $PGBOUNCER_PODS; do
  kubectl exec -n jewelry-shop $POD -- sh -c '
    sed -i "s/^server_login_retry = 5/server_login_retry = 60/" /etc/pgbouncer/pgbouncer.ini
    echo "server_connect_timeout = 30" >> /etc/pgbouncer/pgbouncer.ini
    echo "server_lifetime = 3600" >> /etc/pgbouncer/pgbouncer.ini
    echo "server_idle_timeout = 600" >> /etc/pgbouncer/pgbouncer.ini
    kill -HUP $(cat /var/run/pgbouncer/pgbouncer.pid) || killall -HUP pgbouncer
  ' 2>/dev/null || true
done

echo "${GREEN}✓${NC} PgBouncer configured"
echo ""

# Step 5: Restart application pods
echo "${YELLOW}Step 5/6:${NC} Restarting application deployments..."
kubectl rollout restart deployment/django -n jewelry-shop
kubectl rollout restart deployment/nginx -n jewelry-shop
kubectl rollout restart deployment/celery-worker -n jewelry-shop 2>/dev/null || true
kubectl rollout restart deployment/celery-beat -n jewelry-shop 2>/dev/null || true

echo "${GREEN}✓${NC} Deployments restarted"
echo ""

# Step 6: Wait for services to be ready
echo "${YELLOW}Step 6/6:${NC} Waiting for services to be ready..."
echo "Waiting for Django pods (this may take 2-3 minutes)..."
kubectl wait --for=condition=ready pod -l component=django -n jewelry-shop --timeout=10m || true

echo ""
echo "========================================="
echo "${GREEN}Cluster Startup Complete!${NC}"
echo "========================================="
echo ""

# Show final status
echo "Service Status:"
kubectl get pods -n jewelry-shop -l component=django -o wide
echo ""
kubectl get pods -n jewelry-shop -l component=nginx -o wide
echo ""
kubectl get pods -n jewelry-shop -l application=db-connection-pooler -o wide

echo ""
echo "${GREEN}✓ All services are ready!${NC}"
echo ""
echo "Access your application:"
echo "  HTTPS: https://jewelry-shop.local:8443"
echo "  HTTP:  http://jewelry-shop.local:8080"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n jewelry-shop"
echo "  kubectl logs -n jewelry-shop -l component=django -f"
echo "  kubectl logs -n jewelry-shop -l application=db-connection-pooler -f"
echo ""
