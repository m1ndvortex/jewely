#!/bin/bash
# Generate Diffie-Hellman parameters for SSL/TLS
# This is required for DHE cipher suites

set -e

DHPARAM_FILE="/etc/nginx/ssl/dhparam.pem"
DHPARAM_SIZE=4096

echo "Generating Diffie-Hellman parameters..."
echo "This may take several minutes (up to 30 minutes on slower systems)..."
echo "Size: ${DHPARAM_SIZE} bits"
echo ""

if [ -f "$DHPARAM_FILE" ]; then
    echo "Warning: $DHPARAM_FILE already exists."
    read -p "Do you want to regenerate it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping generation."
        exit 0
    fi
fi

# Create directory if it doesn't exist
mkdir -p "$(dirname "$DHPARAM_FILE")"

# Generate DH parameters
openssl dhparam -out "$DHPARAM_FILE" "$DHPARAM_SIZE"

# Set proper permissions
chmod 644 "$DHPARAM_FILE"

echo ""
echo "✓ Diffie-Hellman parameters generated successfully!"
echo "  Location: $DHPARAM_FILE"
echo "  Size: $DHPARAM_SIZE bits"
