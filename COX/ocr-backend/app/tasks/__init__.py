"""Celery tasks package."""

from app.tasks.document_tasks import process_document_task, process_chunk_task

__all__ = ["process_document_task", "process_chunk_task"]
