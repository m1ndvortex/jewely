# Performance Testing Guide

This directory contains performance testing infrastructure using Locust for the Jewelry SaaS Platform.

## Performance Targets

Based on Requirement 26, the system must meet these performance targets:

- **Page Load Time**: < 2 seconds for initial page load
- **API Response Time**: < 500ms for 95th percentile
- **Database Query Time**: < 100ms for 95th percentile

## Test Files

### `locustfile.py`
Main Locust test file with basic user behaviors:
- `TenantUser`: Simulates users browsing the web interface (75% of traffic)
- `APIUser`: Simulates API clients making requests (25% of traffic)

### `advanced_scenarios.py`
Advanced workflow testing:
- `POSUser`: Complete POS sale workflows
- `InventoryUser`: Inventory management operations
- `ReportUser`: Report generation and export
- `CRMUser`: Customer management operations

### `test_data_setup.py`
Script to generate test data:
- Creates test tenant, users, and branches
- Generates 500 inventory items
- Creates 200 customers
- Generates 100 sales transactions

## Quick Start

### 1. Setup Test Data

```bash
# Run inside Docker container
docker compose exec web python tests/performance/test_data_setup.py
```

### 2. Run Basic Performance Tests

```bash
# Using the convenience script (recommended)
./scripts/run_performance_tests.sh

# Or manually with custom parameters
./scripts/run_performance_tests.sh 50 5 120s http://localhost:8000
# Arguments: users spawn_rate run_time host
```

### 3. Run Advanced Scenario Tests

```bash
docker compose exec web locust \
    -f tests/performance/advanced_scenarios.py \
    --headless \
    --users 20 \
    --spawn-rate 2 \
    --run-time 60s \
    --host http://localhost:8000 \
    --html tests/performance/advanced_report.html
```

## Running with Web UI

For interactive testing with real-time charts:

```bash
# Start Locust web UI
docker compose exec web locust \
    -f tests/performance/locustfile.py \
    --host http://localhost:8000

# Then open browser to: http://localhost:8089
```

## Test Scenarios

### Basic Tests (locustfile.py)

**TenantUser Behavior:**
- Login authentication
- View dashboard
- Browse inventory list
- View inventory details
- View sales list
- View customers list
- Access POS interface
- Search inventory

**APIUser Behavior:**
- JWT token authentication
- List inventory items
- Get inventory details
- List sales
- List customers
- Get dashboard statistics

### Advanced Tests (advanced_scenarios.py)

**POS Sale Workflow:**
1. Load POS interface
2. Search for products
3. Add items to cart
4. Select customer
5. Complete sale transaction

**Inventory Management:**
1. Browse with pagination
2. Filter by category/karat
3. View item details
4. Check low stock
5. View valuation reports

**Report Generation:**
1. Daily sales reports
2. Sales by product
3. Customer analytics
4. Financial summaries
5. PDF export

**Customer Management:**
1. Browse customers
2. Search customers
3. View profiles
4. Check loyalty points
5. View purchase history

## Analyzing Results

### Command Line Output

The script displays:
- Request statistics (count, failures, avg/min/max response times)
- Requests per second
- Failure rates

### HTML Report

Generated at `tests/performance/report.html`:
- Response time charts
- Requests per second over time
- Response time distribution
- Failure statistics

### CSV Files

- `results_stats.csv`: Detailed statistics per endpoint
- `results_failures.csv`: All failed requests with details

## Performance Optimization Checklist

If tests reveal performance issues, check:

### Database
- [ ] Indexes on frequently queried fields
- [ ] select_related/prefetch_related usage
- [ ] Query count (N+1 problems)
- [ ] PgBouncer connection pooling
- [ ] Slow query log analysis

### Caching
- [ ] Redis cache configuration
- [ ] Query result caching
- [ ] Template fragment caching
- [ ] API response caching

### Frontend
- [ ] Asset compression enabled
- [ ] CSS/JS minification
- [ ] Image lazy loading
- [ ] Browser caching headers
- [ ] CDN usage for static files

### API
- [ ] Pagination on list endpoints
- [ ] Response compression (gzip)
- [ ] Rate limiting configured
- [ ] Unnecessary data serialization

### Application
- [ ] Background tasks for heavy operations
- [ ] Celery worker capacity
- [ ] Memory usage optimization
- [ ] Code profiling results

## Continuous Performance Testing

### In CI/CD Pipeline

Add to GitHub Actions:

```yaml
- name: Performance Tests
  run: |
    docker compose up -d
    docker compose exec -T web python tests/performance/test_data_setup.py
    docker compose exec -T web locust \
      -f tests/performance/locustfile.py \
      --headless \
      --users 10 \
      --spawn-rate 2 \
      --run-time 60s \
      --host http://localhost:8000
```

### Regular Monitoring

Schedule weekly performance tests:
- Compare results over time
- Track performance degradation
- Identify optimization opportunities
- Validate performance after deployments

## Troubleshooting

### "Connection refused" errors
- Ensure Docker containers are running: `docker compose ps`
- Check web service is healthy: `docker compose logs web`
- Verify host URL is correct

### "Authentication failed" errors
- Run test data setup script first
- Check test user credentials in locustfile.py
- Verify Django authentication is working

### Low requests per second
- Increase number of users
- Reduce wait time between requests
- Check for bottlenecks in application
- Monitor system resources (CPU, memory, disk)

### High failure rates
- Check application logs: `docker compose logs web`
- Review failed requests in CSV file
- Verify test data exists
- Check database connections

## Best Practices

1. **Always run tests in Docker** - Matches production environment
2. **Use realistic test data** - Reflects actual usage patterns
3. **Test incrementally** - Start with low load, increase gradually
4. **Monitor system resources** - Watch CPU, memory, disk I/O
5. **Test different scenarios** - Mix of read/write operations
6. **Document baselines** - Track performance over time
7. **Test after changes** - Verify optimizations work
8. **Simulate real users** - Include think time between actions

## Resources

- [Locust Documentation](https://docs.locust.io/)
- [Django Performance Tips](https://docs.djangoproject.com/en/4.2/topics/performance/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Redis Performance Best Practices](https://redis.io/docs/management/optimization/)
