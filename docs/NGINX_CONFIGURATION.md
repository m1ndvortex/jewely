# Nginx Configuration Guide

This document provides comprehensive guidance on the Nginx configuration for the Jewelry SaaS Platform, covering setup, deployment, security, and troubleshooting.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Development Setup](#development-setup)
4. [Production Deployment](#production-deployment)
5. [SSL/TLS Configuration](#ssltls-configuration)
6. [Security Features](#security-features)
7. [Performance Optimization](#performance-optimization)
8. [Monitoring and Metrics](#monitoring-and-metrics)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

## Overview

The Nginx configuration implements all requirements from **Requirement 22: Nginx Configuration and Reverse Proxy**:

✅ Reverse proxy to Django backend  
✅ Static and media file serving  
✅ SSL/TLS termination with Let's Encrypt  
✅ HTTP/2 support  
✅ Security headers (HSTS, CSP, X-Frame-Options, etc.)  
✅ Rate limiting per IP address  
✅ Gzip compression  
✅ WebSocket proxy support  
✅ Request logging with response times  
✅ Prometheus metrics export  

## Architecture

```
Internet
    │
    ▼
┌─────────────────┐
│  Nginx (Port 80/443)  │
│  - SSL Termination    │
│  - Rate Limiting      │
│  - Static Files       │
│  - Security Headers   │
└─────────────────┘
    │
    ├─────────────────────┐
    │                     │
    ▼                     ▼
┌─────────────┐    ┌─────────────┐
│   Django    │    │   Static    │
│  (Port 8000)│    │   Files     │
└─────────────┘    └─────────────┘
    │
    ▼
┌─────────────┐
│  Prometheus │
│   Metrics   │
└─────────────┘
```

## Development Setup

### Quick Start

1. **Start all services:**
   ```bash
   docker compose up -d
   ```

2. **Access the application:**
   - Application: http://localhost
   - Django Admin: http://localhost/admin/
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000

3. **View nginx logs:**
   ```bash
   docker compose logs -f nginx
   ```

### Configuration Files

The development configuration uses HTTP only (no SSL):

- `docker/nginx/nginx.conf` - Main configuration
- `docker/nginx/conf.d/jewelry-shop.conf` - Site configuration
- `docker/nginx/snippets/` - Reusable configuration snippets

### Testing Configuration

```bash
# Test nginx configuration syntax
docker compose exec nginx nginx -t

# Reload nginx after changes
docker compose exec nginx nginx -s reload

# View nginx version and modules
docker compose exec nginx nginx -V
```

## Production Deployment

### Prerequisites

1. **Domain name** pointing to your server
2. **Firewall rules** allowing ports 80 and 443
3. **DNS records** configured:
   - A record: `your-domain.com` → Server IP
   - A record: `www.your-domain.com` → Server IP

### Step-by-Step Deployment

#### 1. Generate Diffie-Hellman Parameters

```bash
# This takes 10-30 minutes
docker compose exec nginx /bin/sh -c "openssl dhparam -out /etc/nginx/ssl/dhparam.pem 4096"
```

Or use the provided script:
```bash
docker compose exec nginx /docker/nginx/generate-dhparam.sh
```

#### 2. Obtain SSL Certificate

Use the provided script:
```bash
./docker/nginx/setup-ssl.sh your-domain.com admin@your-domain.com
```

Or manually:
```bash
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@your-domain.com \
    --agree-tos \
    --no-eff-email \
    -d your-domain.com \
    -d www.your-domain.com
```

#### 3. Update Configuration

Edit `docker/nginx/conf.d/jewelry-shop.conf`:

```nginx
# 1. In the HTTP server block, comment out the location / block:
# location / {
#     ...
# }

# 2. Uncomment the redirect:
location / {
    return 301 https://$host$request_uri;
}

# 3. Uncomment the entire HTTPS server block
# 4. Replace 'your-domain.com' with your actual domain
```

Edit `docker/nginx/snippets/ssl-params.conf`:

```nginx
# Update the ssl_trusted_certificate path:
ssl_trusted_certificate /etc/letsencrypt/live/your-domain.com/chain.pem;
```

#### 4. Update Environment Variables

Edit `.env`:
```bash
NGINX_DOMAIN=your-domain.com
LETSENCRYPT_EMAIL=admin@your-domain.com
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

#### 5. Reload Nginx

```bash
# Test configuration
docker compose exec nginx nginx -t

# Reload if test passes
docker compose exec nginx nginx -s reload
```

#### 6. Verify SSL

```bash
# Check SSL certificate
curl -vI https://your-domain.com

# Test SSL configuration
docker compose exec nginx openssl s_client -connect localhost:443 -servername your-domain.com
```

### Certificate Auto-Renewal

The certbot service automatically renews certificates every 12 hours. Monitor renewal:

```bash
# View certbot logs
docker compose logs -f certbot

# Manually trigger renewal (for testing)
docker compose run --rm certbot renew --dry-run
```

## SSL/TLS Configuration

### Protocols and Ciphers

The configuration uses:
- **Protocols**: TLS 1.2 and 1.3 only
- **Ciphers**: Modern, secure cipher suites
- **Perfect Forward Secrecy**: ECDHE and DHE ciphers

### OCSP Stapling

OCSP stapling is enabled for faster certificate validation:

```nginx
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/letsencrypt/live/your-domain.com/chain.pem;
```

### Testing SSL Configuration

Use SSL Labs to test your configuration:
https://www.ssllabs.com/ssltest/analyze.html?d=your-domain.com

Target: **A+ rating**

## Security Features

### Security Headers

All security headers are configured in `snippets/security-headers.conf`:

| Header | Value | Purpose |
|--------|-------|---------|
| Strict-Transport-Security | max-age=31536000 | Force HTTPS for 1 year |
| Content-Security-Policy | (see config) | Prevent XSS attacks |
| X-Frame-Options | DENY | Prevent clickjacking |
| X-Content-Type-Options | nosniff | Prevent MIME sniffing |
| X-XSS-Protection | 1; mode=block | XSS protection (legacy) |
| Referrer-Policy | strict-origin-when-cross-origin | Control referrer info |
| Permissions-Policy | (see config) | Disable unnecessary features |

### Rate Limiting

Four rate limiting zones are configured:

```nginx
# General traffic: 10 requests/second
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;

# API endpoints: 20 requests/second
limit_req_zone $binary_remote_addr zone=api:10m rate=20r/s;

# Login endpoints: 5 requests/minute (brute force prevention)
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

# Admin panel: 10 requests/second
limit_req_zone $binary_remote_addr zone=admin:10m rate=10r/s;
```

### Adjusting Rate Limits

Edit `docker/nginx/nginx.conf` to adjust rates based on your traffic:

```nginx
# Example: Increase API rate limit
limit_req_zone $binary_remote_addr zone=api:10m rate=50r/s;
```

Then reload:
```bash
docker compose exec nginx nginx -s reload
```

### Content Security Policy (CSP)

The CSP is configured to allow:
- Self-hosted resources
- CDN resources (jsDelivr, unpkg)
- Google Fonts
- Stripe API

**Customize CSP** in `snippets/security-headers.conf` based on your needs:

```nginx
add_header Content-Security-Policy "
    default-src 'self';
    script-src 'self' 'unsafe-inline' https://cdn.example.com;
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    ...
" always;
```

## WebSocket Proxying

### Overview

WebSocket support is configured for real-time features like notifications, live updates, and chat functionality. The configuration handles WebSocket upgrade requests and maintains long-lived connections.

### Configuration

WebSocket proxying is configured in `snippets/websocket.conf`:

```nginx
# Use HTTP/1.1 for WebSocket
proxy_http_version 1.1;

# WebSocket upgrade headers
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";

# WebSocket connection timeouts (24 hours)
proxy_connect_timeout 24h;
proxy_send_timeout 24h;
proxy_read_timeout 24h;

# Disable buffering for WebSocket
proxy_buffering off;

# Keep connection alive
tcp_nodelay on;
```

### Usage

WebSocket connections are handled at the `/ws/` location:

```nginx
location /ws/ {
    # Rate limiting for WebSocket connections
    limit_req zone=general burst=10 nodelay;
    limit_conn addr 5;
    
    # Proxy to Django
    include /etc/nginx/snippets/proxy-params.conf;
    proxy_pass http://django_backend;
    
    # WebSocket specific configuration
    include /etc/nginx/snippets/websocket.conf;
}
```

### Timeout Configuration

The default timeout is **24 hours**, which is appropriate for most WebSocket applications. Adjust if needed:

```nginx
# For shorter-lived connections (e.g., 1 hour)
proxy_connect_timeout 1h;
proxy_send_timeout 1h;
proxy_read_timeout 1h;

# For very long-lived connections (e.g., 7 days)
proxy_connect_timeout 7d;
proxy_send_timeout 7d;
proxy_read_timeout 7d;
```

### Testing WebSocket Connections

#### Using wscat (WebSocket CLI tool)

```bash
# Install wscat
npm install -g wscat

# Test WebSocket connection
wscat -c ws://localhost/ws/notifications/

# Test with authentication
wscat -c ws://localhost/ws/notifications/ -H "Authorization: Bearer YOUR_TOKEN"
```

#### Using JavaScript

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost/ws/notifications/');

// Connection opened
ws.addEventListener('open', (event) => {
    console.log('WebSocket connected');
    ws.send('Hello Server!');
});

// Listen for messages
ws.addEventListener('message', (event) => {
    console.log('Message from server:', event.data);
});

// Connection closed
ws.addEventListener('close', (event) => {
    console.log('WebSocket disconnected');
});

// Error handling
ws.addEventListener('error', (event) => {
    console.error('WebSocket error:', event);
});
```

#### Using Python

```python
import asyncio
import websockets

async def test_websocket():
    uri = "ws://localhost/ws/notifications/"
    async with websockets.connect(uri) as websocket:
        # Send message
        await websocket.send("Hello Server!")
        
        # Receive message
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_websocket())
```

### Monitoring WebSocket Connections

#### Check Active Connections

```bash
# View nginx status
docker compose exec nginx curl http://localhost/nginx_status

# Output includes:
# Active connections: 15
# Reading: 0 Writing: 1 Waiting: 14
```

#### Monitor WebSocket Traffic

```bash
# View access logs for WebSocket requests
docker compose exec nginx grep "/ws/" /var/log/nginx/access.log

# Monitor in real-time
docker compose exec nginx tail -f /var/log/nginx/access.log | grep "/ws/"
```

### Troubleshooting WebSocket Issues

#### 1. Connection Upgrade Failed

**Symptoms**: WebSocket connection fails with 400 or 426 error

**Causes**:
- Missing Upgrade header
- HTTP/1.0 instead of HTTP/1.1
- Proxy not configured correctly

**Solutions**:
```bash
# Verify websocket.conf is included
docker compose exec nginx grep -r "websocket.conf" /etc/nginx/

# Check nginx error log
docker compose exec nginx tail -f /var/log/nginx/error.log

# Test with curl
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost/ws/test/
```

#### 2. Connection Timeout

**Symptoms**: WebSocket connection drops after a period

**Causes**:
- Timeout values too short
- Firewall closing idle connections
- Load balancer timeout

**Solutions**:
```bash
# Increase timeouts in websocket.conf
proxy_read_timeout 48h;

# Implement ping/pong heartbeat in application
# Send ping every 30 seconds to keep connection alive
```

#### 3. High Memory Usage

**Symptoms**: Nginx memory usage increases with WebSocket connections

**Causes**:
- Too many concurrent connections
- Memory leak in application
- Buffering enabled

**Solutions**:
```bash
# Limit concurrent connections
limit_conn addr 5;

# Ensure buffering is disabled
proxy_buffering off;

# Monitor memory usage
docker stats jewelry_shop_nginx
```

### Rate Limiting for WebSocket

WebSocket connections are rate-limited to prevent abuse:

```nginx
# Allow 10 connection attempts per second
limit_req zone=general burst=10 nodelay;

# Maximum 5 concurrent connections per IP
limit_conn addr 5;
```

Adjust based on your application needs:

```nginx
# For applications with many concurrent connections
limit_conn addr 20;

# For stricter rate limiting
limit_req zone=general burst=5 nodelay;
```

### Security Considerations

1. **Authentication**: Always authenticate WebSocket connections
2. **Origin Validation**: Validate the Origin header to prevent CSRF
3. **Rate Limiting**: Implement rate limiting to prevent DoS attacks
4. **Encryption**: Use WSS (WebSocket Secure) in production
5. **Timeout**: Set reasonable timeouts to prevent resource exhaustion

### Production Deployment

For production with SSL, WebSocket connections use WSS:

```javascript
// Use wss:// instead of ws://
const ws = new WebSocket('wss://your-domain.com/ws/notifications/');
```

The HTTPS server block automatically handles WSS connections with the same configuration.

## Performance Optimization

### Gzip Compression

Gzip compression is enabled for text-based files:

```nginx
gzip on;
gzip_comp_level 6;
gzip_types text/plain text/css application/json ...;
```

**Compression ratio**: Typically 70-80% size reduction

### Static File Caching

Static files are cached with long expiration:

```nginx
location /static/ {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

### Connection Keepalive

Keepalive connections to upstream servers:

```nginx
upstream django_backend {
    keepalive 32;
}
```

### Buffer Tuning

Optimized buffer sizes for performance:

```nginx
client_body_buffer_size 128k;
client_max_body_size 100M;
```

## Monitoring and Metrics

### Nginx Metrics

Nginx metrics are exposed via stub_status:

```nginx
location /nginx_status {
    stub_status on;
    access_log off;
    allow 127.0.0.1;
    allow 172.16.0.0/12;  # Docker network
    deny all;
}
```

### Prometheus Integration

The `nginx_exporter` service scrapes metrics and exposes them to Prometheus:

- **Endpoint**: http://nginx_exporter:9113/metrics
- **Metrics**: Connections, requests, response codes, etc.

### Grafana Dashboards

Import Nginx dashboards in Grafana:
- Dashboard ID: 12708 (Nginx Prometheus Exporter)
- Dashboard ID: 11199 (Nginx Monitoring)

### Log Analysis

Access logs include response times:

```
$remote_addr - $remote_user [$time_local] "$request" 
$status $body_bytes_sent "$http_referer" 
"$http_user_agent" "$http_x_forwarded_for" 
rt=$request_time uct="$upstream_connect_time" 
uht="$upstream_header_time" urt="$upstream_response_time"
```

**View slow requests:**
```bash
docker compose exec nginx awk '$NF > 1' /var/log/nginx/access.log
```

## Troubleshooting

### Common Issues

#### 1. 502 Bad Gateway

**Symptoms**: Nginx returns 502 error

**Causes**:
- Django not running
- Network connectivity issue
- Upstream timeout

**Solutions**:
```bash
# Check Django status
docker compose ps web

# Check Django logs
docker compose logs web

# Test connectivity
docker compose exec nginx wget -O- http://web:8000/health/

# Increase timeouts in proxy-params.conf
proxy_read_timeout 120s;
```

#### 2. Static Files Not Loading

**Symptoms**: 404 errors for static files

**Causes**:
- Static files not collected
- Volume mount issue
- Incorrect path

**Solutions**:
```bash
# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Check volume mounts
docker compose exec nginx ls -la /app/staticfiles/

# Verify nginx configuration
docker compose exec nginx nginx -t
```

#### 3. SSL Certificate Errors

**Symptoms**: Browser shows certificate error

**Causes**:
- Certificate not obtained
- Wrong domain in certificate
- Certificate expired

**Solutions**:
```bash
# Check certificate
docker compose exec nginx openssl x509 -in /etc/letsencrypt/live/your-domain.com/fullchain.pem -text -noout

# Renew certificate
docker compose run --rm certbot renew

# Check certbot logs
docker compose logs certbot
```

#### 4. Rate Limiting Too Strict

**Symptoms**: Legitimate users getting 429 errors

**Solutions**:
```bash
# Check access logs for 429 errors
docker compose exec nginx grep " 429 " /var/log/nginx/access.log

# Adjust rate limits in nginx.conf
# Increase burst values in jewelry-shop.conf
limit_req zone=general burst=50 nodelay;
```

### Debugging Commands

```bash
# View nginx error log
docker compose exec nginx tail -f /var/log/nginx/error.log

# View access log in real-time
docker compose exec nginx tail -f /var/log/nginx/access.log

# Check nginx process
docker compose exec nginx ps aux | grep nginx

# Test upstream connectivity
docker compose exec nginx wget -O- http://web:8000/

# Check nginx configuration
docker compose exec nginx nginx -T

# View loaded modules
docker compose exec nginx nginx -V 2>&1 | grep -o with-[a-z_]*
```

## Maintenance

### Regular Tasks

#### Daily
- Monitor error logs
- Check certificate expiration
- Review rate limit hits

#### Weekly
- Analyze access logs
- Review slow requests
- Check disk space for logs

#### Monthly
- Review and update security headers
- Test SSL configuration
- Update nginx if needed

### Log Rotation

Nginx logs are automatically rotated by Docker. To manually rotate:

```bash
docker compose exec nginx nginx -s reopen
```

### Updating Nginx

```bash
# Pull latest image
docker compose pull nginx

# Recreate container
docker compose up -d nginx

# Verify
docker compose exec nginx nginx -v
```

### Backup Configuration

```bash
# Backup nginx configuration
tar -czf nginx-config-backup-$(date +%Y%m%d).tar.gz docker/nginx/

# Backup SSL certificates
docker compose exec nginx tar -czf /tmp/ssl-backup.tar.gz /etc/letsencrypt/
docker compose cp nginx:/tmp/ssl-backup.tar.gz ./ssl-backup-$(date +%Y%m%d).tar.gz
```

## Performance Benchmarking

### Using Apache Bench

```bash
# Test homepage
ab -n 1000 -c 10 http://localhost/

# Test static files
ab -n 1000 -c 10 http://localhost/static/css/main.css

# Test API endpoint
ab -n 1000 -c 10 -H "Authorization: Bearer TOKEN" http://localhost/api/inventory/
```

### Using wrk

```bash
# Install wrk
# Ubuntu: apt-get install wrk
# macOS: brew install wrk

# Run benchmark
wrk -t4 -c100 -d30s http://localhost/
```

### Expected Performance

- **Static files**: 10,000+ req/sec
- **Dynamic pages**: 500-1000 req/sec
- **API endpoints**: 1000-2000 req/sec

## Security Checklist

Before going to production:

- [ ] SSL certificate obtained and configured
- [ ] HSTS enabled with appropriate max-age
- [ ] CSP configured and tested
- [ ] Rate limiting configured and tested
- [ ] Firewall rules configured
- [ ] DH parameters generated (4096 bits)
- [ ] Server tokens disabled
- [ ] Access logs reviewed
- [ ] Error logs reviewed
- [ ] SSL Labs test passed (A+ rating)
- [ ] Security headers verified
- [ ] WebSocket connections tested (if used)
- [ ] Backup and restore procedures tested

## Additional Resources

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [Nginx Prometheus Exporter](https://github.com/nginxinc/nginx-prometheus-exporter)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review nginx error logs
3. Consult the Nginx documentation
4. Open an issue in the project repository
