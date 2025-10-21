.PHONY: help build up down restart logs shell test migrate makemigrations createsuperuser clean

help:
	@echo "Available commands:"
	@echo "  make build          - Build Docker images"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs (all services)"
	@echo "  make logs-web       - View web service logs"
	@echo "  make logs-celery    - View celery worker logs"
	@echo "  make shell          - Access Django shell"
	@echo "  make dbshell        - Access database shell"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage"
	@echo "  make migrate        - Run database migrations"
	@echo "  make makemigrations - Create new migrations"
	@echo "  make createsuperuser - Create Django superuser"
	@echo "  make format         - Format code with black and isort"
	@echo "  make lint           - Run linters"
	@echo "  make clean          - Stop services and remove volumes"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-celery:
	docker-compose logs -f celery_worker

shell:
	docker-compose exec web python manage.py shell

dbshell:
	docker-compose exec db psql -U postgres -d jewelry_shop

test:
	docker-compose exec web pytest

test-cov:
	docker-compose exec web pytest --cov=apps --cov=config --cov-report=html --cov-report=term

migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

format:
	docker-compose exec web black .
	docker-compose exec web isort .

lint:
	docker-compose exec web flake8 .
	docker-compose exec web mypy .

clean:
	docker-compose down -v
