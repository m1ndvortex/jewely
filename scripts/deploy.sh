#!/bin/bash

###############################################################################
# Deployment Helper Script
#
# This script provides manual deployment operations for the jewelry shop
# SaaS platform. It supports:
# - Deploying to staging or production
# - Running database migrations
# - Rolling back deployments
# - Health check verification
# - Backup operations
#
# Usage:
#   ./scripts/deploy.sh [command] [environment] [options]
#
# Commands:
#   deploy      - Deploy to specified environment
#   rollback    - Rollback to previous version
#   migrate     - Run database migrations
#   health      - Check application health
#   backup      - Create backup before deployment
#
# Environments:
#   staging     - Staging environment
#   production  - Production environment
#
# Examples:
#   ./scripts/deploy.sh deploy staging
#   ./scripts/deploy.sh rollback production
#   ./scripts/deploy.sh migrate staging
#   ./scripts/deploy.sh health production
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="ghcr.io"
IMAGE_NAME="${GITHUB_REPOSITORY:-jewelry-shop}"
NAMESPACE_STAGING="staging"
NAMESPACE_PRODUCTION="production"

# Functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    print_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_error "docker is not installed"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

check_health() {
    local environment=$1
    local url=""
    
    if [ "$environment" == "staging" ]; then
        url="https://staging.jewelry-shop.example.com"
    elif [ "$environment" == "production" ]; then
        url="https://jewelry-shop.example.com"
    else
        print_error "Invalid environment: $environment"
        exit 1
    fi
    
    print_info "Checking health of $environment environment..."
    
    # Check basic health endpoint
    if curl -f -s "${url}/health/" > /dev/null; then
        print_success "Basic health check passed"
    else
        print_error "Basic health check failed"
        return 1
    fi
    
    # Check detailed health endpoint
    response=$(curl -s "${url}/health/detailed/")
    status=$(echo "$response" | jq -r '.status')
    
    if [ "$status" == "healthy" ]; then
        print_success "Detailed health check passed"
        echo "$response" | jq '.'
        return 0
    else
        print_error "Detailed health check failed"
        echo "$response" | jq '.'
        return 1
    fi
}

run_migrations() {
    local environment=$1
    local namespace=""
    
    if [ "$environment" == "staging" ]; then
        namespace=$NAMESPACE_STAGING
    elif [ "$environment" == "production" ]; then
        namespace=$NAMESPACE_PRODUCTION
    else
        print_error "Invalid environment: $environment"
        exit 1
    fi
    
    print_info "Running database migrations in $environment..."
    
    kubectl exec -n "$namespace" deployment/web -- python manage.py migrate --noinput
    
    print_success "Migrations completed"
}

create_backup() {
    local environment=$1
    local namespace=""
    
    if [ "$environment" == "staging" ]; then
        namespace=$NAMESPACE_STAGING
    elif [ "$environment" == "production" ]; then
        namespace=$NAMESPACE_PRODUCTION
    else
        print_error "Invalid environment: $environment"
        exit 1
    fi
    
    print_info "Creating backup in $environment..."
    
    kubectl exec -n "$namespace" deployment/web -- python manage.py trigger_backup --type=full
    
    print_success "Backup created"
}

deploy() {
    local environment=$1
    local version=${2:-"main"}
    local namespace=""
    
    if [ "$environment" == "staging" ]; then
        namespace=$NAMESPACE_STAGING
    elif [ "$environment" == "production" ]; then
        namespace=$NAMESPACE_PRODUCTION
    else
        print_error "Invalid environment: $environment"
        exit 1
    fi
    
    print_info "Deploying version $version to $environment..."
    
    # Create backup for production
    if [ "$environment" == "production" ]; then
        print_warning "Creating backup before production deployment..."
        create_backup "$environment"
    fi
    
    # Run migrations
    print_info "Running database migrations..."
    run_migrations "$environment"
    
    # Update deployment
    print_info "Updating deployment..."
    kubectl set image deployment/web \
        web="${REGISTRY}/${IMAGE_NAME}:${version}" \
        -n "$namespace"
    
    # Wait for rollout
    print_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/web -n "$namespace" --timeout=10m
    
    # Verify deployment
    print_info "Verifying deployment..."
    sleep 30  # Wait for pods to be fully ready
    
    if check_health "$environment"; then
        print_success "Deployment to $environment completed successfully"
    else
        print_error "Deployment verification failed"
        print_warning "Consider rolling back"
        exit 1
    fi
}

rollback() {
    local environment=$1
    local revision=${2:-""}
    local namespace=""
    
    if [ "$environment" == "staging" ]; then
        namespace=$NAMESPACE_STAGING
    elif [ "$environment" == "production" ]; then
        namespace=$NAMESPACE_PRODUCTION
    else
        print_error "Invalid environment: $environment"
        exit 1
    fi
    
    print_warning "Rolling back deployment in $environment..."
    
    if [ -z "$revision" ]; then
        # Rollback to previous version
        kubectl rollout undo deployment/web -n "$namespace"
    else
        # Rollback to specific revision
        kubectl rollout undo deployment/web -n "$namespace" --to-revision="$revision"
    fi
    
    # Wait for rollback
    print_info "Waiting for rollback to complete..."
    kubectl rollout status deployment/web -n "$namespace" --timeout=5m
    
    # Verify rollback
    print_info "Verifying rollback..."
    sleep 30
    
    if check_health "$environment"; then
        print_success "Rollback completed successfully"
    else
        print_error "Rollback verification failed"
        exit 1
    fi
}

show_history() {
    local environment=$1
    local namespace=""
    
    if [ "$environment" == "staging" ]; then
        namespace=$NAMESPACE_STAGING
    elif [ "$environment" == "production" ]; then
        namespace=$NAMESPACE_PRODUCTION
    else
        print_error "Invalid environment: $environment"
        exit 1
    fi
    
    print_info "Deployment history for $environment:"
    kubectl rollout history deployment/web -n "$namespace"
}

show_status() {
    local environment=$1
    local namespace=""
    
    if [ "$environment" == "staging" ]; then
        namespace=$NAMESPACE_STAGING
    elif [ "$environment" == "production" ]; then
        namespace=$NAMESPACE_PRODUCTION
    else
        print_error "Invalid environment: $environment"
        exit 1
    fi
    
    print_info "Current status of $environment:"
    echo ""
    echo "Pods:"
    kubectl get pods -n "$namespace"
    echo ""
    echo "Services:"
    kubectl get services -n "$namespace"
    echo ""
    echo "Deployments:"
    kubectl get deployments -n "$namespace"
}

show_usage() {
    cat << EOF
Deployment Helper Script

Usage:
  $0 [command] [environment] [options]

Commands:
  deploy [env] [version]    Deploy to environment (default version: main)
  rollback [env] [revision] Rollback deployment (default: previous version)
  migrate [env]             Run database migrations
  health [env]              Check application health
  backup [env]              Create backup
  history [env]             Show deployment history
  status [env]              Show current status
  help                      Show this help message

Environments:
  staging                   Staging environment
  production                Production environment

Examples:
  $0 deploy staging
  $0 deploy production v1.2.3
  $0 rollback production
  $0 rollback production 5
  $0 migrate staging
  $0 health production
  $0 backup production
  $0 history staging
  $0 status production

EOF
}

# Main script
main() {
    local command=${1:-"help"}
    local environment=$2
    local option=$3
    
    case "$command" in
        deploy)
            check_prerequisites
            if [ -z "$environment" ]; then
                print_error "Environment is required"
                show_usage
                exit 1
            fi
            deploy "$environment" "$option"
            ;;
        rollback)
            check_prerequisites
            if [ -z "$environment" ]; then
                print_error "Environment is required"
                show_usage
                exit 1
            fi
            rollback "$environment" "$option"
            ;;
        migrate)
            check_prerequisites
            if [ -z "$environment" ]; then
                print_error "Environment is required"
                show_usage
                exit 1
            fi
            run_migrations "$environment"
            ;;
        health)
            if [ -z "$environment" ]; then
                print_error "Environment is required"
                show_usage
                exit 1
            fi
            check_health "$environment"
            ;;
        backup)
            check_prerequisites
            if [ -z "$environment" ]; then
                print_error "Environment is required"
                show_usage
                exit 1
            fi
            create_backup "$environment"
            ;;
        history)
            check_prerequisites
            if [ -z "$environment" ]; then
                print_error "Environment is required"
                show_usage
                exit 1
            fi
            show_history "$environment"
            ;;
        status)
            check_prerequisites
            if [ -z "$environment" ]; then
                print_error "Environment is required"
                show_usage
                exit 1
            fi
            show_status "$environment"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
