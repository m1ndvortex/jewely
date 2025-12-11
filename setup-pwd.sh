#!/bin/bash
# Play with Docker Setup Script
# Run this on play-with-docker.com

set -e

echo "🐳 Setting up Jewelry Shop SaaS on Play with Docker"
echo "=================================================="

# Check if Docker Swarm is initialized
if ! docker info | grep -q "Swarm: active"; then
    echo "📋 Step 1: Initializing Docker Swarm..."
    docker swarm init --advertise-addr eth0
    echo "✅ Swarm initialized!"
else
    echo "✅ Swarm already initialized"
fi

# Check if we need to build the image
if ! docker images | grep -q "jewelry-shop"; then
    echo "📦 Step 2: Building Docker image (this may take a few minutes)..."
    docker build -t jewelry-shop:latest -f Dockerfile .
    echo "✅ Image built!"
else
    echo "✅ Image already exists"
fi

# Run migrations in a temporary container
echo "🗄️  Step 3: Running database migrations..."
docker stack deploy -c docker-stack-pwd.yml jewelry

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 15

# Run migrations
docker run --rm \
    --network jewelry_backend \
    -e DATABASE_URL=postgres://postgres:postgres123@db:5432/jewelry_shop \
    -e DJANGO_SETTINGS_MODULE=config.settings.base \
    jewelry-shop:latest \
    python manage.py migrate --noinput

echo "👤 Step 4: Creating superuser..."
docker run --rm \
    --network jewelry_backend \
    -e DATABASE_URL=postgres://postgres:postgres123@db:5432/jewelry_shop \
    -e DJANGO_SETTINGS_MODULE=config.settings.base \
    jewelry-shop:latest \
    python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
    print('Superuser created!')
else:
    print('Superuser already exists')
"

echo "📊 Step 5: Checking service status..."
docker service ls

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Access your app at:"
echo "   http://ip<session_id>-80.direct.labs.play-with-docker.com"
echo ""
echo "🔐 Login credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "📈 Monitor services:"
echo "   docker service ls"
echo "   docker service ps jewelry_web"
echo "   docker service logs -f jewelry_web"
echo ""
echo "🔄 Scale services:"
echo "   docker service scale jewelry_web=5"
echo "   docker service scale jewelry_celery_worker=3"
echo ""
echo "🧪 Test self-healing (kill a container):"
echo "   docker ps"
echo "   docker kill <container_id>"
echo "   docker service ps jewelry_web  # Watch it restart"
echo ""
