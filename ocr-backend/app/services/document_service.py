"""Document service for orchestrating document processing."""

from datetime import datetime
from typing import Optional, Dict, Any, List
import json

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from celery.result import AsyncResult
import redis

from app.config import settings
from app.models.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentExtractionResult,
    ProcessingStatus,
    DocumentMetadata,
    ChunkProgress,
    ConfidenceLevel
)
from app.services.gemini_service import GeminiService
from app.services.storage_service import StorageService
from app.services.pdf_chunking_service import PDFChunkingService
from app.utils.logger import logger


class DocumentService:
    """Service for managing document processing workflow."""
    
    def __init__(self):
        """Initialize document service."""
        self.storage_service = StorageService()
        self.gemini_service = GeminiService()
        self.chunking_service = PDFChunkingService(
            chunk_size_pages=settings.chunk_size_pages
        )
        self.db: Optional[AsyncIOMotorDatabase] = None
        
        # Initialize Redis for shared state (used when MongoDB is not configured)
        self.redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True
        )
        
        # Initialize MongoDB if configured
        if settings.use_mongodb:
            self._init_mongodb()
        else:
            # Use Redis-backed storage for documents (shared between processes)
            logger.info("Using Redis-backed document storage (MongoDB not configured)")
    
    def _init_mongodb(self):
        """Initialize MongoDB connection."""
        try:
            client = AsyncIOMotorClient(settings.mongodb_uri)
            self.db = client[settings.mongodb_database]
            logger.info("MongoDB connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB: {str(e)}")
            raise
    
    async def upload_document(
        self,
        file_data: bytes,
        filename: str
    ) -> DocumentUploadResponse:
        """
        Upload a document and queue Celery task for processing.
        
        Args:
            file_data: PDF file content as bytes
            filename: Original filename
            
        Returns:
            DocumentUploadResponse with document ID, task ID, and status
        """
        try:
            # Save file to storage
            file_id, storage_path = await self.storage_service.save_file(
                file_data,
                filename
            )
            
            # Queue Celery task for processing
            from app.tasks.document_tasks import process_document_task
            task = process_document_task.delay(file_id, storage_path)
            
            # Create document record
            document_data = {
                "document_id": file_id,
                "filename": filename,
                "storage_path": storage_path,
                "status": ProcessingStatus.QUEUED,
                "task_id": task.id,
                "task_status": "PENDING",
                "progress_percentage": 0.0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "extracted_text": None,
                "metadata": None,
                "error_message": None
            }
            
            # Save to database or Redis storage
            if self.db is not None:
                await self.db.documents.insert_one(document_data)
            else:
                # Save to Redis
                key = f"document:{file_id}"
                doc_copy = document_data.copy()
                doc_copy['created_at'] = doc_copy['created_at'].isoformat()
                doc_copy['updated_at'] = doc_copy['updated_at'].isoformat()
                self.redis_client.set(key, json.dumps(doc_copy))
            
            logger.info(f"Document uploaded and queued: {file_id} ({filename}), task_id: {task.id}")
            
            return DocumentUploadResponse(
                document_id=file_id,
                filename=filename,
                status=ProcessingStatus.QUEUED,
                task_id=task.id,
                message="Document uploaded successfully. Processing queued in background."
            )
            
        except Exception as e:
            logger.error(f"Failed to upload document: {str(e)}")
            raise
    
    async def process_document(self, document_id: str) -> DocumentResponse:
        """
        Process a document: extract text using Gemini.
        Automatically detects large files and uses chunking strategy.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            DocumentResponse with extraction results
        """
        try:
            # Get document record
            doc = await self._get_document_record(document_id)
            if not doc:
                raise ValueError(f"Document not found: {document_id}")
            
            # Retrieve file from storage
            file_data = await self.storage_service.get_file(doc["storage_path"])
            
            # Get PDF info to determine processing strategy
            pdf_info = await self.chunking_service.get_pdf_info(file_data)
            
            # Determine if chunking is needed
            should_chunk = self.chunking_service.should_use_chunking(
                page_count=pdf_info["page_count"],
                file_size_mb=pdf_info["file_size_mb"],
                page_threshold=settings.large_file_page_threshold,
                size_threshold_mb=settings.large_file_threshold_mb
            )
            
            if should_chunk:
                logger.info(
                    f"Processing large document {document_id} with chunking strategy "
                    f"({pdf_info['page_count']} pages, {pdf_info['file_size_mb']} MB)"
                )
                return await self._process_large_document(document_id, file_data, pdf_info)
            else:
                logger.info(
                    f"Processing small document {document_id} without chunking "
                    f"({pdf_info['page_count']} pages, {pdf_info['file_size_mb']} MB)"
                )
                return await self._process_small_document(document_id, file_data, pdf_info)
            
        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {str(e)}")
            
            # Update status to error
            await self._update_document(document_id, {
                "status": ProcessingStatus.ERROR,
                "error_message": str(e),
                "updated_at": datetime.utcnow()
            })
            
            raise
    
    async def _process_small_document(
        self,
        document_id: str,
        file_data: bytes,
        pdf_info: Dict[str, Any]
    ) -> DocumentResponse:
        """
        Process a small document without chunking.
        
        Args:
            document_id: Document identifier
            file_data: PDF file bytes
            pdf_info: PDF metadata
            
        Returns:
            DocumentResponse with extraction results
        """
        # Update status to extracting
        await self._update_document_status(
            document_id,
            ProcessingStatus.EXTRACTING
        )
        
        # Extract text using Gemini
        extraction_result = await self.gemini_service.extract_pdf_content(file_data)
        
        # Update metadata with file info
        metadata = extraction_result.metadata
        metadata.file_size = pdf_info["file_size"]
        metadata.is_chunked = False
        
        # Update document with extraction results
        update_data = {
            "status": ProcessingStatus.COMPLETED,
            "extracted_text": extraction_result.text,
            "metadata": metadata.model_dump(),
            "updated_at": datetime.utcnow()
        }
        
        await self._update_document(document_id, update_data)
        
        logger.info(f"Small document processed successfully: {document_id}")
        
        return await self.get_document(document_id)
    
    async def _process_large_document(
        self,
        document_id: str,
        file_data: bytes,
        pdf_info: Dict[str, Any]
    ) -> DocumentResponse:
        """
        Process a large document using chunking strategy.
        
        Args:
            document_id: Document identifier
            file_data: PDF file bytes
            pdf_info: PDF metadata
            
        Returns:
            DocumentResponse with extraction results
        """
        try:
            # Split PDF into chunks
            chunks = await self.chunking_service.split_pdf(file_data)
            total_chunks = len(chunks)
            
            logger.info(f"Split document {document_id} into {total_chunks} chunks")
            
            # Initialize chunk progress
            chunk_progress = ChunkProgress(
                total_chunks=total_chunks,
                completed_chunks=0,
                failed_chunks=0,
                current_chunk=0
            )
            
            # Update status to processing chunks
            await self._update_document(document_id, {
                "status": ProcessingStatus.PROCESSING_CHUNKS,
                "metadata": {
                    "page_count": pdf_info["page_count"],
                    "file_size": pdf_info["file_size"],
                    "is_chunked": True,
                    "chunk_size": settings.chunk_size_pages,
                    "chunk_progress": chunk_progress.model_dump()
                },
                "updated_at": datetime.utcnow()
            })
            
            # Process each chunk
            all_extracted_text = []
            failed_chunks = []
            overall_confidence_scores = []
            has_handwriting = False
            
            for idx, (chunk_bytes, start_page, end_page) in enumerate(chunks, 1):
                chunk_info = f"chunk {idx} of {total_chunks}"
                
                try:
                    # Update current chunk
                    chunk_progress.current_chunk = idx
                    await self._update_document(document_id, {
                        "metadata.chunk_progress": chunk_progress.model_dump(),
                        "updated_at": datetime.utcnow()
                    })
                    
                    logger.info(
                        f"Processing {chunk_info} for document {document_id} "
                        f"(pages {start_page}-{end_page})"
                    )
                    
                    # Extract text from chunk
                    chunk_result = await self.gemini_service.extract_pdf_chunk(
                        pdf_chunk=chunk_bytes,
                        chunk_info=chunk_info,
                        start_page=start_page,
                        end_page=end_page
                    )
                    
                    # Collect results
                    all_extracted_text.append(chunk_result.text)
                    overall_confidence_scores.append(chunk_result.confidence)
                    
                    if chunk_result.metadata.has_handwriting:
                        has_handwriting = True
                    
                    # Update progress
                    chunk_progress.completed_chunks += 1
                    await self._update_document(document_id, {
                        "metadata.chunk_progress": chunk_progress.model_dump(),
                        "updated_at": datetime.utcnow()
                    })
                    
                    logger.info(
                        f"Successfully processed {chunk_info} for document {document_id} "
                        f"({chunk_progress.completed_chunks}/{total_chunks} complete)"
                    )
                    
                except Exception as chunk_error:
                    logger.error(
                        f"Failed to process {chunk_info} for document {document_id}: "
                        f"{str(chunk_error)}"
                    )
                    failed_chunks.append({
                        "chunk": idx,
                        "pages": f"{start_page}-{end_page}",
                        "error": str(chunk_error)
                    })
                    chunk_progress.failed_chunks += 1
                    
                    # Continue processing other chunks
                    continue
            
            # Aggregate results
            combined_text = "\n\n".join(all_extracted_text)
            
            # Calculate overall confidence
            if overall_confidence_scores:
                # Count confidence levels
                high_count = sum(1 for c in overall_confidence_scores if c == ConfidenceLevel.HIGH)
                medium_count = sum(1 for c in overall_confidence_scores if c == ConfidenceLevel.MEDIUM)
                
                if high_count > len(overall_confidence_scores) / 2:
                    overall_confidence = ConfidenceLevel.HIGH
                elif high_count + medium_count > len(overall_confidence_scores) / 2:
                    overall_confidence = ConfidenceLevel.MEDIUM
                else:
                    overall_confidence = ConfidenceLevel.LOW
            else:
                overall_confidence = ConfidenceLevel.LOW
            
            # Determine final status
            if chunk_progress.failed_chunks == 0:
                final_status = ProcessingStatus.COMPLETED
                error_message = None
            elif chunk_progress.completed_chunks > 0:
                final_status = ProcessingStatus.PARTIAL_ERROR
                error_message = (
                    f"Processed {chunk_progress.completed_chunks}/{total_chunks} chunks successfully. "
                    f"Failed chunks: {', '.join([f['pages'] for f in failed_chunks])}"
                )
            else:
                final_status = ProcessingStatus.ERROR
                error_message = "All chunks failed to process"
            
            # Create extraction notes
            extraction_notes = (
                f"Processed in {total_chunks} chunks. "
                f"Successful: {chunk_progress.completed_chunks}, "
                f"Failed: {chunk_progress.failed_chunks}"
            )
            
            if failed_chunks:
                extraction_notes += f". Failed chunks: {', '.join([f['pages'] for f in failed_chunks])}"
            
            # Create final metadata
            final_metadata = DocumentMetadata(
                page_count=pdf_info["page_count"],
                has_handwriting=has_handwriting,
                quality=overall_confidence,
                file_size=pdf_info["file_size"],
                mime_type="application/pdf",
                extraction_notes=extraction_notes,
                is_chunked=True,
                chunk_size=settings.chunk_size_pages,
                chunk_progress=chunk_progress
            )
            
            # Update document with final results
            update_data = {
                "status": final_status,
                "extracted_text": combined_text,
                "metadata": final_metadata.model_dump(),
                "error_message": error_message,
                "updated_at": datetime.utcnow()
            }
            
            await self._update_document(document_id, update_data)
            
            logger.info(
                f"Large document processing complete for {document_id}: "
                f"{final_status.value} ({chunk_progress.completed_chunks}/{total_chunks} chunks)"
            )
            
            return await self.get_document(document_id)
            
        except Exception as e:
            logger.error(f"Failed to process large document {document_id}: {str(e)}")
            raise
    
    async def get_document(self, document_id: str) -> DocumentResponse:
        """
        Get document details by ID.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            DocumentResponse with document details
        """
        doc = await self._get_document_record(document_id)
        
        if not doc:
            raise ValueError(f"Document not found: {document_id}")
        
        # Parse metadata if present
        metadata = None
        if doc.get("metadata"):
            metadata = DocumentMetadata(**doc["metadata"])
        
        return DocumentResponse(
            document_id=doc["document_id"],
            filename=doc["filename"],
            status=doc["status"],
            extracted_text=doc.get("extracted_text"),
            metadata=metadata,
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            processing_time_seconds=doc.get("processing_time_seconds"),
            error_message=doc.get("error_message")
        )
    
    async def get_document_text(self, document_id: str) -> str:
        """
        Get extracted text for a document.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            Extracted text content
        """
        doc = await self._get_document_record(document_id)
        
        if not doc:
            raise ValueError(f"Document not found: {document_id}")
        
        if doc["status"] != ProcessingStatus.COMPLETED:
            raise ValueError(f"Document not yet processed: {document_id}")
        
        return doc.get("extracted_text", "")
    
    async def list_documents(self) -> List[DocumentResponse]:
        """
        Get a list of all documents.
        
        Returns:
            List of DocumentResponse objects
        """
        documents = []
        
        if self.db is not None:
            # Get all documents from MongoDB
            cursor = self.db.documents.find({})
            async for doc in cursor:
                metadata = None
                if doc.get("metadata"):
                    metadata = DocumentMetadata(**doc["metadata"])
                
                documents.append(DocumentResponse(
                    document_id=doc["document_id"],
                    filename=doc["filename"],
                    status=doc["status"],
                    extracted_text=doc.get("extracted_text"),
                    metadata=metadata,
                    created_at=doc["created_at"],
                    updated_at=doc["updated_at"],
                    processing_time_seconds=doc.get("processing_time_seconds"),
                    error_message=doc.get("error_message")
                ))
        else:
            # Get all documents from Redis storage
            keys = self.redis_client.keys("document:*")
            for key in keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        doc = json.loads(data)
                        # Convert ISO strings back to datetime
                        if 'created_at' in doc and isinstance(doc['created_at'], str):
                            doc['created_at'] = datetime.fromisoformat(doc['created_at'])
                        if 'updated_at' in doc and isinstance(doc['updated_at'], str):
                            doc['updated_at'] = datetime.fromisoformat(doc['updated_at'])
                        
                        metadata = None
                        if doc.get("metadata"):
                            metadata = DocumentMetadata(**doc["metadata"])
                        
                        documents.append(DocumentResponse(
                            document_id=doc.get("document_id", key.split(":")[-1]),
                            filename=doc.get("filename", "unknown"),
                            status=doc.get("status", ProcessingStatus.QUEUED),
                            extracted_text=doc.get("extracted_text"),
                            metadata=metadata,
                            created_at=doc.get("created_at", datetime.utcnow()),
                            updated_at=doc.get("updated_at", datetime.utcnow()),
                            processing_time_seconds=doc.get("processing_time_seconds"),
                            error_message=doc.get("error_message")
                        ))
                except Exception as e:
                    logger.error(f"Error parsing document from Redis key {key}: {str(e)}")
                    continue
        
        # Deduplicate by document_id (in case of Redis key issues)
        seen_ids = set()
        unique_documents = []
        for doc in documents:
            if doc.document_id not in seen_ids:
                seen_ids.add(doc.document_id)
                unique_documents.append(doc)
            else:
                logger.warning(f"Duplicate document_id found in list_documents: {doc.document_id}")
        
        # Sort by created_at descending (newest first)
        unique_documents.sort(key=lambda x: x.created_at, reverse=True)
        
        return unique_documents
    
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and its associated file.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            True if deleted successfully
        """
        try:
            doc = await self._get_document_record(document_id)
            
            if not doc:
                raise ValueError(f"Document not found: {document_id}")
            
            # Delete file from storage
            await self.storage_service.delete_file(doc["storage_path"])
            
            # Delete from database or Redis storage
            if self.db is not None:
                await self.db.documents.delete_one({"document_id": document_id})
            else:
                key = f"document:{document_id}"
                self.redis_client.delete(key)
            
            logger.info(f"Document deleted: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document: {str(e)}")
            return False
    
    async def _get_document_record(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document record from database or Redis storage."""
        if self.db is not None:
            return await self.db.documents.find_one({"document_id": document_id})
        else:
            # Get from Redis
            key = f"document:{document_id}"
            data = self.redis_client.get(key)
            if data:
                doc = json.loads(data)
                # Convert ISO strings back to datetime
                if 'created_at' in doc and isinstance(doc['created_at'], str):
                    doc['created_at'] = datetime.fromisoformat(doc['created_at'])
                if 'updated_at' in doc and isinstance(doc['updated_at'], str):
                    doc['updated_at'] = datetime.fromisoformat(doc['updated_at'])
                return doc
            return None
    
    async def _update_document_status(
        self,
        document_id: str,
        status: ProcessingStatus
    ):
        """Update document processing status."""
        await self._update_document(document_id, {
            "status": status,
            "updated_at": datetime.utcnow()
        })
    
    async def _update_document(
        self,
        document_id: str,
        update_data: Dict[str, Any]
    ):
        """Update document record."""
        if self.db is not None:
            await self.db.documents.update_one(
                {"document_id": document_id},
                {"$set": update_data}
            )
        else:
            # Update in Redis
            key = f"document:{document_id}"
            doc = await self._get_document_record(document_id)
            if doc:
                doc.update(update_data)
                # Convert datetime to ISO string for JSON serialization
                doc_copy = doc.copy()
                if 'created_at' in doc_copy and isinstance(doc_copy['created_at'], datetime):
                    doc_copy['created_at'] = doc_copy['created_at'].isoformat()
                if 'updated_at' in doc_copy and isinstance(doc_copy['updated_at'], datetime):
                    doc_copy['updated_at'] = doc_copy['updated_at'].isoformat()
                self.redis_client.set(key, json.dumps(doc_copy))
