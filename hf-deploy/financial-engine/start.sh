#!/usr/bin/env bash
# Boots Redis (ephemeral cache), then the API in the foreground.
set -e

redis-server --daemonize yes --dir /tmp --save "" --appendonly no

for i in $(seq 1 20); do
  redis-cli ping >/dev/null 2>&1 && break
  sleep 0.5
done

exec uvicorn app.main:app --host 0.0.0.0 --port 8001
