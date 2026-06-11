#!/usr/bin/env bash
# Boots Redis (ephemeral, in-memory), the Celery worker, then the API in the foreground.
set -e

# In-container Redis — broker + progress cache. No disk persistence (HF disk is ephemeral).
redis-server --daemonize yes --dir /tmp --save "" --appendonly no

# Wait for Redis to accept connections before starting Celery.
for i in $(seq 1 20); do
  redis-cli ping >/dev/null 2>&1 && break
  sleep 0.5
done

# Celery worker in the background.
celery -A app.celery_app worker \
  --loglevel=info \
  -Q document_processing,chunk_processing,default \
  --concurrency="${CELERY_WORKER_CONCURRENCY:-2}" \
  --max-tasks-per-child=200 \
  --time-limit=3600 --soft-time-limit=3300 \
  -n worker@hf &

# FastAPI API in the foreground on the HF-exposed port.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
