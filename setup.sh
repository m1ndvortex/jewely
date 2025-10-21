#!/bin/bash
# Setup script for Jewelry Shop SaaS Platform

set -e

echo "🚀 Setting up Jewelry Shop SaaS Platform..."
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi
echo ""

# Build Docker images
echo "🔨 Building Docker images..."
docker compose build
echo "✅ Docker images built"
echo ""

# Start services
echo "🚀 Starting services..."
docker compose up -d
echo "✅ Services started"
echo ""

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Run migrations
echo "🗄️  Running database migrations..."
docker compose exec web python manage.py migrate
echo "✅ Migrations completed"
echo ""

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
if [ -f .git/hooks/pre-commit ]; then
    chmod +x .git/hooks/pre-commit
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  Pre-commit hook file not found. It should be at .git/hooks/pre-commit"
fi
echo ""

# Run tests
echo "🧪 Running tests..."
docker compose exec web pytest
echo "✅ Tests passed"
echo ""

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Create a superuser: docker compose exec web python manage.py createsuperuser"
echo "   2. Access the application: http://localhost:8000"
echo "   3. Access the admin panel: http://localhost:8000/admin"
echo "   4. View logs: docker compose logs -f web"
echo ""
echo "📚 For more information, see README.md"
