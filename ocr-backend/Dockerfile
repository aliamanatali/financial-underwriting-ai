# OCR Backend — FastAPI API + Celery worker share this one image.
# Fly runs the API or the worker by overriding the command via [processes] in fly.toml.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl is used by the container healthcheck; build tools kept minimal (deps ship wheels).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Default command (the API). The Celery worker process overrides this in fly.toml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
