#!/bin/bash

# ============================================================================
# Production Deployment Script
# Jewelry Management SaaS Platform
# ============================================================================
# This script automates the production deployment process
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
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
    echo -e "${NC}ℹ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_error "Please do not run this script as root"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Please copy .env.example to .env and configure it"
    exit 1
fi

# Load environment variables
source .env

# Check required environment variables
required_vars=(
    "SECRET_KEY"
    "DB_SUPERUSER_PASSWORD"
    "APP_DB_PASSWORD"
    "GRAFANA_ADMIN_PASSWORD"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        print_error "Required environment variable $var is not set"
        exit 1
    fi
done

print_success "Environment variables validated"

# Check Docker installation
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    print_info "Install Docker: curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed"
    print_info "Install Docker Compose: sudo apt-get install docker-compose-plugin"
    exit 1
fi

print_success "Docker and Docker Compose are installed"

# Parse command line arguments
COMMAND=${1:-deploy}

case $COMMAND in
    deploy)
        print_info "Starting production deployment..."
        
        # Build images
        print_info "Building Docker images..."
        docker compose -f docker-compose.prod.yml build
        print_success "Images built successfully"
        
        # Start services
        print_info "Starting services..."
        docker compose -f docker-compose.prod.yml up -d
        print_success "Services started"
        
        # Wait for database to be ready
        print_info "Waiting for database to be ready..."
        sleep 10
        
        # Run migrations
        print_info "Running database migrations..."
        docker compose -f docker-compose.prod.yml exec -T web python manage.py migrate --noinput
        print_success "Migrations completed"
        
        # Collect static files
        print_info "Collecting static files..."
        docker compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput --clear
        print_success "Static files collected"
        
        # Compile messages
        print_info "Compiling translation messages..."
        docker compose -f docker-compose.prod.yml exec -T web python manage.py compilemessages || true
        print_success "Messages compiled"
        
        # Check service health
        print_info "Checking service health..."
        sleep 5
        docker compose -f docker-compose.prod.yml ps
        
        print_success "Deployment completed successfully!"
        print_info "Access your application at: http://localhost"
        print_info "Grafana dashboard: http://localhost:3000"
        print_info "Prometheus: http://localhost:9090"
        ;;
        
    update)
        print_info "Updating production deployment..."
        
        # Pull latest images
        print_info "Pulling latest images..."
        docker compose -f docker-compose.prod.yml pull
        
        # Rebuild images
        print_info "Rebuilding images..."
        docker compose -f docker-compose.prod.yml build
        
        # Restart services with zero downtime
        print_info "Restarting services..."
        docker compose -f docker-compose.prod.yml up -d --no-deps --build web
        docker compose -f docker-compose.prod.yml up -d --no-deps --build celery_worker
        docker compose -f docker-compose.prod.yml up -d --no-deps --build celery_beat
        
        # Run migrations
        print_info "Running database migrations..."
        docker compose -f docker-compose.prod.yml exec -T web python manage.py migrate --noinput
        
        # Collect static files
        print_info "Collecting static files..."
        docker compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput --clear
        
        print_success "Update completed successfully!"
        ;;
        
    stop)
        print_info "Stopping all services..."
        docker compose -f docker-compose.prod.yml stop
        print_success "All services stopped"
        ;;
        
    start)
        print_info "Starting all services..."
        docker compose -f docker-compose.prod.yml start
        print_success "All services started"
        ;;
        
    restart)
        print_info "Restarting all services..."
        docker compose -f docker-compose.prod.yml restart
        print_success "All services restarted"
        ;;
        
    down)
        print_warning "This will stop and remove all containers"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker compose -f docker-compose.prod.yml down
            print_success "All containers removed"
        else
            print_info "Operation cancelled"
        fi
        ;;
        
    logs)
        SERVICE=${2:-}
        if [ -z "$SERVICE" ]; then
            docker compose -f docker-compose.prod.yml logs -f
        else
            docker compose -f docker-compose.prod.yml logs -f $SERVICE
        fi
        ;;
        
    status)
        print_info "Service status:"
        docker compose -f docker-compose.prod.yml ps
        echo
        print_info "Resource usage:"
        docker stats --no-stream
        ;;
        
    backup)
        print_info "Creating manual backup..."
        docker compose -f docker-compose.prod.yml exec -T web python manage.py backup_database
        print_success "Backup completed"
        ;;
        
    shell)
        SERVICE=${2:-web}
        print_info "Opening shell in $SERVICE container..."
        docker compose -f docker-compose.prod.yml exec $SERVICE /bin/bash
        ;;
        
    dbshell)
        print_info "Opening database shell..."
        docker compose -f docker-compose.prod.yml exec db psql -U postgres -d ${POSTGRES_DB:-jewelry_shop}
        ;;
        
    scale)
        WEB_REPLICAS=${2:-3}
        WORKER_REPLICAS=${3:-2}
        print_info "Scaling web to $WEB_REPLICAS replicas and workers to $WORKER_REPLICAS replicas..."
        docker compose -f docker-compose.prod.yml up -d --scale web=$WEB_REPLICAS --scale celery_worker=$WORKER_REPLICAS
        print_success "Scaling completed"
        ;;
        
    health)
        print_info "Checking service health..."
        
        # Check web health
        if curl -f http://localhost/health/ > /dev/null 2>&1; then
            print_success "Web service is healthy"
        else
            print_error "Web service is unhealthy"
        fi
        
        # Check Prometheus
        if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
            print_success "Prometheus is healthy"
        else
            print_error "Prometheus is unhealthy"
        fi
        
        # Check Grafana
        if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
            print_success "Grafana is healthy"
        else
            print_error "Grafana is unhealthy"
        fi
        ;;
        
    clean)
        print_warning "This will remove unused Docker resources"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker system prune -f
            print_success "Cleanup completed"
        else
            print_info "Operation cancelled"
        fi
        ;;
        
    *)
        echo "Usage: $0 {deploy|update|start|stop|restart|down|logs|status|backup|shell|dbshell|scale|health|clean}"
        echo
        echo "Commands:"
        echo "  deploy    - Initial deployment (build, start, migrate)"
        echo "  update    - Update deployment (pull, rebuild, restart)"
        echo "  start     - Start all services"
        echo "  stop      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  down      - Stop and remove all containers"
        echo "  logs      - View logs (optionally specify service)"
        echo "  status    - Show service status and resource usage"
        echo "  backup    - Create manual backup"
        echo "  shell     - Open shell in container (default: web)"
        echo "  dbshell   - Open database shell"
        echo "  scale     - Scale services (usage: scale <web_replicas> <worker_replicas>)"
        echo "  health    - Check service health"
        echo "  clean     - Clean up unused Docker resources"
        echo
        echo "Examples:"
        echo "  $0 deploy"
        echo "  $0 logs web"
        echo "  $0 scale 3 2"
        echo "  $0 shell celery_worker"
        exit 1
        ;;
esac
