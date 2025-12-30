# Celery Setup Guide for OCR Backend

This guide explains how to set up and use Celery for asynchronous document processing in the OCR Backend.

## Overview

The OCR Backend uses **Celery** with **Redis** as a message broker to handle document processing asynchronously. This allows:

- ✅ **Immediate API responses** - Upload returns instantly with a task ID
- ✅ **Background processing** - Documents are processed by Celery workers
- ✅ **Parallel chunk processing** - Large PDFs are split and processed in parallel
- ✅ **Real-time progress tracking** - Monitor processing status via Redis
- ✅ **Automatic retries** - Failed tasks are retried automatically
- ✅ **Scalability** - Run multiple workers for better performance

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │─────▶│  FastAPI API │─────▶│    Redis    │
│  (Upload)   │      │   (Queue)    │      │  (Broker)   │
└─────────────┘      └──────────────┘      └─────────────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │   Celery    │
                                            │   Worker    │
                                            └─────────────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │  Process    │
                                            │  Document   │
                                            └─────────────┘
```

## Prerequisites

### 1. Install Redis

**macOS (using Homebrew):**

```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Verify Redis is running:**

```bash
redis-cli ping
# Should return: PONG
```

### 2. Install Python Dependencies

```bash
cd ocr-backend
source venv/bin/activate
pip install -r requirements.txt
```

This installs:

- `celery[redis]>=5.3.0` - Celery with Redis support
- `redis>=5.0.0` - Redis Python client

## Configuration

### Environment Variables

Update your `.env` file with Redis and Celery configuration:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=16
CELERY_TASK_TIME_LIMIT=3600
CELERY_TASK_SOFT_TIME_LIMIT=3300
CELERY_WORKER_PREFETCH_MULTIPLIER=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
```

### Configuration Options

| Variable                            | Description                  | Default                    |
| ----------------------------------- | ---------------------------- | -------------------------- |
| `REDIS_URL`                         | Redis connection URL         | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL`                 | Celery message broker URL    | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND`             | Where to store task results  | `redis://localhost:6379/0` |
| `CELERY_WORKER_CONCURRENCY`         | Number of worker processes   | `16`                       |
| `CELERY_TASK_TIME_LIMIT`            | Hard time limit (seconds)    | `3600` (1 hour)            |
| `CELERY_TASK_SOFT_TIME_LIMIT`       | Soft time limit (seconds)    | `3300` (55 min)            |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | Tasks to prefetch per worker | `4`                        |
| `CELERY_WORKER_MAX_TASKS_PER_CHILD` | Tasks before worker restart  | `1000`                     |

## Running the System

### 1. Start Redis (if not running)

```bash
redis-server
```

### 2. Start the FastAPI Server

```bash
cd ocr-backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 3. Start the Celery Worker

**Using the startup script (recommended):**

```bash
cd ocr-backend
./start_worker.sh
```

**Manual start:**

```bash
cd ocr-backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info --concurrency=16
```

### 4. Monitor Tasks (Optional)

**Flower - Web-based monitoring:**

```bash
pip install flower
celery -A app.celery_app flower
# Open http://localhost:5555
```

**Command-line monitoring:**

```bash
celery -A app.celery_app events
```

## Task Queues

The system uses three queues for task organization:

1. **`document_processing`** - Main document processing tasks
2. **`chunk_processing`** - Individual chunk processing (parallel)
3. **`default`** - General tasks

## Workflow

### Document Upload and Processing

1. **Client uploads PDF** → `POST /api/documents/upload`
2. **API saves file** and creates document record
3. **API queues Celery task** and returns immediately with `task_id`
4. **Celery worker picks up task** from Redis queue
5. **Worker processes document:**
   - Small files: Direct processing
   - Large files: Split into chunks → Process in parallel → Aggregate results
6. **Worker updates document status** in database
7. **Client polls for status** → `GET /api/documents/{id}/status`
8. **Client retrieves results** → `GET /api/documents/{id}`

### Parallel Chunk Processing

For large documents (>1 page or >5MB):

```python
# 1. Split PDF into chunks
chunks = split_pdf(file_data)  # e.g., 10 chunks

# 2. Create parallel tasks using Celery group
chunk_tasks = [
    process_chunk_task.s(doc_id, idx, chunk_data, ...)
    for idx, chunk_data in enumerate(chunks)
]

# 3. Process in parallel and aggregate
chord(chunk_tasks)(aggregate_chunks_task.s(doc_id, pdf_info))
```

## API Endpoints

### Upload Document

```http
POST /api/documents/upload
Content-Type: multipart/form-data

Response:
{
  "document_id": "abc123",
  "filename": "document.pdf",
  "status": "queued",
  "task_id": "celery-task-id-xyz",
  "message": "Document uploaded successfully. Processing queued in background."
}
```

### Check Status

```http
GET /api/documents/{document_id}/status

Response:
{
  "document_id": "abc123",
  "status": "processing_chunks",
  "progress_percentage": 45.5,
  "task": {
    "task_id": "celery-task-id-xyz",
    "state": "STARTED",
    "info": {...}
  },
  "error_message": null,
  "updated_at": "2025-12-24T09:30:00Z"
}
```

### Get Progress Details

```http
GET /api/documents/{document_id}/progress

Response:
{
  "document_id": "abc123",
  "status": "processing_chunks",
  "progress_percentage": 45.5,
  "metadata": {...},
  "real_time_progress": {
    "total_chunks": 10,
    "completed_chunks": 4,
    "failed_chunks": 1,
    "processing_chunks": 2,
    "overall_progress": 45.5
  },
  "chunk_details": {
    "1": {"status": "completed", "error": null},
    "2": {"status": "completed", "error": null},
    "3": {"status": "failed", "error": "Timeout"},
    "4": {"status": "processing", "error": null}
  }
}
```

## Task States

| State        | Description                   |
| ------------ | ----------------------------- |
| `PENDING`    | Task queued, waiting to start |
| `STARTED`    | Task picked up by worker      |
| `PROCESSING` | Task is actively processing   |
| `SUCCESS`    | Task completed successfully   |
| `FAILURE`    | Task failed with error        |
| `RETRY`      | Task is being retried         |

## Document Processing States

| Status              | Description                          |
| ------------------- | ------------------------------------ |
| `pending`           | Document created, not yet queued     |
| `queued`            | Task queued in Celery                |
| `extracting`        | Extracting text from document        |
| `processing_chunks` | Processing chunks in parallel        |
| `completed`         | Processing finished successfully     |
| `partial_error`     | Some chunks failed, others succeeded |
| `error`             | Processing failed completely         |
| `cancelled`         | Task was cancelled                   |

## Monitoring and Debugging

### Check Worker Status

```bash
celery -A app.celery_app inspect active
celery -A app.celery_app inspect stats
```

### View Task Results

```bash
celery -A app.celery_app result <task-id>
```

### Purge All Tasks

```bash
celery -A app.celery_app purge
```

### Check Redis Keys

```bash
redis-cli
> KEYS celery*
> GET celery-task-meta-<task-id>
```

## Performance Tuning

### Adjust Worker Concurrency

**Default Configuration (Recommended for I/O-bound tasks):**

The default concurrency is set to **16 workers**, which is optimal for I/O-bound tasks like Gemini API calls:

```bash
# Default: 16 workers (optimal for I/O-bound Gemini API processing)
celery -A app.celery_app worker --concurrency=16
```

**Why 16 Workers?**

- Document processing is **I/O-bound** (waiting for Gemini API responses)
- Each chunk takes ~5-10 seconds to process
- For I/O-bound tasks, concurrency can be 2-3x CPU cores
- 16 workers allows processing 16 chunks simultaneously
- Provides 4x faster processing than the previous 4 workers
- Optimal balance between throughput and system resources

**Adjusting Based on System:**

For systems with fewer CPU cores (4-6 cores):

```bash
# Conservative: 8 workers
celery -A app.celery_app worker --concurrency=8
```

For high-performance systems (12+ cores):

```bash
# Aggressive: 24 workers for maximum throughput
celery -A app.celery_app worker --concurrency=24
```

For CPU-intensive tasks (if you add non-API processing):

```bash
# Set concurrency to number of CPU cores
celery -A app.celery_app worker --concurrency=8
```

**Resource Considerations:**

- Each worker uses ~100-200MB RAM
- 16 workers = ~1.6-3.2GB RAM (acceptable for most systems)
- Monitor Gemini API rate limits if using high concurrency
- Adjust based on actual performance and system resources

### Multiple Workers

Run multiple workers for better scalability:

```bash
# Terminal 1
celery -A app.celery_app worker -n worker1@%h --concurrency=16

# Terminal 2
celery -A app.celery_app worker -n worker2@%h --concurrency=16
```

### Queue Prioritization

Process specific queues with dedicated workers:

```bash
# Worker for document processing only
celery -A app.celery_app worker -Q document_processing --concurrency=2

# Worker for chunk processing only
celery -A app.celery_app worker -Q chunk_processing --concurrency=8
```

## Troubleshooting

### Redis Connection Error

```
Error: Redis is not running or not accessible
```

**Solution:** Start Redis with `redis-server` or `brew services start redis`

### Task Timeout

```
SoftTimeLimitExceeded: Task exceeded soft time limit
```

**Solution:** Increase `CELERY_TASK_SOFT_TIME_LIMIT` in `.env`

### Worker Not Processing Tasks

```bash
# Check if worker is running
ps aux | grep celery

# Check Redis connection
redis-cli ping

# Restart worker
pkill -f "celery worker"
./start_worker.sh
```

### Memory Issues

```
Worker consuming too much memory
```

**Solution:** Reduce `CELERY_WORKER_MAX_TASKS_PER_CHILD` to restart workers more frequently

## Production Deployment

### Using Supervisor (Linux)

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=16
directory=/path/to/ocr-backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log
```

Start with:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery-worker
```

### Using systemd (Linux)

Create `/etc/systemd/system/celery.service`:

```ini
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/ocr-backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=16 --detach
ExecStop=/path/to/venv/bin/celery -A app.celery_app control shutdown
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable celery
sudo systemctl start celery
sudo systemctl status celery
```

### Docker Deployment

See `docker-compose.yml` for containerized deployment with Redis and Celery workers.

## Best Practices

1. **Always run Redis** before starting workers
2. **Monitor worker health** using Flower or logs
3. **Set appropriate timeouts** based on document sizes
4. **Use multiple workers** for better throughput
5. **Implement retry logic** for transient failures
6. **Monitor Redis memory** usage
7. **Log task failures** for debugging
8. **Use task routing** for different document types
9. **Implement rate limiting** to prevent overload
10. **Regular worker restarts** to prevent memory leaks

## Additional Resources

- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [Flower Monitoring](https://flower.readthedocs.io/)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)

## Support

For issues or questions:

1. Check logs: `tail -f /var/log/celery/worker.log`
2. Monitor Redis: `redis-cli monitor`
3. Check worker status: `celery -A app.celery_app inspect active`
4. Review task results: `celery -A app.celery_app result <task-id>`
