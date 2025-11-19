#!/bin/bash

# Hot reload script for template changes
# Usage: ./scripts/hot-reload-template.sh templates/account/login.html

TEMPLATE_FILE="$1"

if [ -z "$TEMPLATE_FILE" ]; then
    echo "Usage: $0 <template-file-path>"
    echo "Example: $0 templates/account/login.html"
    exit 1
fi

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Error: Template file not found: $TEMPLATE_FILE"
    exit 1
fi

echo "🔄 Copying $TEMPLATE_FILE to Django pods..."

# Get all Django pod names
PODS=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[*].metadata.name}')

if [ -z "$PODS" ]; then
    echo "❌ No Django pods found"
    exit 1
fi

# Copy template to each pod
for POD in $PODS; do
    echo "  📦 Copying to $POD..."
    kubectl cp "$TEMPLATE_FILE" "jewelry-shop/$POD:/app/$TEMPLATE_FILE"
    
    if [ $? -eq 0 ]; then
        echo "  ✅ Done"
    else
        echo "  ❌ Failed"
    fi
done

echo ""
echo "✨ Template updated! Just refresh your browser (Django auto-reloads in DEBUG mode)"
echo "🌐 https://jewelry-shop.local:8443/accounts/login/"
