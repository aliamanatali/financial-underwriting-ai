"""PDF chunking service for splitting large PDFs into manageable chunks."""

import io
from typing import List, Tuple, Dict, Any
from PyPDF2 import PdfReader, PdfWriter

from app.utils.logger import logger


class PDFChunkingService:
    """Service for splitting large PDFs into smaller chunks."""
    
    def __init__(self, chunk_size_pages: int = 20):
        """
        Initialize PDF chunking service.
        
        Args:
            chunk_size_pages: Number of pages per chunk (default: 20)
        """
        self.chunk_size_pages = chunk_size_pages
        logger.info(f"Initialized PDF chunking service with chunk size: {chunk_size_pages} pages")
    
    async def get_pdf_info(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Get PDF metadata (page count, file size).
        
        Args:
            pdf_bytes: PDF file content as bytes
            
        Returns:
            Dictionary with PDF information
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            
            page_count = len(reader.pages)
            file_size = len(pdf_bytes)
            
            # Get additional metadata if available
            metadata = reader.metadata or {}
            
            info = {
                "page_count": page_count,
                "file_size": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "title": metadata.get("/Title", ""),
                "author": metadata.get("/Author", ""),
                "subject": metadata.get("/Subject", ""),
                "creator": metadata.get("/Creator", "")
            }
            
            logger.info(
                f"PDF info: {page_count} pages, "
                f"{info['file_size_mb']} MB"
            )
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get PDF info: {str(e)}")
            raise
    
    async def split_pdf(
        self,
        pdf_bytes: bytes,
        chunk_size: int = None
    ) -> List[Tuple[bytes, int, int]]:
        """
        Split PDF into chunks.
        
        Args:
            pdf_bytes: PDF file content as bytes
            chunk_size: Number of pages per chunk (overrides default if provided)
            
        Returns:
            List of tuples: (chunk_bytes, start_page, end_page)
        """
        try:
            chunk_size = chunk_size or self.chunk_size_pages
            
            # Read the PDF
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            logger.info(
                f"Splitting PDF with {total_pages} pages into chunks of {chunk_size} pages"
            )
            
            chunks = []
            
            # Split into chunks
            for start_page in range(0, total_pages, chunk_size):
                end_page = min(start_page + chunk_size, total_pages)
                
                # Create a new PDF for this chunk
                writer = PdfWriter()
                
                # Add pages to the chunk
                for page_num in range(start_page, end_page):
                    writer.add_page(reader.pages[page_num])
                
                # Write chunk to bytes
                chunk_buffer = io.BytesIO()
                writer.write(chunk_buffer)
                chunk_bytes = chunk_buffer.getvalue()
                
                # Store chunk with 1-based page numbers for user-friendly display
                chunks.append((chunk_bytes, start_page + 1, end_page))
                
                logger.debug(
                    f"Created chunk: pages {start_page + 1}-{end_page} "
                    f"({len(chunk_bytes)} bytes)"
                )
            
            logger.info(f"Successfully split PDF into {len(chunks)} chunks")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to split PDF: {str(e)}")
            raise
    
    def should_use_chunking(
        self,
        page_count: int,
        file_size_mb: float,
        page_threshold: int = 50,
        size_threshold_mb: float = 5.0
    ) -> bool:
        """
        Determine if a PDF should be processed using chunking.
        
        Args:
            page_count: Number of pages in the PDF
            file_size_mb: File size in megabytes
            page_threshold: Page count threshold for chunking
            size_threshold_mb: File size threshold in MB for chunking
            
        Returns:
            True if chunking should be used, False otherwise
        """
        should_chunk = (
            page_count > page_threshold or 
            file_size_mb > size_threshold_mb
        )
        
        if should_chunk:
            logger.info(
                f"Chunking recommended: {page_count} pages, {file_size_mb} MB "
                f"(thresholds: {page_threshold} pages, {size_threshold_mb} MB)"
            )
        else:
            logger.info(
                f"Chunking not needed: {page_count} pages, {file_size_mb} MB"
            )
        
        return should_chunk
    
    def calculate_chunk_count(
        self,
        page_count: int,
        chunk_size: int = None
    ) -> int:
        """
        Calculate the number of chunks needed for a PDF.
        
        Args:
            page_count: Total number of pages
            chunk_size: Pages per chunk (uses default if not provided)
            
        Returns:
            Number of chunks needed
        """
        chunk_size = chunk_size or self.chunk_size_pages
        return (page_count + chunk_size - 1) // chunk_size  # Ceiling division
