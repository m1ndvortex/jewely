# Nginx Configuration for Jewelry SaaS Platform

This directory contains the Nginx configuration for the Jewelry SaaS Platform, implementing reverse proxy, static file serving, SSL/TLS termination, and security features.

## Directory Structure

```
docker/nginx/
├── nginx.conf                      # Main Nginx configuration
├── conf.d/
│   └── jewelry-shop.conf          # Site-specific configuration
├── snippets/
│   ├── gzip.conf                  # Gzip compression settings
│   ├── security-headers.conf      # Security headers (HSTS, CSP, etc.)
│   ├── ssl-params.conf            # SSL/TLS parameters
│   └── proxy-params.conf          # Reverse proxy parameters
├── ssl/
│   └── dhparam.pem               # Diffie-Hellman parameters (generate)
└── README.md                      # This file
```

## Features Implemented

### ✅ Requirement 22 Compliance

1. **Reverse Proxy to Django Backend** - Routes requests to Django application
2. **Static File Serving** - Serves static and media files directly
3. **SSL/TLS Termination** - Handles HTTPS with Let's Encrypt support
4. **HTTP/2 Support** - Enabled for improved performance
5. **Security Headers** - HSTS, CSP, X-Frame-Options, X-Content-Type-Options
6. **Rate Limiting** - Per-IP rate limiting for different endpoints
7. **Gzip Compression** - Compresses text-based files
8. **WebSocket Support** - Proxies WebSocket connections
9. **Request Logging** - Logs with response times and upstream times
10. **Prometheus Metrics** - Exposes metrics via stub_status

## Development vs Production

### Development Mode (Current Configuration)

The current configuration in `conf.d/jewelry-shop.conf` is set up for development:

- HTTP only (port 80)
- No SSL/TLS
- Direct proxy to Django
- Simplified configuration

### Production Mode

For production deployment, you need to:

1. **Generate Diffie-Hellman Parameters:**
   ```bash
   docker compose exec nginx openssl dhparam -out /etc/nginx/ssl/dhparam.pem 4096
   ```

2. **Obtain SSL Certificates:**
   - Use Let's Encrypt with certbot (see docker-compose.yml)
   - Or provide your own certificates

3. **Update Configuration:**
   - Edit `conf.d/jewelry-shop.conf`
   - Replace `your-domain.com` with your actual domain
   - Uncomment the HTTPS server block
   - Comment out the HTTP location / block (keep redirect)
   - Update `ssl_trusted_certificate` path in `snippets/ssl-params.conf`

4. **Enable Security Features:**
   - All security headers are already configured
   - Rate limiting is active
   - HSTS will force HTTPS

## Rate Limiting Zones

The configuration includes four rate limiting zones:

| Zone    | Rate          | Purpose                    |
|---------|---------------|----------------------------|
| general | 10 req/sec    | General website traffic    |
| api     | 20 req/sec    | API endpoints              |
| login   | 5 req/min     | Login endpoints (brute force prevention) |
| admin   | 10 req/sec    | Admin panel                |

Adjust these rates in `nginx.conf` based on your traffic patterns.

## Security Headers

The following security headers are configured in `snippets/security-headers.conf`:

- **HSTS**: Forces HTTPS for 1 year
- **CSP**: Content Security Policy to prevent XSS
- **X-Frame-Options**: Prevents clickjacking
- **X-Content-Type-Options**: Prevents MIME sniffing
- **X-XSS-Protection**: XSS protection for older browsers
- **Referrer-Policy**: Controls referrer information
- **Permissions-Policy**: Disables unnecessary browser features

### Customizing CSP

The Content Security Policy may need adjustment based on your specific needs. Edit `snippets/security-headers.conf` to modify the CSP directive.

## SSL/TLS Configuration

The SSL configuration in `snippets/ssl-params.conf` implements:

- **TLS 1.2 and 1.3 only** - No older protocols
- **Strong ciphers** - Modern, secure cipher suites
- **OCSP stapling** - Certificate validation
- **Session caching** - Performance optimization
- **Perfect Forward Secrecy** - DHE/ECDHE ciphers

## Static and Media Files

### Static Files
- **Path**: `/static/`
- **Location**: `/app/staticfiles/`
- **Cache**: 30 days
- **Access log**: Disabled for performance

### Media Files
- **Path**: `/media/`
- **Location**: `/app/media/`
- **Cache**: 7 days
- **Security**: Script execution prevented

## WebSocket Support

WebSocket connections are supported at `/ws/` with:
- Proper upgrade headers
- Long-lived connection timeouts (7 days)
- HTTP/1.1 protocol

## Monitoring and Metrics

### Nginx Status
- **Endpoint**: `/nginx_status`
- **Access**: Restricted to localhost and Docker network
- **Purpose**: Prometheus metrics collection

### Application Metrics
- **Endpoint**: `/metrics`
- **Access**: Restricted to localhost and Docker network
- **Purpose**: Django application metrics

## Logging

### Access Logs
- **Format**: Custom format with response times
- **Location**: `/var/log/nginx/access.log`
- **Includes**: Request time, upstream times, status codes

### Error Logs
- **Level**: warn
- **Location**: `/var/log/nginx/error.log`

### JSON Logging
A JSON log format is also available for structured logging. To use it, change the access_log directive in `conf.d/jewelry-shop.conf`:

```nginx
access_log /var/log/nginx/access.log json_combined;
```

## Performance Optimizations

The configuration includes several performance optimizations:

1. **Sendfile**: Efficient file transfer
2. **TCP optimizations**: tcp_nopush, tcp_nodelay
3. **Keepalive connections**: To upstream servers
4. **Gzip compression**: For text-based files
5. **Static file caching**: Long cache times
6. **Buffer tuning**: Optimized buffer sizes
7. **Worker processes**: Auto-scaled to CPU cores

## Load Balancing

The upstream configuration supports multiple Django servers:

```nginx
upstream django_backend {
    least_conn;
    server web:8000 max_fails=3 fail_timeout=30s;
    server web2:8000 max_fails=3 fail_timeout=30s;  # Add more servers
    keepalive 32;
}
```

Uncomment additional servers in `conf.d/jewelry-shop.conf` for horizontal scaling.

## Testing Configuration

Before deploying, test the configuration:

```bash
# Test syntax
docker compose exec nginx nginx -t

# Reload configuration
docker compose exec nginx nginx -s reload

# View logs
docker compose logs -f nginx
```

## Troubleshooting

### Common Issues

1. **502 Bad Gateway**
   - Check if Django is running: `docker compose ps web`
   - Check upstream configuration
   - Verify network connectivity

2. **Static files not loading**
   - Verify volume mounts in docker-compose.yml
   - Check file permissions
   - Run `python manage.py collectstatic`

3. **SSL certificate errors**
   - Verify certificate paths
   - Check certificate validity
   - Ensure certbot renewal is working

4. **Rate limiting too strict**
   - Adjust rates in nginx.conf
   - Increase burst values
   - Monitor access logs

### Useful Commands

```bash
# Check Nginx version and modules
docker compose exec nginx nginx -V

# View active connections
docker compose exec nginx cat /var/run/nginx.pid | xargs ps aux | grep

# Monitor access log in real-time
docker compose exec nginx tail -f /var/log/nginx/access.log

# Check error log
docker compose exec nginx tail -f /var/log/nginx/error.log
```

## Security Considerations

1. **Keep Nginx updated** - Use latest stable version
2. **Monitor logs** - Watch for suspicious activity
3. **Adjust rate limits** - Based on legitimate traffic patterns
4. **Review CSP** - Ensure it matches your application needs
5. **Certificate renewal** - Automate with certbot
6. **Firewall rules** - Restrict access to necessary ports only

## References

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [Let's Encrypt](https://letsencrypt.org/)
