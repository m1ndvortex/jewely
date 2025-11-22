#!/bin/bash
# ==============================================================================
# Fast Development Sync Script
# ==============================================================================
# This script watches for file changes and syncs them to the running Django pod
# Changes appear in 1-2 seconds with auto-reload
# ==============================================================================

set -e

NAMESPACE="jewelry-shop"
POD_LABEL="component=django"
WATCH_DIRS=("." "templates" "static" "locale" "accounting" "inventory" "pos" "customers" "authentication" "backup" "notifications")

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Fast Development Mode${NC}"
echo -e "${BLUE}========================================${NC}"

# Get the Django pod name
get_pod() {
    kubectl get pod -n $NAMESPACE -l $POD_LABEL -o name | head -n 1 | sed 's/pod\///'
}

POD=$(get_pod)

if [ -z "$POD" ]; then
    echo -e "${RED}❌ No Django pod found!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found pod: $POD${NC}"
echo -e "${YELLOW}📡 Watching for changes...${NC}"
echo ""

# Install inotify-tools if not present
if ! command -v inotifywait &> /dev/null; then
    echo -e "${YELLOW}Installing inotify-tools...${NC}"
    sudo apt-get update && sudo apt-get install -y inotify-tools
fi

# Function to sync file
sync_file() {
    local file=$1
    local pod=$(get_pod)
    
    # Skip certain files
    if [[ "$file" == *"__pycache__"* ]] || \
       [[ "$file" == *".pyc" ]] || \
       [[ "$file" == *".git/"* ]] || \
       [[ "$file" == *"node_modules/"* ]] || \
       [[ "$file" == *".swp" ]] || \
       [[ "$file" == *"~" ]]; then
        return
    fi
    
    echo -e "${BLUE}📤 Syncing: $file${NC}"
    
    # Copy to pod
    kubectl cp "$file" "$NAMESPACE/$pod:/app/$file" 2>/dev/null && \
        echo -e "${GREEN}✅ Synced: $file${NC}" || \
        echo -e "${RED}❌ Failed: $file${NC}"
    
    # If it's a .po file, compile it
    if [[ "$file" == *".po" ]]; then
        echo -e "${YELLOW}🔨 Compiling translations...${NC}"
        kubectl exec -n $NAMESPACE $pod -- python manage.py compilemessages 2>/dev/null && \
            echo -e "${GREEN}✅ Translations compiled${NC}" || \
            echo -e "${YELLOW}⚠️  Compilation warning (check manually)${NC}"
    fi
}

# Watch for changes
inotifywait -m -r -e modify,create,moved_to \
    --exclude '(__pycache__|\.pyc$|\.git/|node_modules/|\.swp$|~$|k8s/)' \
    --format '%w%f' \
    "${WATCH_DIRS[@]}" | while read file
do
    sync_file "$file"
done
