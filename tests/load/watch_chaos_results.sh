#!/bin/bash
################################################################################
# Real-time Chaos Test Monitor
# Shows: HPA scaling, pod failures, recovery times, success rates
################################################################################

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CHAOS TEST REAL-TIME MONITOR${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if test is running
if ! ps aux | grep "run_extreme_chaos_tests.sh" | grep -v grep > /dev/null; then
    echo -e "${RED}❌ No chaos test running${NC}"
    exit 1
fi

# Function to show section
show_section() {
    echo -e "\n${YELLOW}━━━ $1 ━━━${NC}"
}

# 1. LOAD TEST STATUS
show_section "LOAD TEST STATUS"
if curl -s http://localhost:8089/stats/requests 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    users = d['user_count']
    rps = d['total_rps']
    fail_rate = d['fail_ratio'] * 100
    success_rate = 100 - fail_rate
    state = d['state']
    
    print(f'Users: {users}')
    print(f'RPS: {rps:.1f}')
    
    if success_rate >= 80:
        print(f'\033[0;32m✅ Success Rate: {success_rate:.1f}%\033[0m')
    elif success_rate >= 50:
        print(f'\033[1;33m⚠️  Success Rate: {success_rate:.1f}%\033[0m')
    else:
        print(f'\033[0;31m❌ Success Rate: {success_rate:.1f}%\033[0m')
    
    print(f'State: {state}')
except:
    print('Locust not responding')
" 2>/dev/null; then
    :
else
    echo -e "${RED}Locust not accessible${NC}"
fi

# 2. HPA SCALING STATUS
show_section "HPA AUTO-SCALING"
kubectl get hpa -n jewelry-shop django-hpa 2>/dev/null | tail -n 1 | awk '{
    if ($7 == 1) {
        print "\033[0;33m⚠️  Django replicas: " $7 "/" $6 " (NOT SCALED)\033[0m"
    } else if ($7 > 1 && $7 < $6) {
        print "\033[0;32m✅ Django replicas: " $7 "/" $6 " (SCALING UP)\033[0m"
    } else if ($7 == $6) {
        print "\033[0;32m✅ Django replicas: " $7 "/" $6 " (MAX SCALED)\033[0m"
    }
}'

kubectl get hpa -n jewelry-shop django-hpa 2>/dev/null | tail -n 1 | awk '{
    split($4, cpu, "/")
    split(cpu[1], cpu_val, "%")
    cpu_pct = cpu_val[1]
    
    if (cpu_pct+0 >= 70) {
        print "\033[0;31m🔥 CPU: " $4 " (HIGH LOAD)\033[0m"
    } else if (cpu_pct+0 >= 30) {
        print "\033[1;33m⚠️  CPU: " $4 " (MEDIUM LOAD)\033[0m"
    } else {
        print "\033[0;32m✅ CPU: " $4 " (LOW LOAD)\033[0m"
    }
}'

# 3. CHAOS TEST RESULTS
show_section "CHAOS TEST RESULTS"
LATEST_LOG=$(ls -t extreme-test-*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    # PostgreSQL Failover
    if grep -q "PostgreSQL Master Failover" "$LATEST_LOG"; then
        PG_RTO=$(grep "Recovery time:" "$LATEST_LOG" | grep -oP '\d+s' | head -1)
        if [ -n "$PG_RTO" ]; then
            echo -e "${GREEN}✅ PostgreSQL Failover: ${PG_RTO} RTO${NC}"
        else
            echo -e "${YELLOW}⏳ PostgreSQL Failover: In progress...${NC}"
        fi
    fi
    
    # Redis Failover
    if grep -q "Redis Master Failover" "$LATEST_LOG"; then
        REDIS_RTO=$(grep "Redis recovered in" "$LATEST_LOG" | grep -oP '\d+s' | head -1)
        if [ -n "$REDIS_RTO" ]; then
            echo -e "${GREEN}✅ Redis Failover: ${REDIS_RTO} RTO${NC}"
        else
            echo -e "${YELLOW}⏳ Redis Failover: In progress...${NC}"
        fi
    fi
    
    # Django Self-Healing
    if grep -q "Random Django Pod Failures" "$LATEST_LOG"; then
        DJANGO_RTO=$(grep "Django pods recovered in" "$LATEST_LOG" | grep -oP '\d+s' | head -1)
        if [ -n "$DJANGO_RTO" ]; then
            echo -e "${GREEN}✅ Django Self-Healing: ${DJANGO_RTO} RTO${NC}"
        else
            echo -e "${YELLOW}⏳ Django Self-Healing: In progress...${NC}"
        fi
    fi
    
    # Node Drain
    if grep -q "Node Drain" "$LATEST_LOG"; then
        if grep -q "pods rescheduled successfully" "$LATEST_LOG"; then
            echo -e "${GREEN}✅ Node Drain: Completed${NC}"
        else
            echo -e "${YELLOW}⏳ Node Drain: In progress...${NC}"
        fi
    fi
    
    # Network Partition
    if grep -q "Network Partition" "$LATEST_LOG"; then
        if grep -q "recovered from network partition" "$LATEST_LOG"; then
            echo -e "${GREEN}✅ Network Partition: Completed${NC}"
        else
            echo -e "${YELLOW}⏳ Network Partition: In progress...${NC}"
        fi
    fi
fi

# 4. POD STATUS
show_section "POD HEALTH"
echo "PostgreSQL:"
kubectl get pods -n jewelry-shop -l app.kubernetes.io/name=jewelry-shop-db --no-headers 2>/dev/null | awk '{
    if ($2 == "1/1" && $3 == "Running") {
        print "  \033[0;32m✅ " $1 "\033[0m"
    } else {
        print "  \033[0;31m❌ " $1 " (" $3 ")\033[0m"
    }
}'

echo "Redis:"
kubectl get pods -n jewelry-shop -l app=redis --no-headers 2>/dev/null | head -3 | awk '{
    if ($3 == "Running") {
        print "  \033[0;32m✅ " $1 "\033[0m"
    } else {
        print "  \033[0;31m❌ " $1 " (" $3 ")\033[0m"
    }
}'

echo "Django:"
kubectl get pods -n jewelry-shop -l app=django --no-headers 2>/dev/null | awk '{
    if ($2 == "1/1" && $3 == "Running") {
        print "  \033[0;32m✅ " $1 "\033[0m"
    } else {
        print "  \033[0;31m❌ " $1 " (" $3 ")\033[0m"
    }
}'

# 5. TEST PROGRESS
show_section "TEST PROGRESS"
if [ -n "$LATEST_LOG" ]; then
    tail -n 5 "$LATEST_LOG" | grep -E "CHAOS|INFO|SUCCESS|FAILED" | tail -n 3
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Refresh: watch -n 5 $0${NC}"
echo -e "${BLUE}========================================${NC}"
