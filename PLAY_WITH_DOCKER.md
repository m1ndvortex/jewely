# Testing Jewelry Shop SaaS on Play with Docker

## Quick Start (3 minutes)

### 1. Go to Play with Docker
Visit: https://labs.play-with-docker.com
- Click "Start"
- Click "+ ADD NEW INSTANCE"

### 2. Clone & Setup
```bash
# Clone your repo
git clone https://github.com/m1ndvortex/jewely.git
cd jewely

# Run setup script
chmod +x setup-pwd.sh
./setup-pwd.sh
```

### 3. Access Your App
The script will show you the URL, format:
```
http://ip<session_id>-80.direct.labs.play-with-docker.com
```

Login: `admin` / `admin123`

---

## Testing Multi-Node Swarm (Advanced)

### Add More Nodes
1. Click "+ ADD NEW INSTANCE" twice more (total 3 nodes)

2. On Node 1 (manager), get join token:
```bash
docker swarm join-token manager
```

3. On Node 2 & 3, paste the join command

4. Verify cluster:
```bash
docker node ls
```

5. Scale services across nodes:
```bash
docker service scale jewelry_web=6
docker service scale jewelry_celery_worker=3
```

---

## Test Self-Healing

### Kill a Container
```bash
# See running containers
docker ps

# Kill one
docker kill <container_id>

# Watch it auto-restart
docker service ps jewelry_web
```

### Simulate Node Failure
```bash
# On Node 2 or 3
sudo reboot

# On Node 1, watch services migrate
docker service ps jewelry_web --no-trunc
```

---

## Monitor Services

```bash
# List all services
docker service ls

# See where containers are running
docker service ps jewelry_web

# View logs
docker service logs -f jewelry_web

# Check resource usage
docker stats
```

---

## Test Load Balancing

```bash
# Make requests through nginx
for i in {1..10}; do 
  curl http://localhost/health/ 
  echo ""
done

# Check which container handled requests
docker service logs jewelry_web | grep "GET /health/"
```

---

## Rolling Updates

```bash
# Update image
docker service update --image jewelry-shop:v2 jewelry_web

# Watch rolling update
watch docker service ps jewelry_web
```

---

## What You'll See

✅ **Self-healing**: Containers restart in ~5 seconds  
✅ **Load balancing**: Requests distributed across replicas  
✅ **Zero-downtime updates**: Rolling updates with no service interruption  
✅ **High availability**: Services survive node failures  

---

## Limitations on Play with Docker

- **4-hour session limit** (resets after timeout)
- **No persistent storage** (data lost on reset)
- **Limited resources** (~1GB RAM per node)
- **No external domain** (use the generated URL)

Perfect for testing, NOT for production!

---

## Quick Commands Reference

| Command | Purpose |
|---------|---------|
| `docker service ls` | List all services |
| `docker service ps <service>` | Show service containers |
| `docker service logs <service>` | View service logs |
| `docker service scale <service>=N` | Scale to N replicas |
| `docker node ls` | List cluster nodes |
| `docker stack ps jewelry` | Show all stack containers |
| `docker service update --force jewelry_web` | Force redeploy |

---

## Troubleshooting

### Service won't start
```bash
docker service logs jewelry_web
docker service ps jewelry_web --no-trunc
```

### Database connection issues
```bash
# Check if DB is running
docker service ps jewelry_db

# Connect to database
docker exec -it $(docker ps -q -f name=jewelry_db) psql -U postgres -d jewelry_shop
```

### Reset everything
```bash
docker stack rm jewelry
docker system prune -af
./setup-pwd.sh
```
