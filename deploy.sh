#!/bin/bash
# ==============================================================================
# eudragent.com - One-Click Production Deployment Script
# ==============================================================================
set -e

echo "🌲 [EUDRAgent.com] Starting Production Deployment..."

DOMAIN="eudragent.com"
EMAIL="admin@eudragent.com"

# 1. Check if .env.production exists, otherwise copy from example
if [ ! -f .env.production ]; then
    echo "⚠️  .env.production not found. Copying from .env.production.example..."
    cp .env.production.example .env.production
    echo "❗ Please review and edit passwords in .env.production before public launch."
fi

# 2. Pull and build latest production images
echo "📦 Building Docker containers for eudragent.com..."
docker compose -f docker-compose.prod.yml --env-file .env.production build --no-cache

# 3. Launch database and backend services
echo "🚀 Starting PostGIS, Redis, Web API, and Celery Workers..."
docker compose -f docker-compose.prod.yml --env-file .env.production up -d db redis web worker

# 4. Wait for Web API to become healthy
echo "⏳ Waiting for FastAPI service to initialize..."
sleep 8

# 5. Launch Nginx & Certbot for SSL
echo "🔒 Launching Nginx Reverse Proxy with HTTPS..."
docker compose -f docker-compose.prod.yml --env-file .env.production up -d nginx certbot

echo "======================================================================"
echo "✅ eudragent.com deployment initiated successfully!"
echo "🌐 Landing Page: https://${DOMAIN}/"
echo "🖥️  Enterprise Console: https://${DOMAIN}/dashboard"
echo "📖 API Swagger Docs: https://${DOMAIN}/docs"
echo "======================================================================"
