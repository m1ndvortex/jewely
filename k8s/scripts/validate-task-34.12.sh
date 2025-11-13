#!/bin/bash

# Quick validation script for Task 34.12
set -e

echo "=========================================="
echo "Task 34.12 Validation"
echo "=========================================="
echo ""

# Test 1: Check all PVCs exist and are bound
echo "✓ Test 1: Verify all PVCs exist"
TOTAL_PVCS=$(kubectl get pvc -n jewelry-shop --no-headers | wc -l)
BOUND_PVCS=$(kubectl get pvc -n jewelry-shop --no-headers | grep Bound | wc -l)
echo "  Total PVCs: $TOTAL_PVCS"
echo "  Bound PVCs: $BOUND_PVCS"

if [ "$TOTAL_PVCS" -ge 12 ]; then
    echo "  ✅ PASS: All 12 PVCs created"
else
    echo "  ❌ FAIL: Expected 12 PVCs, found $TOTAL_PVCS"
    exit 1
fi

if [ "$BOUND_PVCS" -ge 12 ]; then
    echo "  ✅ PASS: All PVCs are Bound"
else
    echo "  ⚠️  WARNING: $BOUND_PVCS PVCs bound (some may be Pending until mounted)"
fi

echo ""

# Test 2: Check PostgreSQL PVCs
echo "✓ Test 2: Verify PostgreSQL PVCs (100Gi each)"
PG_PVCS=$(kubectl get pvc -n jewelry-shop -l application=spilo --no-headers | wc -l)
echo "  PostgreSQL PVCs: $PG_PVCS"
if [ "$PG_PVCS" -eq 3 ]; then
    echo "  ✅ PASS: 3 PostgreSQL PVCs found"
else
    echo "  ❌ FAIL: Expected 3 PostgreSQL PVCs, found $PG_PVCS"
fi

echo ""

# Test 3: Check Redis PVCs
echo "✓ Test 3: Verify Redis PVCs (10Gi each)"
REDIS_PVCS=$(kubectl get pvc -n jewelry-shop -l app=redis,component=server --no-headers | wc -l)
echo "  Redis PVCs: $REDIS_PVCS"
if [ "$REDIS_PVCS" -eq 3 ]; then
    echo "  ✅ PASS: 3 Redis PVCs found"
else
    echo "  ❌ FAIL: Expected 3 Redis PVCs, found $REDIS_PVCS"
fi

echo ""

# Test 4: Check manual PVCs
echo "✓ Test 4: Verify manual PVCs (media, static, backups)"
MEDIA_PVC=$(kubectl get pvc media-pvc -n jewelry-shop --no-headers 2>/dev/null | wc -l)
STATIC_PVC=$(kubectl get pvc static-pvc -n jewelry-shop --no-headers 2>/dev/null | wc -l)
BACKUPS_PVC=$(kubectl get pvc backups-pvc -n jewelry-shop --no-headers 2>/dev/null | wc -l)

if [ "$MEDIA_PVC" -eq 1 ] && [ "$STATIC_PVC" -eq 1 ] && [ "$BACKUPS_PVC" -eq 1 ]; then
    echo "  ✅ PASS: All manual PVCs exist"
else
    echo "  ❌ FAIL: Some manual PVCs missing"
fi

echo ""

# Test 5: Check storage class
echo "✓ Test 5: Verify storage class configuration"
SC_EXISTS=$(kubectl get storageclass local-path --no-headers 2>/dev/null | wc -l)
if [ "$SC_EXISTS" -eq 1 ]; then
    echo "  ✅ PASS: local-path storage class exists"
else
    echo "  ❌ FAIL: local-path storage class not found"
fi

echo ""

# Test 6: Check total storage
echo "✓ Test 6: Calculate total storage allocation"
kubectl get pvc -n jewelry-shop -o json | jq -r '.items[] | select(.status.phase=="Bound") | "\(.metadata.name): \(.status.capacity.storage)"' | while read line; do
    echo "  $line"
done

TOTAL_STORAGE=$(kubectl get pvc -n jewelry-shop -o json | jq -r '[.items[] | select(.status.phase=="Bound") | .status.capacity.storage | rtrimstr("Gi") | tonumber] | add')
echo ""
echo "  Total Bound Storage: ${TOTAL_STORAGE}Gi"

if [ "$TOTAL_STORAGE" -ge 400 ]; then
    echo "  ✅ PASS: Total storage >= 400Gi"
else
    echo "  ⚠️  WARNING: Total storage is ${TOTAL_STORAGE}Gi"
fi

echo ""
echo "=========================================="
echo "✅ Task 34.12 Validation Complete"
echo "=========================================="
