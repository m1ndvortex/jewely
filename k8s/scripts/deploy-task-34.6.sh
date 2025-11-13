#!/bin/bash

# ============================================================================
# Task 34.6: Deploy PostgreSQL Cluster with Automatic Failover
# ============================================================================
# This script deploys a highly available PostgreSQL cluster using the
# Zalando Postgres Operator with:
# - 3 replicas (1 master + 2 replicas)
# - Patroni for automatic failover
# - PgBouncer for connection pooling
# - Automated backups
# - postgres_exporter for metrics
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
CLUSTER_NAME="jewelry-shop-db"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

wait_for_pods() {
    local label=$1
    local count=$2
    local timeout=${3:-300}
    
    print_info "Waiting for $count pods with label $label to be ready (timeout: ${timeout}s)..."
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        local ready=$(kubectl get pods -n $NAMESPACE -l "$label" --no-headers 2>/dev/null | grep -c "Running" || echo "0")
        
        if [ "$ready" -eq "$count" ]; then
            print_success "All $count pods are ready"
            return 0
        fi
        
        echo -n "."
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    echo ""
    print_error "Timeout waiting for pods to be ready"
    kubectl get pods -n $NAMESPACE -l "$label"
    return 1
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_header "Pre-flight Checks"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed"
    exit 1
fi
print_success "kubectl is installed"

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to Kubernetes cluster"
    exit 1
fi
print_success "Kubernetes cluster is accessible"

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    print_error "Namespace $NAMESPACE does not exist"
    print_info "Run: kubectl create namespace $NAMESPACE"
    exit 1
fi
print_success "Namespace $NAMESPACE exists"

# Check if Postgres Operator is installed
if ! kubectl get crd postgresqls.acid.zalan.do &> /dev/null; then
    print_error "Zalando Postgres Operator is not installed"
    print_info "Please run Task 34.5 first to install the operator"
    exit 1
fi
print_success "Zalando Postgres Operator is installed"

# Check if operator is running
if ! kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator | grep -q "Running"; then
    print_error "Postgres Operator is not running"
    exit 1
fi
print_success "Postgres Operator is running"

# Check if secrets exist
if ! kubectl get secret postgres-secrets -n $NAMESPACE &> /dev/null; then
    print_warning "Secret postgres-secrets not found, creating from secrets.yaml..."
    kubectl apply -f "$K8S_DIR/secrets.yaml"
fi
print_success "Required secrets exist"

# ============================================================================
# Deploy PostgreSQL Cluster
# ============================================================================

print_header "Deploying PostgreSQL Cluster"

print_info "Applying postgresql-cluster.yaml..."
kubectl apply -f "$K8S_DIR/postgresql-cluster.yaml"

print_success "PostgreSQL cluster manifest applied"

# ============================================================================
# Wait for Cluster to be Ready
# ============================================================================

print_header "Waiting for PostgreSQL Cluster"

print_info "Waiting for postgresql resource to be created..."
sleep 5

# Wait for the postgresql resource to be created
timeout=60
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if kubectl get postgresql $CLUSTER_NAME -n $NAMESPACE &> /dev/null; then
        print_success "PostgreSQL resource created"
        break
    fi
    echo -n "."
    sleep 2
    elapsed=$((elapsed + 2))
done

if [ $elapsed -ge $timeout ]; then
    print_error "Timeout waiting for postgresql resource"
    exit 1
fi

# Show cluster status
print_info "Cluster status:"
kubectl get postgresql $CLUSTER_NAME -n $NAMESPACE

# Wait for pods to be created
print_info "Waiting for PostgreSQL pods to be created..."
sleep 10

# Wait for all 3 PostgreSQL pods to be running
if ! wait_for_pods "application=spilo,cluster-name=$CLUSTER_NAME" 3 600; then
    print_error "Failed to start PostgreSQL pods"
    print_info "Checking pod status..."
    kubectl get pods -n $NAMESPACE -l "application=spilo,cluster-name=$CLUSTER_NAME"
    print_info "Checking operator logs..."
    kubectl logs -n postgres-operator -l app.kubernetes.io/name=postgres-operator --tail=50
    exit 1
fi

# Wait for PgBouncer pods to be running
print_info "Waiting for PgBouncer pods..."
if ! wait_for_pods "application=db-connection-pooler,cluster-name=$CLUSTER_NAME" 2 300; then
    print_warning "PgBouncer pods not ready yet, but continuing..."
fi

# ============================================================================
# Verify Cluster Health
# ============================================================================

print_header "Verifying Cluster Health"

# Get pod names
MASTER_POD=$(kubectl get pods -n $NAMESPACE -l "application=spilo,cluster-name=$CLUSTER_NAME,spilo-role=master" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -z "$MASTER_POD" ]; then
    print_warning "Master pod not identified yet, waiting..."
    sleep 10
    MASTER_POD=$(kubectl get pods -n $NAMESPACE -l "application=spilo,cluster-name=$CLUSTER_NAME,spilo-role=master" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
fi

if [ -n "$MASTER_POD" ]; then
    print_success "Master pod: $MASTER_POD"
    
    # Check PostgreSQL is accepting connections
    print_info "Testing PostgreSQL connection..."
    if kubectl exec -n $NAMESPACE $MASTER_POD -- psql -U postgres -c "SELECT version();" &> /dev/null; then
        print_success "PostgreSQL is accepting connections"
    else
        print_warning "PostgreSQL connection test failed, but cluster may still be initializing"
    fi
    
    # Check replication status
    print_info "Checking replication status..."
    kubectl exec -n $NAMESPACE $MASTER_POD -- psql -U postgres -c "SELECT * FROM pg_stat_replication;" || true
else
    print_warning "Master pod not found yet, cluster may still be initializing"
fi

# List all pods
print_info "All PostgreSQL pods:"
kubectl get pods -n $NAMESPACE -l "application=spilo,cluster-name=$CLUSTER_NAME" -o wide

# List services
print_info "PostgreSQL services:"
kubectl get svc -n $NAMESPACE -l "application=spilo,cluster-name=$CLUSTER_NAME"

# ============================================================================
# Display Connection Information
# ============================================================================

print_header "Connection Information"

echo -e "${GREEN}PostgreSQL cluster deployed successfully!${NC}\n"

echo "Cluster Name: $CLUSTER_NAME"
echo "Namespace: $NAMESPACE"
echo ""

echo "Services created:"
echo "  - ${CLUSTER_NAME}: Master service (read-write)"
echo "  - ${CLUSTER_NAME}-repl: Replica service (read-only)"
echo "  - ${CLUSTER_NAME}-pooler: PgBouncer connection pooler"
echo ""

echo "Connection strings:"
echo "  Master (via PgBouncer): postgresql://jewelry_app@${CLUSTER_NAME}-pooler.${NAMESPACE}.svc.cluster.local:5432/jewelry_shop"
echo "  Master (direct):        postgresql://jewelry_app@${CLUSTER_NAME}.${NAMESPACE}.svc.cluster.local:5432/jewelry_shop"
echo "  Replica (read-only):    postgresql://jewelry_app@${CLUSTER_NAME}-repl.${NAMESPACE}.svc.cluster.local:5432/jewelry_shop"
echo ""

echo "To get the application password:"
echo "  kubectl get secret jewelry-app.${CLUSTER_NAME}.credentials.postgresql.acid.zalan.do -n $NAMESPACE -o jsonpath='{.data.password}' | base64 -d"
echo ""

echo "To connect to the master:"
echo "  kubectl exec -it -n $NAMESPACE $MASTER_POD -- psql -U postgres"
echo ""

echo "Next steps:"
echo "  1. Run validation script: ./scripts/validate-task-34.6.sh"
echo "  2. Test automatic failover by killing the master pod"
echo "  3. Update Django deployment to use the new database service"
echo ""

print_success "Deployment complete!"
