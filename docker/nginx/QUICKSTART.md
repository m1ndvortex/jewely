# Nginx Quick Start Guide

## Development (Current Setup)

### Start Services
```bash
docker compose up -d
```

### Access Application
- **Application**: http://localhost
- **Admin Panel**: http://localhost/admin/
- **API**: http://localhost/api/
- **Health Check**: http://localhost/health/

### View Logs
```bash
# All nginx logs
docker compose logs -f nginx

# Access log only
docker compose exec nginx tail -f /var/log/nginx/access.log

# Error log only
docker compose exec nginx tail -f /var/log/nginx/error.log
```

### Test Configuration
```bash
# Test syntax
docker compose exec nginx nginx -t

# Reload after changes
docker compose exec nginx nginx -s reload
```

## Production Deployment

### Prerequisites
1. Domain name pointing to your server
2. Ports 80 and 443 open in firewall
3. DNS A records configured

### Quick Setup (5 steps)

#### 1. Generate DH Parameters (10-30 minutes)
```bash
docker compose exec nginx openssl dhparam -out /etc/nginx/ssl/dhparam.pem 4096
```

#### 2. Obtain SSL Certificate
```bash
./docker/nginx/setup-ssl.sh your-domain.com admin@your-domain.com
```

#### 3. Update Configuration
Edit `docker/nginx/conf.d/jewelry-shop.conf`:
- Replace `your-domain.com` with your domain
- Uncomment HTTPS server block (lines ~100-250)
- Comment out HTTP location / block (lines ~30-40)

#### 4. Update Environment
Edit `.env`:
```bash
NGINX_DOMAIN=your-domain.com
LETSENCRYPT_EMAIL=admin@your-domain.com
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

#### 5. Reload Nginx
```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

### Verify
```bash
# Test HTTPS
curl -I https://your-domain.com

# Check SSL Labs
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=your-domain.com
```

## Common Commands

### Service Management
```bash
# Start nginx
docker compose up -d nginx

# Stop nginx
docker compose stop nginx

# Restart nginx
docker compose restart nginx

# View status
docker compose ps nginx
```

### Configuration
```bash
# Test configuration
docker compose exec nginx nginx -t

# Reload configuration
docker compose exec nginx nginx -s reload

# View full configuration
docker compose exec nginx nginx -T
```

### Logs
```bash
# Follow all logs
docker compose logs -f nginx

# Last 100 lines
docker compose logs --tail=100 nginx

# Find errors
docker compose exec nginx grep "error" /var/log/nginx/error.log

# Find slow requests (>1 second)
docker compose exec nginx awk '$NF > 1' /var/log/nginx/access.log
```

### SSL/TLS
```bash
# Check certificate
docker compose exec nginx openssl x509 -in /etc/letsencrypt/live/your-domain.com/fullchain.pem -text -noout

# Test SSL connection
docker compose exec nginx openssl s_client -connect localhost:443 -servername your-domain.com

# Renew certificate (manual)
docker compose run --rm certbot renew

# Test renewal
docker compose run --rm certbot renew --dry-run
```

### Monitoring
```bash
# View nginx metrics
curl http://localhost:9113/metrics

# View nginx status
docker compose exec nginx curl http://localhost/nginx_status

# Check connections
docker compose exec nginx netstat -an | grep :80
```

## Troubleshooting

### 502 Bad Gateway
```bash
# Check Django is running
docker compose ps web

# Test connectivity
docker compose exec nginx wget -O- http://web:8000/health/

# Check logs
docker compose logs web
```

### Static Files Not Loading
```bash
# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Check volume mount
docker compose exec nginx ls -la /app/staticfiles/

# Check permissions
docker compose exec nginx ls -la /app/staticfiles/admin/
```

### Rate Limiting Issues
```bash
# Check for 429 errors
docker compose exec nginx grep " 429 " /var/log/nginx/access.log

# Adjust rate limits in docker/nginx/nginx.conf
# Then reload: docker compose exec nginx nginx -s reload
```

### SSL Certificate Issues
```bash
# Check certbot logs
docker compose logs certbot

# Verify certificate files
docker compose exec nginx ls -la /etc/letsencrypt/live/your-domain.com/

# Test certificate renewal
docker compose run --rm certbot renew --dry-run
```

## Performance Testing

### Apache Bench
```bash
# Test homepage
ab -n 1000 -c 10 http://localhost/

# Test static files
ab -n 1000 -c 10 http://localhost/static/admin/css/base.css
```

### Expected Results
- Static files: 10,000+ req/sec
- Dynamic pages: 500-1000 req/sec
- API endpoints: 1000-2000 req/sec

## Security Checklist

Before production:
- [ ] SSL certificate obtained
- [ ] HSTS enabled
- [ ] CSP configured
- [ ] Rate limiting tested
- [ ] Firewall configured
- [ ] DH parameters generated
- [ ] Server tokens disabled
- [ ] SSL Labs test passed (A+)

## Need Help?

1. Check `docker/nginx/README.md` for detailed configuration info
2. Check `docs/NGINX_CONFIGURATION.md` for comprehensive guide
3. Review nginx error logs
4. Consult Nginx documentation: https://nginx.org/en/docs/

## Quick Links

- **Configuration**: `docker/nginx/`
- **Site Config**: `docker/nginx/conf.d/jewelry-shop.conf`
- **Security**: `docker/nginx/snippets/security-headers.conf`
- **SSL Setup**: `./docker/nginx/setup-ssl.sh`
- **Full Guide**: `docs/NGINX_CONFIGURATION.md`
