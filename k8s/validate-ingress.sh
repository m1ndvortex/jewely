#!/bin/bash

# Ingress Validation Script for Task 34.9
# This script validates the Traefik Ingress Controller installation
# and SSL certificate configuration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TRAEFIK_NAMESPACE="traefik"
CERT_MANAGER_NAMESPACE="cert-manager"
APP_NAMESPACE="jewelry-shop"
DOMAIN="jewelry-shop.com"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to print test result
print_result() {
    local test_name=$1
    local result=$2
    local message=$3
    
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
        if [ -n "$message" ]; then
            echo -e "  ${BLUE}$message${NC}"
        fi
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name"
        if [ -n "$message" ]; then
            echo -e "  ${RED}$message${NC}"
        fi
        ((TESTS_FAILED++))
    fi
    echo ""
}

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Ingress Validation - Task 34.9${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Test 1: Check if Traefik namespace exists
echo -e "${YELLOW}Test 1: Checking Traefik namespace...${NC}"
if kubectl get namespace ${TRAEFIK_NAMESPACE} &> /dev/null; then
    print_result "Traefik namespace exists" "PASS" "Namespace: ${TRAEFIK_NAMESPACE}"
else
    print_result "Traefik namespace exists" "FAIL" "Namespace ${TRAEFIK_NAMESPACE} not found"
fi

# Test 2: Check if Traefik pods are running
echo -e "${YELLOW}Test 2: Checking Traefik pods...${NC}"
TRAEFIK_PODS=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o json)
TRAEFIK_POD_COUNT=$(echo $TRAEFIK_PODS | jq -r '.items | length')
TRAEFIK_RUNNING=$(echo $TRAEFIK_PODS | jq -r '[.items[] | select(.status.phase=="Running")] | length')

if [ "$TRAEFIK_POD_COUNT" -gt 0 ] && [ "$TRAEFIK_RUNNING" -eq "$TRAEFIK_POD_COUNT" ]; then
    print_result "Traefik pods running" "PASS" "${TRAEFIK_RUNNING}/${TRAEFIK_POD_COUNT} pods running"
    kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik
    echo ""
else
    print_result "Traefik pods running" "FAIL" "Only ${TRAEFIK_RUNNING}/${TRAEFIK_POD_COUNT} pods running"
fi

# Test 3: Check if Traefik service exists
echo -e "${YELLOW}Test 3: Checking Traefik service...${NC}"
if kubectl get svc -n ${TRAEFIK_NAMESPACE} traefik &> /dev/null; then
    SERVICE_TYPE=$(kubectl get svc -n ${TRAEFIK_NAMESPACE} traefik -o jsonpath='{.spec.type}')
    print_result "Traefik service exists" "PASS" "Service type: ${SERVICE_TYPE}"
    kubectl get svc -n ${TRAEFIK_NAMESPACE} traefik
    echo ""
else
    print_result "Traefik service exists" "FAIL" "Traefik service not found"
fi

# Test 4: Check if cert-manager is installed
echo -e "${YELLOW}Test 4: Checking cert-manager installation...${NC}"
if kubectl get namespace ${CERT_MANAGER_NAMESPACE} &> /dev/null; then
    CERT_MANAGER_PODS=$(kubectl get pods -n ${CERT_MANAGER_NAMESPACE} -o json)
    CERT_MANAGER_RUNNING=$(echo $CERT_MANAGER_PODS | jq -r '[.items[] | select(.status.phase=="Running")] | length')
    CERT_MANAGER_TOTAL=$(echo $CERT_MANAGER_PODS | jq -r '.items | length')
    
    if [ "$CERT_MANAGER_RUNNING" -eq "$CERT_MANAGER_TOTAL" ] && [ "$CERT_MANAGER_TOTAL" -ge 3 ]; then
        print_result "cert-manager installed" "PASS" "${CERT_MANAGER_RUNNING}/${CERT_MANAGER_TOTAL} pods running"
        kubectl get pods -n ${CERT_MANAGER_NAMESPACE}
        echo ""
    else
        print_result "cert-manager installed" "FAIL" "Only ${CERT_MANAGER_RUNNING}/${CERT_MANAGER_TOTAL} pods running"
    fi
else
    print_result "cert-manager installed" "FAIL" "cert-manager namespace not found"
fi

# Test 5: Check if ClusterIssuer exists
echo -e "${YELLOW}Test 5: Checking Let's Encrypt ClusterIssuer...${NC}"
if kubectl get clusterissuer letsencrypt-prod &> /dev/null; then
    ISSUER_STATUS=$(kubectl get clusterissuer letsencrypt-prod -o jsonpath='{.status.conditions[0].status}')
    if [ "$ISSUER_STATUS" = "True" ]; then
        print_result "ClusterIssuer ready" "PASS" "letsencrypt-prod is ready"
        kubectl get clusterissuer
        echo ""
    else
        print_result "ClusterIssuer ready" "FAIL" "letsencrypt-prod status: ${ISSUER_STATUS}"
    fi
else
    print_result "ClusterIssuer ready" "FAIL" "letsencrypt-prod not found"
fi

# Test 6: Check if Ingress resource exists
echo -e "${YELLOW}Test 6: Checking Ingress resource...${NC}"
if kubectl get ingress -n ${APP_NAMESPACE} jewelry-shop-ingress &> /dev/null; then
    print_result "Ingress resource exists" "PASS" "jewelry-shop-ingress found"
    kubectl get ingress -n ${APP_NAMESPACE} jewelry-shop-ingress
    echo ""
else
    print_result "Ingress resource exists" "FAIL" "jewelry-shop-ingress not found in ${APP_NAMESPACE}"
fi

# Test 7: Check if SSL certificate is issued
echo -e "${YELLOW}Test 7: Checking SSL certificate...${NC}"
if kubectl get certificate -n ${APP_NAMESPACE} jewelry-shop-tls-cert &> /dev/null; then
    CERT_READY=$(kubectl get certificate -n ${APP_NAMESPACE} jewelry-shop-tls-cert -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
    if [ "$CERT_READY" = "True" ]; then
        print_result "SSL certificate issued" "PASS" "Certificate is ready"
        kubectl get certificate -n ${APP_NAMESPACE}
        echo ""
    else
        print_result "SSL certificate issued" "FAIL" "Certificate not ready yet"
        echo -e "${YELLOW}Certificate status:${NC}"
        kubectl describe certificate -n ${APP_NAMESPACE} jewelry-shop-tls-cert | tail -20
        echo ""
    fi
else
    print_result "SSL certificate issued" "FAIL" "Certificate jewelry-shop-tls-cert not found"
fi

# Test 8: Check HTTP to HTTPS redirect (if accessible)
echo -e "${YELLOW}Test 8: Testing HTTP to HTTPS redirect...${NC}"
if command -v curl &> /dev/null; then
    # Get LoadBalancer IP or use localhost for k3d
    EXTERNAL_IP=$(kubectl get svc -n ${TRAEFIK_NAMESPACE} traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    
    if [ -z "$EXTERNAL_IP" ]; then
        echo -e "${YELLOW}LoadBalancer IP not available, skipping HTTP redirect test${NC}"
        echo -e "${YELLOW}For k3d, you can test with port-forward:${NC}"
        echo -e "  kubectl port-forward -n ${TRAEFIK_NAMESPACE} svc/traefik 8080:80 8443:443"
        echo -e "  curl -I http://localhost:8080 -H 'Host: ${DOMAIN}'"
        echo ""
    else
        HTTP_RESPONSE=$(curl -s -I -L --max-redirs 0 http://${EXTERNAL_IP} -H "Host: ${DOMAIN}" 2>&1 || true)
        if echo "$HTTP_RESPONSE" | grep -q "301\|302\|307\|308"; then
            if echo "$HTTP_RESPONSE" | grep -qi "https"; then
                print_result "HTTP to HTTPS redirect" "PASS" "Redirect is configured"
            else
                print_result "HTTP to HTTPS redirect" "FAIL" "Redirect found but not to HTTPS"
            fi
        else
            print_result "HTTP to HTTPS redirect" "FAIL" "No redirect detected"
        fi
    fi
else
    echo -e "${YELLOW}curl not available, skipping HTTP redirect test${NC}"
    echo ""
fi

# Test 9: Check if Nginx service exists (backend)
echo -e "${YELLOW}Test 9: Checking Nginx backend service...${NC}"
if kubectl get svc -n ${APP_NAMESPACE} nginx-service &> /dev/null; then
    print_result "Nginx service exists" "PASS" "Backend service is available"
    kubectl get svc -n ${APP_NAMESPACE} nginx-service
    echo ""
else
    print_result "Nginx service exists" "FAIL" "nginx-service not found in ${APP_NAMESPACE}"
fi

# Test 10: Check Traefik metrics endpoint
echo -e "${YELLOW}Test 10: Checking Traefik metrics...${NC}"
TRAEFIK_POD=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$TRAEFIK_POD" ]; then
    METRICS=$(kubectl exec -n ${TRAEFIK_NAMESPACE} ${TRAEFIK_POD} -- wget -q -O- http://localhost:9100/metrics 2>/dev/null | head -5 || echo "")
    if [ -n "$METRICS" ]; then
        print_result "Traefik metrics available" "PASS" "Prometheus metrics endpoint is working"
    else
        print_result "Traefik metrics available" "FAIL" "Cannot access metrics endpoint"
    fi
else
    print_result "Traefik metrics available" "FAIL" "No Traefik pod found"
fi

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Validation Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Ingress is properly configured.${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo -e "  1. Update DNS records to point ${DOMAIN} to the LoadBalancer IP"
    echo -e "  2. Wait for DNS propagation (can take up to 48 hours)"
    echo -e "  3. Test with: curl -I https://${DOMAIN}"
    echo -e "  4. Monitor certificate renewal: kubectl get certificate -n ${APP_NAMESPACE} --watch"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the errors above.${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting Commands:${NC}"
    echo -e "  Check Traefik logs: kubectl logs -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik"
    echo -e "  Check cert-manager logs: kubectl logs -n ${CERT_MANAGER_NAMESPACE} -l app=cert-manager"
    echo -e "  Check certificate status: kubectl describe certificate -n ${APP_NAMESPACE} jewelry-shop-tls-cert"
    echo -e "  Check certificate request: kubectl get certificaterequest -n ${APP_NAMESPACE}"
    echo -e "  Check ACME challenges: kubectl get challenge -n ${APP_NAMESPACE}"
    echo ""
    exit 1
fi
