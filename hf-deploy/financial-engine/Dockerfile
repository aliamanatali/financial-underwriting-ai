# Hugging Face Space — Financial Engine (self-contained).
# Runs redis-server (cache) + FastAPI API in one container. No Celery worker.
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
    REDIS_URL=redis://localhost:6379/0

WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# HF exposes this port (declared as app_port: 8001 in README.md).
EXPOSE 8001
CMD ["bash", "start.sh"]
