"""Pydantic models for document-related data structures."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    QUEUED = "queued"  # Task queued in Celery
    EXTRACTING = "extracting"
    PROCESSING_CHUNKS = "processing_chunks"
    COMPLETED = "completed"
    ERROR = "error"
    PARTIAL_ERROR = "partial_error"  # Some chunks failed but others succeeded
    CANCELLED = "cancelled"  # Task was cancelled


class ConfidenceLevel(str, Enum):
    """Extraction confidence level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChunkProgress(BaseModel):
    """Progress information for chunked processing."""
    total_chunks: int = Field(..., description="Total number of chunks")
    completed_chunks: int = Field(default=0, description="Number of completed chunks")
    failed_chunks: int = Field(default=0, description="Number of failed chunks")
    current_chunk: int = Field(default=0, description="Currently processing chunk number")
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_chunks == 0:
            return 0.0
        return (self.completed_chunks / self.total_chunks) * 100


class DocumentMetadata(BaseModel):
    """Document metadata extracted during processing."""
    page_count: int = Field(default=0, description="Number of pages in document")
    has_handwriting: bool = Field(default=False, description="Whether handwriting was detected")
    quality: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM, description="Overall extraction quality")
    file_size: int = Field(default=0, description="File size in bytes")
    mime_type: str = Field(default="application/pdf", description="MIME type of the file")
    extraction_notes: Optional[str] = Field(default=None, description="Additional extraction notes")
    
    # Chunking metadata
    is_chunked: bool = Field(default=False, description="Whether document was processed in chunks")
    chunk_size: Optional[int] = Field(default=None, description="Number of pages per chunk")
    chunk_progress: Optional[ChunkProgress] = Field(default=None, description="Chunk processing progress")


class DocumentExtractionResult(BaseModel):
    """Result of document text extraction."""
    text: str = Field(..., description="Extracted text content")
    page_count: int = Field(..., description="Number of pages extracted")
    confidence: ConfidenceLevel = Field(..., description="Extraction confidence level")
    metadata: DocumentMetadata = Field(..., description="Document metadata")


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    status: ProcessingStatus = Field(..., description="Current processing status")
    task_id: Optional[str] = Field(default=None, description="Celery task ID for tracking")
    message: str = Field(default="Document uploaded successfully", description="Status message")


class DocumentResponse(BaseModel):
    """Complete document information response."""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    status: ProcessingStatus = Field(..., description="Current processing status")
    task_id: Optional[str] = Field(default=None, description="Celery task ID for tracking")
    task_status: Optional[str] = Field(default=None, description="Celery task status (PENDING, STARTED, SUCCESS, FAILURE)")
    progress_percentage: float = Field(default=0.0, description="Overall progress percentage (0-100)")
    extracted_text: Optional[str] = Field(default=None, description="Extracted text content")
    metadata: Optional[DocumentMetadata] = Field(default=None, description="Document metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    processing_time_seconds: Optional[float] = Field(default=None, description="Total processing time in seconds")
    error_message: Optional[str] = Field(default=None, description="Error message if processing failed")
    
    @property
    def status_message(self) -> str:
        """Get a human-readable status message."""
        if self.status == ProcessingStatus.PROCESSING_CHUNKS and self.metadata and self.metadata.chunk_progress:
            progress = self.metadata.chunk_progress
            return (
                f"Processing chunk {progress.current_chunk} of {progress.total_chunks} "
                f"({progress.progress_percentage:.1f}% complete)"
            )
        return self.status.value


class DocumentTextResponse(BaseModel):
    """Response containing only extracted text."""
    document_id: str = Field(..., description="Unique document identifier")
    text: str = Field(..., description="Extracted text content")
    page_count: int = Field(..., description="Number of pages")
    confidence: ConfidenceLevel = Field(..., description="Extraction confidence level")


class DocumentListResponse(BaseModel):
    """Response containing list of documents."""
    documents: List[DocumentResponse] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy", description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    services: Dict[str, bool] = Field(default_factory=dict, description="Service availability")
