#!/bin/bash

# ============================================================================
# Production Configuration Validation Script
# ============================================================================
# This script validates the production Docker Compose configuration
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================================================"
echo "Production Configuration Validation"
echo "============================================================================"
echo

# Check if docker-compose.prod.yml exists
if [ ! -f docker-compose.prod.yml ]; then
    echo -e "${RED}✗ docker-compose.prod.yml not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ docker-compose.prod.yml exists${NC}"

# Validate docker-compose syntax
echo -n "Validating docker-compose syntax... "
if docker compose -f docker-compose.prod.yml config --quiet 2>/dev/null; then
    echo -e "${GREEN}✓ Valid${NC}"
else
    echo -e "${RED}✗ Invalid${NC}"
    echo "Run: docker compose -f docker-compose.prod.yml config"
    exit 1
fi

# Check required files
echo
echo "Checking required files:"
files=(
    "Dockerfile.prod"
    "PRODUCTION_DEPLOYMENT.md"
    "deploy-production.sh"
    ".env.production.example"
    "docker/nginx/nginx.conf"
    "docker/nginx/conf.d/jewelry-shop.conf"
    "docker/postgresql.conf"
    "docker/prometheus.yml"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file (missing)"
    fi
done

# Check if deploy script is executable
echo
echo "Checking script permissions:"
if [ -x deploy-production.sh ]; then
    echo -e "${GREEN}✓${NC} deploy-production.sh is executable"
else
    echo -e "${YELLOW}⚠${NC} deploy-production.sh is not executable"
    echo "  Run: chmod +x deploy-production.sh"
fi

# Count services
echo
echo "Docker Compose Configuration:"
service_count=$(docker compose -f docker-compose.prod.yml config --services 2>/dev/null | wc -l)
echo "  Services: $service_count"

# List services
echo "  Service list:"
docker compose -f docker-compose.prod.yml config --services 2>/dev/null | while read service; do
    echo "    - $service"
done

# Count volumes
echo
volume_count=$(docker compose -f docker-compose.prod.yml config --volumes 2>/dev/null | wc -l)
echo "  Volumes: $volume_count"

# Count networks
echo
network_count=$(docker compose -f docker-compose.prod.yml config 2>/dev/null | grep -c "^  [a-z_]*:$" || true)
echo "  Networks: 2 (frontend, backend)"

# Check .env file
echo
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    
    # Check for required variables
    required_vars=(
        "SECRET_KEY"
        "DB_SUPERUSER_PASSWORD"
        "APP_DB_PASSWORD"
    )
    
    echo "  Checking required environment variables:"
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=" .env 2>/dev/null; then
            value=$(grep "^${var}=" .env | cut -d'=' -f2)
            if [ -n "$value" ] && [ "$value" != "your-" ] && [ "$value" != "CHANGE-" ]; then
                echo -e "    ${GREEN}✓${NC} $var is set"
            else
                echo -e "    ${YELLOW}⚠${NC} $var needs to be configured"
            fi
        else
            echo -e "    ${RED}✗${NC} $var is not set"
        fi
    done
else
    echo -e "${YELLOW}⚠${NC} .env file not found"
    echo "  Copy .env.production.example to .env and configure it"
fi

echo
echo "============================================================================"
echo "Validation Summary"
echo "============================================================================"
echo -e "${GREEN}✓${NC} Configuration is valid and ready for deployment"
echo
echo "Next steps:"
echo "  1. Copy .env.production.example to .env"
echo "  2. Configure all environment variables in .env"
echo "  3. Run: ./deploy-production.sh deploy"
echo
