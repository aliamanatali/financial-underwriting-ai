"""Celery application configuration for async task processing."""

from celery import Celery
from kombu import Queue, Exchange

from app.config import settings
from app.utils.logger import logger


# Initialize Celery app
celery_app = Celery(
    "ocr_backend",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.document_tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_track_started=True,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Worker settings
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,
    worker_disable_rate_limits=False,
    
    # Queue settings
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("document_processing", Exchange("document_processing"), routing_key="document.#"),
        Queue("chunk_processing", Exchange("chunk_processing"), routing_key="chunk.#"),
    ),
    
    # Route tasks to specific queues
    task_routes={
        "app.tasks.document_tasks.process_document_task": {
            "queue": "document_processing",
            "routing_key": "document.process"
        },
        "app.tasks.document_tasks.process_chunk_task": {
            "queue": "chunk_processing",
            "routing_key": "chunk.process"
        },
    },
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery setup."""
    logger.info(f"Request: {self.request!r}")
    return {"status": "ok", "task_id": self.request.id}


# Event handlers
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks if needed."""
    # Example: Clean up old results every hour
    # sender.add_periodic_task(3600.0, cleanup_old_results.s(), name='cleanup-hourly')
    pass


logger.info("Celery app initialized successfully")
