#!/bin/bash

# Performance Testing Script for Jewelry SaaS Platform
# This script runs Locust performance tests inside Docker containers

set -e

echo "=========================================="
echo "Performance Testing Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"

# Check if containers are up
if ! docker compose ps | grep -q "web.*Up"; then
    echo -e "${YELLOW}⚠ Web container is not running. Starting services...${NC}"
    docker compose up -d
    echo "Waiting for services to be ready..."
    sleep 10
fi

echo -e "${GREEN}✓ Services are running${NC}"
echo ""

# Install/update locust if needed
echo "Checking Locust installation..."
docker compose exec -T web pip show locust > /dev/null 2>&1 || {
    echo -e "${YELLOW}⚠ Locust not found. Installing...${NC}"
    docker compose build web
    docker compose up -d web
    sleep 5
}

echo -e "${GREEN}✓ Locust is installed${NC}"
echo ""

# Setup test data
echo "Setting up test data..."
docker compose exec -T web python tests/performance/test_data_setup.py

echo ""
echo "=========================================="
echo "Running Performance Tests"
echo "=========================================="
echo ""

# Parse command line arguments
USERS=${1:-10}
SPAWN_RATE=${2:-2}
RUN_TIME=${3:-60s}
HOST=${4:-http://localhost:8000}

echo "Configuration:"
echo "  Users: $USERS"
echo "  Spawn Rate: $SPAWN_RATE users/second"
echo "  Run Time: $RUN_TIME"
echo "  Host: $HOST"
echo ""

# Run Locust in headless mode
echo "Starting Locust tests..."
echo ""

docker compose exec -T web locust \
    -f tests/performance/locustfile.py \
    --headless \
    --users $USERS \
    --spawn-rate $SPAWN_RATE \
    --run-time $RUN_TIME \
    --host $HOST \
    --html tests/performance/report.html \
    --csv tests/performance/results

echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo ""

# Display results summary
if [ -f tests/performance/results_stats.csv ]; then
    echo "Results saved to:"
    echo "  - HTML Report: tests/performance/report.html"
    echo "  - CSV Stats: tests/performance/results_stats.csv"
    echo "  - CSV Failures: tests/performance/results_failures.csv"
    echo ""
    
    echo "Quick Summary:"
    echo ""
    docker compose exec -T web cat tests/performance/results_stats.csv | head -n 10
    echo ""
fi

echo "=========================================="
echo "Performance Targets"
echo "=========================================="
echo ""
echo "Target Metrics:"
echo "  ✓ Page Load Time: < 2 seconds"
echo "  ✓ API Response Time (95th percentile): < 500ms"
echo "  ✓ Database Query Time (95th percentile): < 100ms"
echo ""
echo "Review the HTML report for detailed analysis:"
echo "  open tests/performance/report.html"
echo ""

echo -e "${GREEN}✓ Performance testing complete!${NC}"
