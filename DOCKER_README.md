# Docker Deployment Guide

This guide explains how to deploy the DynamicGroundingDINO API using Docker and Docker Compose.

## 📋 Prerequisites

- **Docker**: Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/)
- **Docker Compose**: Usually included with Docker Desktop
- **System Requirements**: 
  - At least 4GB RAM (8GB recommended)
  - 2GB free disk space for Docker images
  - Optional: NVIDIA GPU with CUDA support for faster inference

## 🚀 Quick Start

### Method 1: Using Deployment Scripts (Recommended)

**For Windows:**
```bash
deploy.bat
```

**For Linux/Mac:**
```bash
chmod +x deploy.sh
./deploy.sh
```

### Method 2: Manual Docker Compose

**Basic deployment:**
```bash
docker-compose up -d
```

**Development mode with code hot-reload:**
```bash
docker-compose -f docker-compose.dev.yml up -d
```

**Production mode with Nginx reverse proxy:**
```bash
docker-compose --profile production up -d
```

**With Redis caching:**
```bash
docker-compose --profile cache up -d
```

## 📁 Docker Files Overview

### `Dockerfile`
- **Base Image**: Python 3.11 slim
- **Dependencies**: Installs all required Python packages
- **Security**: Runs as non-root user
- **Health Check**: Built-in health monitoring
- **Port**: Exposes port 8000

### `docker-compose.yml` (Production)
```yaml
# Main service configuration
- API service on port 8000
- Persistent model cache
- Memory limits and health checks
- Optional Nginx reverse proxy
- Optional Redis caching
```

### `docker-compose.dev.yml` (Development)
```yaml
# Development configuration
- Code volume mounting for hot reload
- Development environment variables
- Simplified setup for local development
```

## 🔧 Configuration Options

### Environment Variables

Set these in your docker-compose file or `.env` file:

```yaml
environment:
  - PYTHONUNBUFFERED=1
  - TRANSFORMERS_CACHE=/app/cache/transformers
  - HF_HOME=/app/cache/huggingface
  - ENVIRONMENT=production  # or development
```

### Volume Mounts

**Model Cache** (Recommended):
```yaml
volumes:
  - model_cache:/app/cache
```

**Local Images** (Optional):
```yaml
volumes:
  - ./images:/app/images:ro
```

**Development Code** (Dev only):
```yaml
volumes:
  - .:/app
```

## 🔍 Service Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │────│  FastAPI Service │────│  Model Cache    │
│   (Optional)    │    │  (Port 8000)     │    │  (Persistent)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
   Port 80/443             Docker Network              Volume Mount
```

## 🏥 Health Monitoring

### Built-in Health Checks

The container includes automatic health monitoring:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### Manual Health Check

```bash
# Check container health
docker ps

# Check API health
curl http://localhost:8000/health

# View service logs
docker-compose logs grounding-dino-api
```

## 📊 Performance Optimization

### GPU Support

To enable GPU acceleration, uncomment the PyTorch CUDA installation in the Dockerfile:

```dockerfile
# Install PyTorch with CUDA support
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

Add GPU support to docker-compose:

```yaml
services:
  grounding-dino-api:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Memory Optimization

Adjust memory limits based on your system:

```yaml
deploy:
  resources:
    limits:
      memory: 4G      # Maximum memory
    reservations:
      memory: 2G      # Reserved memory
```

### Model Caching

The service automatically caches downloaded models. Ensure the cache volume is persistent:

```yaml
volumes:
  model_cache:
    driver: local
```

## 🌐 Production Deployment

### With Nginx Reverse Proxy

1. **Start with production profile:**
   ```bash
   docker-compose --profile production up -d
   ```

2. **Configure SSL** (Optional):
   - Place SSL certificates in `./ssl/` directory
   - Update `nginx.conf` with your domain and SSL settings
   - Uncomment HTTPS server block

3. **Update Nginx configuration:**
   ```bash
   # Edit nginx.conf for your domain
   # Restart Nginx
   docker-compose restart nginx
   ```

### Load Balancing

For high-traffic deployments, scale the API service:

```bash
docker-compose up -d --scale grounding-dino-api=3
```

Update nginx.conf upstream block:
```nginx
upstream grounding_dino_backend {
    server grounding-dino-api:8000;
    server grounding-dino-api:8000;
    server grounding-dino-api:8000;
}
```

## 🛠️ Development Workflow

### Local Development

1. **Start development environment:**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **Code changes are automatically reloaded**

3. **View logs:**
   ```bash
   docker-compose -f docker-compose.dev.yml logs -f
   ```

### Building Custom Images

```bash
# Build only
docker-compose build

# Build with no cache
docker-compose build --no-cache

# Build specific service
docker-compose build grounding-dino-api
```

## 🔧 Troubleshooting

### Common Issues

**1. Model Download Failures:**
```bash
# Check internet connectivity
docker-compose exec grounding-dino-api curl -I https://huggingface.co

# Clear model cache
docker volume rm ai_thailand_2025_model_cache
```

**2. Memory Issues:**
```bash
# Check container memory usage
docker stats

# Increase memory limits in docker-compose.yml
```

**3. Port Conflicts:**
```bash
# Check what's using port 8000
netstat -tulnp | grep 8000

# Use different port
docker-compose up -d -p 8001:8000
```

**4. Permission Issues:**
```bash
# Fix file permissions
sudo chown -R $(whoami) ./
```

### Debugging Commands

```bash
# Access container shell
docker-compose exec grounding-dino-api bash

# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f grounding-dino-api

# Check service status
docker-compose ps

# Restart specific service
docker-compose restart grounding-dino-api
```

## 🧹 Cleanup

### Stop Services
```bash
docker-compose down
```

### Remove Everything (including volumes)
```bash
docker-compose down -v
docker system prune -a
```

### Remove Only Unused Resources
```bash
docker system prune
```

## 📋 Deployment Checklist

- [ ] Docker and Docker Compose installed
- [ ] Sufficient system resources (4GB+ RAM)
- [ ] Firewall allows port 8000 (and 80/443 for production)
- [ ] SSL certificates configured (production)
- [ ] Environment variables set
- [ ] Health checks passing
- [ ] API endpoints tested
- [ ] Monitoring configured
- [ ] Backup strategy for persistent volumes

## 🚀 Quick Deploy Commands

```bash
# Basic deployment
docker-compose up -d

# Development
docker-compose -f docker-compose.dev.yml up -d

# Production with Nginx
docker-compose --profile production up -d

# With caching
docker-compose --profile cache up -d

# Scale API service
docker-compose up -d --scale grounding-dino-api=3
```

## 📞 Support

If you encounter issues:

1. Check the logs: `docker-compose logs grounding-dino-api`
2. Verify health: `curl http://localhost:8000/health`
3. Check resources: `docker stats`
4. Review this documentation
5. Check Docker/Docker Compose versions
