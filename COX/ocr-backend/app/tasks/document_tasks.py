"""Celery tasks for document processing with parallel chunk processing."""

from datetime import datetime
from typing import Dict, Any, List, Tuple
import asyncio
import time

from celery import group, chord
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.config import settings
from app.models.document import (
    ProcessingStatus,
    ConfidenceLevel,
    DocumentMetadata,
    ChunkProgress
)
from app.services.gemini_service import GeminiService
from app.services.storage_service import StorageService
from app.services.pdf_chunking_service import PDFChunkingService
from app.utils.logger import logger
from app.tasks.redis_progress import RedisProgressTracker


# Initialize services (these will be created per worker)
def get_services():
    """Get service instances for the current worker."""
    return {
        'storage': StorageService(),
        'gemini': GeminiService(),
        'chunking': PDFChunkingService(chunk_size_pages=settings.chunk_size_pages),
        'progress': RedisProgressTracker()
    }


@celery_app.task(
    bind=True,
    name="app.tasks.document_tasks.process_document_task",
    max_retries=3,
    default_retry_delay=60
)
def process_document_task(self, document_id: str, storage_path: str) -> Dict[str, Any]:
    """
    Main document processing task with parallel chunk processing.
    
    Args:
        document_id: Unique document identifier
        storage_path: Path to the stored document
        
    Returns:
        Dictionary with processing results
    """
    # Track start time
    start_time = time.time()
    
    try:
        logger.info(f"Starting document processing task for {document_id}")
        
        # Get services
        services = get_services()
        storage_service = services['storage']
        chunking_service = services['chunking']
        progress_tracker = services['progress']
        
        # Store start time in Redis for later retrieval
        progress_tracker.set_start_time(document_id, start_time)
        
        # Update task status
        self.update_state(
            state='STARTED',
            meta={'status': 'Retrieving document', 'progress': 0}
        )
        
        # Update document status in database
        asyncio.run(_update_document_status(
            document_id,
            ProcessingStatus.EXTRACTING,
            task_id=self.request.id
        ))
        
        # Retrieve file from storage
        file_data = asyncio.run(storage_service.get_file(storage_path))
        
        # Get PDF info
        pdf_info = asyncio.run(chunking_service.get_pdf_info(file_data))
        
        # Determine if chunking is needed
        should_chunk = chunking_service.should_use_chunking(
            page_count=pdf_info["page_count"],
            file_size_mb=pdf_info["file_size_mb"],
            page_threshold=settings.large_file_page_threshold,
            size_threshold_mb=settings.large_file_threshold_mb
        )
        
        if should_chunk:
            logger.info(
                f"Processing large document {document_id} with parallel chunking "
                f"({pdf_info['page_count']} pages, {pdf_info['file_size_mb']} MB)"
            )
            result = _process_with_parallel_chunks(
                self,
                document_id,
                file_data,
                pdf_info,
                chunking_service,
                progress_tracker
            )
        else:
            logger.info(
                f"Processing small document {document_id} without chunking "
                f"({pdf_info['page_count']} pages, {pdf_info['file_size_mb']} MB)"
            )
            result = _process_without_chunks(
                self,
                document_id,
                file_data,
                pdf_info
            )
        
        logger.info(f"Document processing completed for {document_id}")
        return result
        
    except SoftTimeLimitExceeded:
        logger.error(f"Task soft time limit exceeded for document {document_id}")
        asyncio.run(_update_document_status(
            document_id,
            ProcessingStatus.ERROR,
            error_message="Processing timeout - document too large or complex"
        ))
        raise
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        
        # Update document status to error
        asyncio.run(_update_document_status(
            document_id,
            ProcessingStatus.ERROR,
            error_message=str(e)
        ))
        
        # Publish failure event
        services = get_services()
        services['progress'].mark_failed(document_id, str(e))
        
        # Retry on failure
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    name="app.tasks.document_tasks.process_chunk_task",
    max_retries=2,
    default_retry_delay=30
)
def process_chunk_task(
    self,
    document_id: str,
    chunk_index: int,
    chunk_data: bytes,
    start_page: int,
    end_page: int,
    total_chunks: int
) -> Dict[str, Any]:
    """
    Process a single PDF chunk.
    
    Args:
        document_id: Document identifier
        chunk_index: Index of this chunk (1-based)
        chunk_data: PDF chunk bytes
        start_page: Starting page number
        end_page: Ending page number
        total_chunks: Total number of chunks
        
    Returns:
        Dictionary with chunk processing results
    """
    try:
        chunk_info = f"chunk {chunk_index} of {total_chunks}"
        logger.info(
            f"[CHUNK-START] Processing {chunk_info} for document {document_id} "
            f"(pages {start_page}-{end_page})"
        )
        
        # Get services
        services = get_services()
        gemini_service = services['gemini']
        progress_tracker = services['progress']
        
        # Update progress to "processing"
        logger.info(f"[CHUNK-{chunk_index}] Updating status to 'processing' for document {document_id}")
        progress_tracker.update_chunk_progress(
            document_id,
            chunk_index,
            "processing"
        )
        logger.info(f"[CHUNK-{chunk_index}] Status update to 'processing' completed")
        
        # Extract text from chunk
        chunk_result = asyncio.run(gemini_service.extract_pdf_chunk(
            pdf_chunk=chunk_data,
            chunk_info=chunk_info,
            start_page=start_page,
            end_page=end_page
        ))
        
        # Update progress to "completed"
        logger.info(f"[CHUNK-{chunk_index}] Updating status to 'completed' for document {document_id}")
        progress_tracker.update_chunk_progress(
            document_id,
            chunk_index,
            "completed"
        )
        logger.info(f"[CHUNK-{chunk_index}] Status update to 'completed' completed")
        
        logger.info(f"[CHUNK-END] Successfully processed {chunk_info} for document {document_id}")
        
        return {
            'chunk_index': chunk_index,
            'text': chunk_result.text,
            'confidence': chunk_result.confidence.value,
            'has_handwriting': chunk_result.metadata.has_handwriting,
            'start_page': start_page,
            'end_page': end_page,
            'success': True
        }
        
    except Exception as e:
        logger.error(
            f"[CHUNK-ERROR] Error processing chunk {chunk_index} for document {document_id}: {str(e)}"
        )
        
        # Update progress to "failed"
        logger.info(f"[CHUNK-{chunk_index}] Updating status to 'failed' for document {document_id}")
        services = get_services()
        services['progress'].update_chunk_progress(
            document_id,
            chunk_index,
            "failed",
            error=str(e)
        )
        logger.info(f"[CHUNK-{chunk_index}] Status update to 'failed' completed")
        
        return {
            'chunk_index': chunk_index,
            'text': '',
            'confidence': ConfidenceLevel.LOW.value,
            'has_handwriting': False,
            'start_page': start_page,
            'end_page': end_page,
            'success': False,
            'error': str(e)
        }


@celery_app.task(name="app.tasks.document_tasks.aggregate_chunks_task")
def aggregate_chunks_task(chunk_results: List[Dict[str, Any]], document_id: str, pdf_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggregate results from parallel chunk processing.
    
    Args:
        chunk_results: List of chunk processing results
        document_id: Document identifier
        pdf_info: PDF metadata
        
    Returns:
        Aggregated processing results
    """
    try:
        logger.info(f"Aggregating {len(chunk_results)} chunk results for document {document_id}")
        
        # Calculate processing time
        services = get_services()
        progress_tracker = services['progress']
        start_time = progress_tracker.get_start_time(document_id)
        processing_time = time.time() - start_time if start_time else None
        
        if processing_time:
            logger.info(f"Total processing time for {document_id}: {processing_time:.2f} seconds")
        
        # Sort by chunk index
        chunk_results.sort(key=lambda x: x['chunk_index'])
        
        # Separate successful and failed chunks
        successful_chunks = [r for r in chunk_results if r['success']]
        failed_chunks = [r for r in chunk_results if not r['success']]
        
        # Combine text from successful chunks
        all_extracted_text = [r['text'] for r in successful_chunks]
        combined_text = "\n\n".join(all_extracted_text)
        
        # Calculate overall confidence
        confidence_scores = [r['confidence'] for r in successful_chunks]
        overall_confidence = _calculate_overall_confidence(confidence_scores)
        
        # Check for handwriting
        has_handwriting = any(r['has_handwriting'] for r in successful_chunks)
        
        # Determine final status
        total_chunks = len(chunk_results)
        completed_chunks = len(successful_chunks)
        failed_count = len(failed_chunks)
        
        if failed_count == 0:
            final_status = ProcessingStatus.COMPLETED
            error_message = None
        elif completed_chunks > 0:
            final_status = ProcessingStatus.PARTIAL_ERROR
            failed_pages = [f"{r['start_page']}-{r['end_page']}" for r in failed_chunks]
            error_message = (
                f"Processed {completed_chunks}/{total_chunks} chunks successfully. "
                f"Failed chunks (pages): {', '.join(failed_pages)}"
            )
        else:
            final_status = ProcessingStatus.ERROR
            error_message = "All chunks failed to process"
        
        # Create extraction notes
        extraction_notes = (
            f"Processed in {total_chunks} chunks using parallel processing. "
            f"Successful: {completed_chunks}, Failed: {failed_count}"
        )
        
        if failed_chunks:
            failed_pages = [f"{r['start_page']}-{r['end_page']}" for r in failed_chunks]
            extraction_notes += f". Failed chunks (pages): {', '.join(failed_pages)}"
        
        # Create final metadata
        chunk_progress = ChunkProgress(
            total_chunks=total_chunks,
            completed_chunks=completed_chunks,
            failed_chunks=failed_count,
            current_chunk=total_chunks
        )
        
        final_metadata = DocumentMetadata(
            page_count=pdf_info["page_count"],
            has_handwriting=has_handwriting,
            quality=ConfidenceLevel(overall_confidence),
            file_size=pdf_info["file_size"],
            mime_type="application/pdf",
            extraction_notes=extraction_notes,
            is_chunked=True,
            chunk_size=settings.chunk_size_pages,
            chunk_progress=chunk_progress
        )
        
        # Update document with final results
        asyncio.run(_update_document_final(
            document_id,
            final_status,
            combined_text,
            final_metadata,
            error_message,
            processing_time
        ))
        
        # Publish completion/failure event
        services = get_services()
        progress_tracker = services['progress']
        
        if final_status == ProcessingStatus.COMPLETED:
            progress_tracker.mark_completed(document_id)
        elif final_status == ProcessingStatus.ERROR:
            progress_tracker.mark_failed(document_id, error_message or "Processing failed")
        elif final_status == ProcessingStatus.PARTIAL_ERROR:
            # For partial errors, still mark as completed but with warning
            progress_tracker.mark_completed(document_id)
        
        logger.info(
            f"Aggregation complete for {document_id}: "
            f"{final_status.value} ({completed_chunks}/{total_chunks} chunks)"
        )
        
        return {
            'document_id': document_id,
            'status': final_status.value,
            'total_chunks': total_chunks,
            'completed_chunks': completed_chunks,
            'failed_chunks': failed_count,
            'text_length': len(combined_text)
        }
        
    except Exception as e:
        logger.error(f"Error aggregating chunks for document {document_id}: {str(e)}")
        
        # Update document to error state
        asyncio.run(_update_document_status(
            document_id,
            ProcessingStatus.ERROR,
            error_message=f"Failed to aggregate results: {str(e)}"
        ))
        
        # Publish failure event
        services = get_services()
        services['progress'].mark_failed(document_id, f"Failed to aggregate results: {str(e)}")
        
        raise


def _process_with_parallel_chunks(
    task,
    document_id: str,
    file_data: bytes,
    pdf_info: Dict[str, Any],
    chunking_service: PDFChunkingService,
    progress_tracker: RedisProgressTracker
) -> Dict[str, Any]:
    """Process document using parallel chunk processing."""
    
    # Split PDF into chunks
    chunks = asyncio.run(chunking_service.split_pdf(file_data))
    total_chunks = len(chunks)
    
    logger.info(f"Split document {document_id} into {total_chunks} chunks for parallel processing")
    
    # Update status
    asyncio.run(_update_document_status(
        document_id,
        ProcessingStatus.PROCESSING_CHUNKS
    ))
    
    # Initialize progress tracking
    progress_tracker.initialize_document(document_id, total_chunks)
    
    # Add small delay to allow SSE connections to establish
    time.sleep(0.5)
    
    # Create parallel chunk processing tasks
    chunk_tasks = []
    for idx, (chunk_bytes, start_page, end_page) in enumerate(chunks, 1):
        chunk_task = process_chunk_task.s(
            document_id=document_id,
            chunk_index=idx,
            chunk_data=chunk_bytes,
            start_page=start_page,
            end_page=end_page,
            total_chunks=total_chunks
        )
        chunk_tasks.append(chunk_task)
    
    # Use Celery chord to process chunks in parallel and aggregate results
    # group() processes tasks in parallel
    # chord() waits for all to complete then calls callback
    callback = aggregate_chunks_task.s(document_id=document_id, pdf_info=pdf_info)
    chord(chunk_tasks)(callback)
    
    return {
        'document_id': document_id,
        'status': 'processing_chunks',
        'total_chunks': total_chunks,
        'message': f'Processing {total_chunks} chunks in parallel'
    }


def _process_without_chunks(
    task,
    document_id: str,
    file_data: bytes,
    pdf_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Process small document without chunking."""
    
    # Get services
    services = get_services()
    gemini_service = services['gemini']
    progress_tracker = services['progress']
    
    # Get start time
    start_time = progress_tracker.get_start_time(document_id)
    
    # Update progress
    task.update_state(
        state='PROCESSING',
        meta={'status': 'Extracting text', 'progress': 50}
    )
    
    # Extract text using Gemini
    extraction_result = asyncio.run(gemini_service.extract_pdf_content(file_data))
    
    # Calculate processing time
    processing_time = time.time() - start_time if start_time else None
    
    if processing_time:
        logger.info(f"Total processing time for {document_id}: {processing_time:.2f} seconds")
    
    # Update metadata with file info
    metadata = extraction_result.metadata
    metadata.file_size = pdf_info["file_size"]
    metadata.is_chunked = False
    
    # Update document with extraction results
    asyncio.run(_update_document_final(
        document_id,
        ProcessingStatus.COMPLETED,
        extraction_result.text,
        metadata,
        None,
        processing_time
    ))
    
    # Mark as completed (no chunking, so no Redis progress tracking initialized)
    # This is for consistency, though SSE won't be used for small documents
    
    # Update progress
    task.update_state(
        state='SUCCESS',
        meta={'status': 'Completed', 'progress': 100}
    )
    
    return {
        'document_id': document_id,
        'status': 'completed',
        'text_length': len(extraction_result.text),
        'page_count': extraction_result.page_count
    }


def _calculate_overall_confidence(confidence_scores: List[str]) -> str:
    """Calculate overall confidence from chunk confidence scores."""
    if not confidence_scores:
        return ConfidenceLevel.LOW.value
    
    # Count confidence levels
    high_count = sum(1 for c in confidence_scores if c == ConfidenceLevel.HIGH.value)
    medium_count = sum(1 for c in confidence_scores if c == ConfidenceLevel.MEDIUM.value)
    
    total = len(confidence_scores)
    
    if high_count > total / 2:
        return ConfidenceLevel.HIGH.value
    elif high_count + medium_count > total / 2:
        return ConfidenceLevel.MEDIUM.value
    else:
        return ConfidenceLevel.LOW.value


async def _update_document_status(
    document_id: str,
    status: ProcessingStatus,
    task_id: str = None,
    error_message: str = None
):
    """Update document status in database."""
    from app.services.document_service import DocumentService
    
    service = DocumentService()
    
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }
    
    if task_id:
        update_data["task_id"] = task_id
    
    if error_message:
        update_data["error_message"] = error_message
    
    await service._update_document(document_id, update_data)


async def _update_document_final(
    document_id: str,
    status: ProcessingStatus,
    extracted_text: str,
    metadata: DocumentMetadata,
    error_message: str = None,
    processing_time: float = None
):
    """Update document with final processing results."""
    from app.services.document_service import DocumentService
    
    service = DocumentService()
    
    update_data = {
        "status": status,
        "extracted_text": extracted_text,
        "metadata": metadata.model_dump(),
        "updated_at": datetime.utcnow()
    }
    
    if error_message:
        update_data["error_message"] = error_message
    
    if processing_time is not None:
        update_data["processing_time_seconds"] = processing_time
    
    await service._update_document(document_id, update_data)
