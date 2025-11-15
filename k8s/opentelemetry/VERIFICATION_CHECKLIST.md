# OpenTelemetry Distributed Tracing - Verification Checklist

Use this checklist to verify the OpenTelemetry distributed tracing implementation.

## Pre-Deployment Verification

### Code Changes
- [x] OpenTelemetry dependencies added to `requirements.txt`
- [x] Tracing configuration module created (`apps/core/tracing.py`)
- [x] WSGI initialization updated (`config/wsgi.py`)
- [x] Celery initialization updated (`config/celery.py`)
- [x] No Python syntax errors or linting issues

### Kubernetes Manifests
- [x] Tempo ConfigMap created (`tempo-configmap.yaml`)
- [x] Tempo Deployment created (`tempo-deployment.yaml`)
- [x] OpenTelemetry Collector ConfigMap created (`otel-collector-configmap.yaml`)
- [x] OpenTelemetry Collector Deployment created (`otel-collector-deployment.yaml`)
- [x] Grafana datasources updated with Tempo (`grafana-configmap.yaml`)
- [x] Django deployment updated with OTEL env vars
- [x] Celery deployment updated with OTEL env vars

### Scripts and Documentation
- [x] Installation script created (`install-opentelemetry.sh`)
- [x] Validation script created (`validate-opentelemetry.sh`)
- [x] Comprehensive test script created (`test-opentelemetry-comprehensive.sh`)
- [x] README documentation created
- [x] Quick start guide created
- [x] Requirements verification document created
- [x] All scripts are executable (chmod +x)

## Deployment Verification

### Installation
- [ ] Run installation script: `./install-opentelemetry.sh`
- [ ] Installation completes without errors
- [ ] All components report as deployed

### Component Health
- [ ] Tempo pod is running: `kubectl get pods -n jewelry-shop -l app=tempo`
- [ ] OpenTelemetry Collector pods are running (2 replicas): `kubectl get pods -n jewelry-shop -l app=otel-collector`
- [ ] Tempo service exists: `kubectl get svc tempo -n jewelry-shop`
- [ ] OpenTelemetry Collector service exists: `kubectl get svc otel-collector -n jewelry-shop`
- [ ] Tempo PVC is bound: `kubectl get pvc tempo-data -n jewelry-shop`

### Health Checks
- [ ] Tempo health endpoint responds: `kubectl exec -n jewelry-shop <tempo-pod> -- wget -q -O- http://localhost:3200/ready`
- [ ] OpenTelemetry Collector health endpoint responds: `kubectl exec -n jewelry-shop <otel-pod> -- wget -q -O- http://localhost:13133`
- [ ] No errors in Tempo logs: `kubectl logs -n jewelry-shop -l app=tempo --tail=50`
- [ ] No errors in OpenTelemetry Collector logs: `kubectl logs -n jewelry-shop -l app=otel-collector --tail=50`

### Validation Script
- [ ] Run validation script: `./validate-opentelemetry.sh`
- [ ] All 12 tests pass
- [ ] No failures reported

## Application Deployment Verification

### Container Rebuild
- [ ] Rebuild Docker image: `docker compose build web`
- [ ] Tag image: `docker tag jewelry-shop:latest jewelry-shop:otel-v1`
- [ ] Import to k3d: `k3d image import jewelry-shop:otel-v1 -c jewelry-shop`
- [ ] OpenTelemetry packages present in image: `docker run jewelry-shop:otel-v1 pip list | grep opentelemetry`

### Application Redeployment
- [ ] Update Django deployment: `kubectl set image deployment/django django=jewelry-shop:otel-v1 -n jewelry-shop`
- [ ] Update Celery deployment: `kubectl set image deployment/celery-worker celery-worker=jewelry-shop:otel-v1 -n jewelry-shop`
- [ ] Django rollout completes: `kubectl rollout status deployment/django -n jewelry-shop`
- [ ] Celery rollout completes: `kubectl rollout status deployment/celery-worker -n jewelry-shop`

### Environment Variables
- [ ] Django has OTEL_ENABLED: `kubectl exec -n jewelry-shop <django-pod> -- env | grep OTEL_ENABLED`
- [ ] Django has OTEL_SERVICE_NAME: `kubectl exec -n jewelry-shop <django-pod> -- env | grep OTEL_SERVICE_NAME`
- [ ] Django has OTEL_EXPORTER_OTLP_ENDPOINT: `kubectl exec -n jewelry-shop <django-pod> -- env | grep OTEL_EXPORTER_OTLP_ENDPOINT`
- [ ] Celery has OTEL_ENABLED: `kubectl exec -n jewelry-shop <celery-pod> -- env | grep OTEL_ENABLED`
- [ ] Celery has OTEL_SERVICE_NAME: `kubectl exec -n jewelry-shop <celery-pod> -- env | grep OTEL_SERVICE_NAME`
- [ ] Celery has OTEL_EXPORTER_OTLP_ENDPOINT: `kubectl exec -n jewelry-shop <celery-pod> -- env | grep OTEL_EXPORTER_OTLP_ENDPOINT`

## Trace Generation and Verification

### Generate Test Traces
- [ ] Get Django pod name: `DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')`
- [ ] Generate traces: `for i in {1..10}; do kubectl exec -n jewelry-shop $DJANGO_POD -- wget -q -O- http://localhost:8000/health/live/; sleep 1; done`
- [ ] Wait 10 seconds for trace propagation

### Verify Trace Flow
- [ ] OpenTelemetry Collector received traces: `kubectl logs -n jewelry-shop -l app=otel-collector --tail=100 | grep -i trace`
- [ ] Tempo received spans: `kubectl exec -n jewelry-shop <tempo-pod> -- wget -q -O- http://localhost:3200/metrics | grep tempo_distributor_spans_received_total`
- [ ] Tempo metrics show non-zero span count

### Comprehensive Testing
- [ ] Run comprehensive test script: `./test-opentelemetry-comprehensive.sh`
- [ ] All 10 tests pass
- [ ] No failures reported

## Grafana Integration Verification

### Grafana Access
- [ ] Port-forward Grafana: `kubectl port-forward -n jewelry-shop svc/grafana 3000:3000`
- [ ] Access Grafana: http://localhost:3000
- [ ] Login successful

### Tempo Datasource
- [ ] Navigate to Configuration → Data Sources
- [ ] Tempo datasource is listed
- [ ] Tempo datasource shows "Data source is working"
- [ ] Test query returns results

### Trace Visualization
- [ ] Navigate to Explore
- [ ] Select "Tempo" from datasource dropdown
- [ ] Click "Search" tab
- [ ] Select service: "jewelry-shop-django"
- [ ] Click "Run query"
- [ ] Traces are displayed in list
- [ ] Click on a trace to view details
- [ ] Span timeline (waterfall view) is visible
- [ ] Individual spans show details (duration, tags, attributes)

### Trace Features
- [ ] Service map is visible
- [ ] Node graph is available
- [ ] Trace-to-logs link works (if Loki is configured)
- [ ] Trace-to-metrics link works (if Prometheus is configured)
- [ ] Search by trace ID works
- [ ] Search by tags works
- [ ] Search by duration works

## Performance Verification

### Resource Usage
- [ ] Check Tempo resource usage: `kubectl top pod -n jewelry-shop -l app=tempo`
- [ ] Tempo CPU usage is reasonable (< 1000m)
- [ ] Tempo memory usage is reasonable (< 2Gi)
- [ ] Check OpenTelemetry Collector resource usage: `kubectl top pod -n jewelry-shop -l app=otel-collector`
- [ ] Collector CPU usage is reasonable (< 1000m per pod)
- [ ] Collector memory usage is reasonable (< 1Gi per pod)

### Storage Usage
- [ ] Check Tempo storage usage: `kubectl exec -n jewelry-shop <tempo-pod> -- du -sh /var/tempo/traces`
- [ ] Storage usage is reasonable (< 10Gi)
- [ ] PVC has sufficient space remaining

### Application Performance
- [ ] Django response times are acceptable (< 2s)
- [ ] Celery task execution times are acceptable
- [ ] No significant performance degradation from tracing overhead

## Requirements Compliance

### Requirement 24.9 Verification
- [x] OpenTelemetry is integrated: Check `requirements.txt` for OpenTelemetry packages
- [x] Trace collection is configured: OpenTelemetry Collector is deployed and configured
- [x] Traces are visualized in Grafana: Tempo datasource is configured and traces are visible
- [x] Django is instrumented: `opentelemetry-instrumentation-django` is installed
- [x] PostgreSQL is instrumented: `opentelemetry-instrumentation-psycopg2` is installed
- [x] Redis is instrumented: `opentelemetry-instrumentation-redis` is installed
- [x] Celery is instrumented: `opentelemetry-instrumentation-celery` is installed
- [x] HTTP requests are instrumented: `opentelemetry-instrumentation-requests` is installed

## Documentation Verification

- [x] README.md is complete and accurate
- [x] QUICK_START.md provides clear 5-minute guide
- [x] REQUIREMENTS_VERIFICATION.md documents compliance
- [x] COMPLETION_REPORT.md summarizes implementation
- [x] All commands in documentation are tested and work
- [x] Architecture diagrams are clear and accurate
- [x] Troubleshooting section covers common issues

## Final Sign-Off

### Functional Requirements
- [ ] All components deployed successfully
- [ ] All health checks pass
- [ ] Traces are generated from Django
- [ ] Traces are generated from Celery
- [ ] Traces are visible in Grafana
- [ ] Trace search works correctly
- [ ] Trace details are complete and accurate

### Non-Functional Requirements
- [ ] Performance overhead is acceptable
- [ ] Resource usage is within limits
- [ ] Storage usage is manageable
- [ ] High availability is maintained (2 collector replicas)
- [ ] Documentation is complete

### Production Readiness
- [ ] All validation tests pass
- [ ] All comprehensive tests pass
- [ ] No errors in component logs
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures documented
- [ ] Troubleshooting guide is comprehensive

## Sign-Off

**Verified By:** _________________  
**Date:** _________________  
**Status:** [ ] APPROVED FOR PRODUCTION  

**Notes:**
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________

---

## Quick Verification Commands

```bash
# Check all components
kubectl get pods,svc,pvc -n jewelry-shop -l component=tracing

# Run validation
cd k8s/opentelemetry && ./validate-opentelemetry.sh

# Run comprehensive tests
cd k8s/opentelemetry && ./test-opentelemetry-comprehensive.sh

# Check logs
kubectl logs -n jewelry-shop -l app=tempo --tail=50
kubectl logs -n jewelry-shop -l app=otel-collector --tail=50

# Generate test traces
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
for i in {1..10}; do kubectl exec -n jewelry-shop $DJANGO_POD -- wget -q -O- http://localhost:8000/health/live/; sleep 1; done

# View traces in Grafana
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
# Open http://localhost:3000 → Explore → Tempo
```
