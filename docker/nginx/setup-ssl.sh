#!/bin/bash
# Setup SSL certificates with Let's Encrypt
# This script helps obtain SSL certificates for production deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Let's Encrypt SSL Certificate Setup ===${NC}"
echo ""

# Check if domain is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Domain name is required${NC}"
    echo "Usage: $0 <domain> [email]"
    echo "Example: $0 jewelry-shop.com admin@jewelry-shop.com"
    exit 1
fi

DOMAIN=$1
EMAIL=${2:-""}

# Validate domain format
if [[ ! $DOMAIN =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$ ]]; then
    echo -e "${RED}Error: Invalid domain format${NC}"
    echo "Please provide a valid domain name (e.g., example.com)"
    exit 1
fi

# Check if email is provided
if [ -z "$EMAIL" ]; then
    read -p "Enter email address for Let's Encrypt notifications: " EMAIL
fi

# Validate email format
if [[ ! $EMAIL =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
    echo -e "${RED}Error: Invalid email format${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Domain: $DOMAIN"
echo "  Email: $EMAIL"
echo ""

# Confirm
read -p "Proceed with certificate request? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${GREEN}Step 1: Ensuring nginx is running...${NC}"
docker compose up -d nginx

echo ""
echo -e "${GREEN}Step 2: Requesting certificate from Let's Encrypt...${NC}"
echo "This may take a few minutes..."

# Request certificate
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Certificate obtained successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Update docker/nginx/conf.d/jewelry-shop.conf:"
    echo "   - Replace 'your-domain.com' with '$DOMAIN'"
    echo "   - Uncomment the HTTPS server block"
    echo "   - Comment out the HTTP location / block"
    echo ""
    echo "2. Update docker/nginx/snippets/ssl-params.conf:"
    echo "   - Update ssl_trusted_certificate path to:"
    echo "     /etc/letsencrypt/live/$DOMAIN/chain.pem"
    echo ""
    echo "3. Reload nginx:"
    echo "   docker compose exec nginx nginx -s reload"
    echo ""
    echo -e "${GREEN}Certificate will auto-renew every 12 hours via certbot service.${NC}"
else
    echo ""
    echo -e "${RED}✗ Certificate request failed!${NC}"
    echo ""
    echo "Common issues:"
    echo "1. Domain DNS not pointing to this server"
    echo "2. Port 80 not accessible from internet"
    echo "3. Firewall blocking HTTP traffic"
    echo ""
    echo "Please check your DNS settings and firewall rules."
    exit 1
fi
