"""Document upload and extraction endpoints."""

from typing import Dict, Any, AsyncGenerator
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from celery.result import AsyncResult
import asyncio
import json

from app.models.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentTextResponse,
    DocumentListResponse
)
from app.services.document_service import DocumentService
from app.celery_app import celery_app
from app.tasks.redis_progress import RedisProgressTracker
from app.utils.logger import logger
from app.config import settings

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# Global document service instance
document_service = DocumentService()
progress_tracker = RedisProgressTracker()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...)
):
    """
    Upload a PDF document and queue for background processing with Celery.
    
    The document is uploaded and a Celery task is queued immediately.
    Use the returned task_id to check status and retrieve results.
    
    Args:
        file: PDF file to upload (multipart/form-data)
        
    Returns:
        DocumentUploadResponse with document_id, task_id, and status
    """
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    try:
        # Read file content
        file_data = await file.read()
        
        if len(file_data) == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )
        
        # Upload document and queue Celery task
        response = await document_service.upload_document(
            file_data=file_data,
            filename=file.filename or "document.pdf"
        )
        
        logger.info(f"Document uploaded and queued: {response.document_id}, task_id: {response.task_id}")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to upload document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("", response_model=DocumentListResponse)
async def list_documents():
    """
    Get a list of all documents.
    
    Returns:
        DocumentListResponse with list of all documents
    """
    try:
        documents = await document_service.list_documents()
        
        return DocumentListResponse(
            documents=documents,
            total=len(documents)
        )
        
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get document details including extraction results.
    
    Args:
        document_id: Unique document identifier
        
    Returns:
        DocumentResponse with complete document information
    """
    try:
        document = await document_service.get_document(document_id)
        return document
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document: {str(e)}"
        )


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
async def get_document_text(document_id: str):
    """
    Get extracted text for a document.
    
    Args:
        document_id: Unique document identifier
        
    Returns:
        DocumentTextResponse with extracted text
    """
    try:
        document = await document_service.get_document(document_id)
        
        if not document.extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Document has not been processed yet"
            )
        
        return DocumentTextResponse(
            document_id=document.document_id,
            text=document.extracted_text,
            page_count=document.metadata.page_count if document.metadata else 0,
            confidence=document.metadata.quality if document.metadata else "medium"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document text: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document text: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and its associated file.
    
    Args:
        document_id: Unique document identifier
        
    Returns:
        Success message
    """
    try:
        success = await document_service.delete_document(document_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete document"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Document {document_id} deleted successfully"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get("/{document_id}/status")
async def get_document_status(document_id: str) -> Dict[str, Any]:
    """
    Get processing status for a document including Celery task status.
    
    Args:
        document_id: Unique document identifier
        
    Returns:
        Status information including task state and progress
    """
    try:
        document = await document_service.get_document(document_id)
        
        # Get Celery task status if task_id exists
        task_info = None
        if document.task_id:
            task_result = AsyncResult(document.task_id, app=celery_app)
            task_info = {
                "task_id": document.task_id,
                "state": task_result.state,
                "info": task_result.info if task_result.info else {}
            }
        
        return {
            "document_id": document.document_id,
            "status": document.status.value,
            "progress_percentage": document.progress_percentage,
            "task": task_info,
            "error_message": document.error_message,
            "updated_at": document.updated_at.isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get document status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document status: {str(e)}"
        )


@router.get("/{document_id}/progress")
async def get_document_progress(document_id: str) -> Dict[str, Any]:
    """
    Get detailed progress information for document processing.
    
    This includes chunk-level progress for large documents.
    
    Args:
        document_id: Unique document identifier
        
    Returns:
        Detailed progress information
    """
    try:
        document = await document_service.get_document(document_id)
        
        # Get Redis progress data
        redis_progress = progress_tracker.get_progress(document_id)
        
        # Get chunk details if available
        chunk_details = None
        if redis_progress:
            chunk_details = progress_tracker.get_chunk_details(document_id)
        
        # Build response
        response = {
            "document_id": document.document_id,
            "status": document.status.value,
            "progress_percentage": document.progress_percentage,
            "metadata": document.metadata.model_dump() if document.metadata else None
        }
        
        if redis_progress:
            response["real_time_progress"] = {
                "total_chunks": redis_progress.get("total_chunks", 0),
                "completed_chunks": redis_progress.get("completed_chunks", 0),
                "failed_chunks": redis_progress.get("failed_chunks", 0),
                "processing_chunks": redis_progress.get("processing_chunks", 0),
                "overall_progress": redis_progress.get("overall_progress", 0.0)
            }
        
        if chunk_details:
            response["chunk_details"] = chunk_details
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get document progress: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document progress: {str(e)}"
        )


@router.get("/{document_id}/progress/stream")
async def stream_document_progress(document_id: str):
    """
    Stream real-time progress updates using Server-Sent Events (SSE).
    
    This endpoint establishes a persistent connection and streams progress updates
    as they occur via Redis pub/sub. The connection automatically closes when
    processing completes or fails.
    
    Args:
        document_id: Unique document identifier
        
    Returns:
        StreamingResponse with text/event-stream content type
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from Redis pub/sub."""
        import redis.asyncio as aioredis
        
        redis_client = None
        pubsub = None
        
        try:
            # Verify document exists
            try:
                await document_service.get_document(document_id)
            except ValueError:
                yield f"event: error\ndata: {json.dumps({'error': 'Document not found'})}\n\n"
                return
            
            # Connect to Redis using settings
            redis_client = await aioredis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            
            # Subscribe to progress channel
            channel = progress_tracker._get_channel(document_id)
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            logger.info(f"SSE client connected for document {document_id}")
            
            # Send initial progress state
            initial_progress = progress_tracker.get_progress(document_id)
            if initial_progress:
                yield f"event: progress\ndata: {json.dumps(initial_progress)}\n\n"
            
            # Listen for updates
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        event_type = data.get('event', 'progress')
                        
                        # Send SSE event
                        yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                        
                        # Close connection if completed or failed
                        if event_type in ['completed', 'error']:
                            logger.info(f"SSE stream closing for document {document_id}: {event_type}")
                            break
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode message: {str(e)}")
                        continue
                
                # Add small delay to prevent overwhelming the client
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in SSE stream for document {document_id}: {str(e)}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            
        finally:
            # Cleanup
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            if redis_client:
                await redis_client.close()
            logger.info(f"SSE client disconnected for document {document_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",  # Allow CORS for SSE
        }
    )


@router.post("/{document_id}/reprocess")
async def reprocess_document(document_id: str):
    """
    Reprocess a document (re-extract text) using Celery.
    
    Args:
        document_id: Unique document identifier
        
    Returns:
        Success message with new task_id
    """
    try:
        # Verify document exists and get storage path
        document = await document_service.get_document(document_id)
        
        # Queue new Celery task
        from app.tasks.document_tasks import process_document_task
        task = process_document_task.delay(document_id, document.storage_path)
        
        # Update document with new task_id
        await document_service._update_document(document_id, {
            "task_id": task.id,
            "status": "queued",
            "task_status": "PENDING"
        })
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Document {document_id} reprocessing queued",
                "task_id": task.id
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reprocess document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reprocess document: {str(e)}"
        )
