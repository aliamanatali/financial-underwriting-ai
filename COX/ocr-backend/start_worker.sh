#!/bin/bash

# Celery Worker Startup Script
# This script starts a Celery worker for processing document tasks

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Error: Virtual environment not found at venv/"
    exit 1
fi

# Check if Redis is running
echo "Checking Redis connection..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Warning: Redis is not running or not accessible"
    echo "Please start Redis with: redis-server"
    echo "Or install Redis with: brew install redis (macOS) or apt-get install redis (Linux)"
    exit 1
fi

# Purge existing Celery tasks
echo "Purging existing Celery tasks..."
"$SCRIPT_DIR/venv/bin/celery" -A app.celery_app purge -f
echo ""

echo "Starting Celery worker..."
echo "Worker concurrency: ${CELERY_WORKER_CONCURRENCY:-16}"
echo "Log level: ${CELERY_LOG_LEVEL:-info}"
echo ""

# Start Celery worker
# -A: Application module
# worker: Start worker mode
# --loglevel: Logging level
# --concurrency: Number of worker processes (16 for balanced performance + reliability)
#               Reduced from 10 to work with semaphore (4 concurrent API requests)
# -Q: Queues to consume from
# -n: Worker name
"$SCRIPT_DIR/venv/bin/celery" -A app.celery_app worker \
    --loglevel="${CELERY_LOG_LEVEL:-info}" \
    --concurrency="${CELERY_WORKER_CONCURRENCY:-16}" \
    -Q document_processing,chunk_processing,default \
    -n worker@%h \
    --max-tasks-per-child=1000 \
    --time-limit=3600 \
    --soft-time-limit=3300

# Note: Press Ctrl+C to stop the worker gracefully
