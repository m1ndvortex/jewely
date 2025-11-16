#!/bin/bash
# Build custom pre-built images for air-gapped/enterprise deployment
# These images work WITHOUT internet access

set -e

echo "🏗️  Building custom enterprise-ready images..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Build Grafana with pre-installed plugins
echo -e "${BLUE}Building custom Grafana image...${NC}"
docker build -f docker/Dockerfile.grafana -t jewelry-shop-grafana:10.2.2 .
echo -e "${GREEN}✓ Grafana image built${NC}"

# Tag for k3d import
docker tag jewelry-shop-grafana:10.2.2 jewelry-shop-grafana:latest

echo ""
echo -e "${GREEN}✓ All custom images built successfully!${NC}"
echo ""
echo "📦 Images created:"
echo "  - jewelry-shop-grafana:10.2.2"
echo "  - jewelry-shop-grafana:latest"
echo ""
echo "🚀 Next steps:"
echo "  1. Import to k3d: k3d image import jewelry-shop-grafana:latest -c jewelry-shop"
echo "  2. Update deployments to use custom images"
echo "  3. Apply updated manifests"
