# Queue System Documentation - DynamicGroundingDINO API

## Overview

This document describes the production-ready queue system implementation for the DynamicGroundingDINO API service, designed to handle high-load scenarios for the "AI for Thais" website.

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───►│  Nginx LB    │───►│  FastAPI    │───►│   Redis     │
│   Request   │    │ (Rate Limit) │    │   Server    │    │  (Broker)   │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
                                              │                    │
                                              ▼                    ▼
                                       ┌─────────────┐    ┌─────────────┐
                                       │   Queue     │    │   Celery    │
                                       │  Manager    │    │  Workers    │
                                       └─────────────┘    └─────────────┘
                                              │                    │
                                              ▼                    ▼
                                       ┌─────────────┐    ┌─────────────┐
                                       │   Flower    │    │ AI Model    │
                                       │ Monitoring  │    │ Processing  │
                                       └─────────────┘    └─────────────┘
```

## Components

### 1. FastAPI Server (`server.py`)
- **Async Endpoints**: `/detect/async`, `/upload/async`
- **Queue Management**: Task status, cancellation, queue statistics
- **Health Checks**: Service and queue health monitoring
- **Rate Limiting**: Built-in request throttling

### 2. Celery Workers (`queue_worker.py`)
- **Task Processing**: Asynchronous object detection
- **Auto-scaling**: Dynamic worker scaling based on load
- **Error Handling**: Robust error recovery and logging
- **Priority Queue**: Task prioritization (1-10 scale)

### 3. Redis
- **Message Broker**: Task queue management
- **Result Backend**: Task status and result storage
- **Caching**: Model and result caching

### 4. Monitoring
- **Flower**: Celery task monitoring UI
- **Health Endpoints**: Service status monitoring
- **Metrics**: Queue length, worker status, task statistics

## Deployment Options

### Quick Start
```bash
# Basic API + Redis only
./deploy-queue.sh --basic

# With queue workers
./deploy-queue.sh --with-workers

# Full production setup
./deploy-queue.sh --production

# With monitoring services
./deploy-queue.sh --monitoring
```

### Windows Deployment
```cmd
REM Basic setup
deploy-queue.bat --basic

REM Production setup
deploy-queue.bat --production
```

## API Endpoints

### Queue Operations

#### Submit Async Detection
```http
POST /detect/async
Content-Type: application/json

{
    "image_url": "http://example.com/image.jpg",
    "text_queries": ["cat", "dog", "person"],
    "priority": 5,
    "confidence_threshold": 0.3,
    "box_threshold": 0.25
}
```

**Response:**
```json
{
    "task_id": "abc123-def456-ghi789",
    "status": "pending",
    "estimated_time": 30,
    "queue_position": 5
}
```

#### Check Task Status
```http
GET /task/{task_id}
```

**Response:**
```json
{
    "task_id": "abc123-def456-ghi789",
    "status": "success",
    "progress": 100,
    "result": {
        "detections": [...],
        "object_count": 3,
        "processing_time": 2.5
    },
    "created_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:00:03Z"
}
```

#### Cancel Task
```http
DELETE /task/{task_id}
```

#### Upload Async Processing
```http
POST /upload/async
Content-Type: multipart/form-data

file: [image file]
text_queries: ["cat", "dog"]
priority: 7
```

### Queue Management

#### Queue Status
```http
GET /queue/status
```

**Response:**
```json
{
    "active_tasks": 5,
    "pending_tasks": 12,
    "failed_tasks": 1,
    "completed_tasks": 1234,
    "workers": {
        "online": 3,
        "busy": 2,
        "idle": 1
    },
    "queue_length": 17,
    "average_processing_time": 2.3
}
```

#### Clear Failed Tasks
```http
POST /queue/clear-failed
```

#### Worker Statistics
```http
GET /queue/workers
```

## Task Priorities

Tasks are processed based on priority (1-10 scale):

- **Priority 1-3**: Low priority (batch processing)
- **Priority 4-6**: Normal priority (default: 5)
- **Priority 7-8**: High priority (user-facing requests)
- **Priority 9-10**: Critical priority (emergency processing)

## Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json

# Worker Configuration
CELERY_WORKER_CONCURRENCY=2
CELERY_MAX_TASKS_PER_CHILD=100
CELERY_TASK_TIME_LIMIT=300
CELERY_TASK_SOFT_TIME_LIMIT=240

# Queue Configuration
QUEUE_DEFAULT_PRIORITY=5
QUEUE_MAX_RETRIES=3
QUEUE_RETRY_DELAY=60

# Model Configuration
MODEL_CACHE_SIZE=1
MODEL_CACHE_TTL=3600
```

### Docker Compose Profiles

```yaml
# Basic setup (API + Redis)
docker-compose up -d

# With workers
docker-compose --profile workers up -d

# With monitoring
docker-compose --profile workers --profile monitoring up -d

# Production setup
docker-compose -f docker-compose.prod.yml up -d
```

## Scaling

### Horizontal Scaling

```bash
# Scale workers during runtime
docker-compose -f docker-compose.prod.yml up -d --scale worker=5

# Scale API instances
docker-compose -f docker-compose.prod.yml up -d --scale api=3
```

### Auto-scaling Configuration

The system supports auto-scaling based on:
- Queue length
- Worker utilization
- Response time metrics
- Memory usage

### Load Balancing

Nginx handles load balancing with:
- Round-robin distribution
- Health check routing
- Rate limiting (100 req/min per IP)
- Connection pooling

## Monitoring

### Web Interfaces

- **API Documentation**: `http://localhost:8000/docs`
- **Flower Dashboard**: `http://localhost:5555`
- **Queue Status**: `http://localhost:8000/queue/status`
- **Health Check**: `http://localhost:8000/health`

### Metrics Collection

```bash
# Check service status
./deploy-queue.sh --status

# View logs
./deploy-queue.sh --logs

# Real-time monitoring
curl http://localhost:8000/queue/status | jq .
```

### Alerting

Set up monitoring alerts for:
- Queue length > 100 tasks
- Worker failure rate > 5%
- Average response time > 10s
- Memory usage > 80%

## Performance Tuning

### Worker Optimization

```python
# Celery worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # For memory-intensive tasks
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100  # Prevent memory leaks
CELERY_TASK_ACKS_LATE = True  # Ensure task completion
```

### Redis Optimization

```redis
# Redis configuration for high performance
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Model Optimization

- **Model Caching**: Keep model in memory across tasks
- **Batch Processing**: Process multiple images together
- **GPU Utilization**: Optimize CUDA memory usage
- **Result Caching**: Cache frequent detection results

## Error Handling

### Task Retry Logic

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def detect_objects_task(self, image_data, text_queries, **kwargs):
    try:
        # Process task
        return result
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        raise exc
```

### Error Categories

1. **Transient Errors**: Network timeouts, temporary resource unavailability
2. **Permanent Errors**: Invalid input, model errors
3. **System Errors**: Out of memory, disk space issues

### Recovery Strategies

- **Exponential Backoff**: Increasing delay between retries
- **Circuit Breaker**: Temporary service isolation
- **Dead Letter Queue**: Failed task analysis
- **Health Checks**: Automatic service recovery

## Security

### Rate Limiting

```nginx
# Nginx rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
limit_req zone=api burst=20 nodelay;
```

### Input Validation

- Image format validation
- File size limits (10MB max)
- Text query sanitization
- Parameter bounds checking

### Network Security

- Internal service communication
- Redis password protection
- HTTPS termination
- CORS configuration

## Troubleshooting

### Common Issues

1. **Queue Stuck**
   ```bash
   # Clear failed tasks
   curl -X POST http://localhost:8000/queue/clear-failed
   
   # Restart workers
   ./deploy-queue.sh --restart
   ```

2. **High Memory Usage**
   ```bash
   # Check worker memory
   docker stats grounding-dino-worker-1
   
   # Reduce worker concurrency
   export CELERY_WORKER_CONCURRENCY=1
   ```

3. **Slow Processing**
   ```bash
   # Check queue status
   curl http://localhost:8000/queue/status
   
   # Scale workers
   docker-compose up -d --scale worker=3
   ```

### Debug Commands

```bash
# Check Redis connection
docker exec grounding-dino-redis redis-cli ping

# Monitor worker logs
docker logs -f grounding-dino-worker-1

# Test API endpoints
curl -X POST http://localhost:8000/detect/async \
     -H "Content-Type: application/json" \
     -d '{"image_url":"http://example.com/test.jpg","text_queries":["test"]}'

# Check task in Redis
docker exec grounding-dino-redis redis-cli keys "*task*"
```

## Best Practices

### Development

1. **Test Locally**: Use `--basic` mode for development
2. **Monitor Resources**: Watch memory and CPU usage
3. **Error Logging**: Enable detailed error logging
4. **Version Control**: Tag deployment versions

### Production

1. **Health Monitoring**: Set up automated health checks
2. **Backup Strategy**: Regular Redis data backups
3. **Resource Limits**: Set appropriate Docker resource limits
4. **Load Testing**: Test with expected traffic patterns

### Maintenance

1. **Regular Updates**: Keep dependencies updated
2. **Log Rotation**: Implement log rotation policies
3. **Performance Review**: Regular performance analysis
4. **Capacity Planning**: Monitor and plan for growth

## Support

For issues and questions:

1. Check service logs: `./deploy-queue.sh --logs`
2. Verify service status: `./deploy-queue.sh --status`
3. Review queue metrics: `curl http://localhost:8000/queue/status`
4. Monitor Flower dashboard: `http://localhost:5555`

## License

This queue system implementation is part of the DynamicGroundingDINO API service for the AI for Thais project.
