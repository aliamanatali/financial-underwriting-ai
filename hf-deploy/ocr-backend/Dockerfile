# Hugging Face Space — OCR backend (self-contained).
# Runs redis-server + Celery worker + FastAPI API in one container.
# HF runs the container as UID 1000, so we create `user` per HF requirements.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends redis-server curl \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces run as user 1000.
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REDIS_URL=redis://localhost:6379/0 \
    CELERY_BROKER_URL=redis://localhost:6379/0 \
    CELERY_RESULT_BACKEND=redis://localhost:6379/0 \
    CELERY_WORKER_CONCURRENCY=2

WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# HF exposes this port (declared as app_port: 8000 in README.md).
EXPOSE 8000
CMD ["bash", "start.sh"]
