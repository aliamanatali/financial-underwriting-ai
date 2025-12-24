# PDF Chunking Strategy - Implementation Guide

## Overview

This document describes the PDF chunking strategy implemented to handle large documents that exceed Gemini's timeout limits (60 seconds). The system automatically detects large PDFs and processes them in smaller chunks to avoid timeout errors.

## Problem Statement

**Issue**: Large PDFs (600+ pages) were causing `504 Deadline Exceeded` errors when processed as a single document.

**Root Cause**: Gemini API has a 60-second timeout limit, and processing large PDFs in one request exceeds this limit.

**Solution**: Implement automatic PDF chunking with batch processing, progress tracking, and graceful error handling.

## Architecture

### Components

1. **PDFChunkingService** (`app/services/pdf_chunking_service.py`)

   - Splits large PDFs into manageable chunks
   - Provides PDF metadata (page count, file size)
   - Determines if chunking is needed

2. **GeminiService** (`app/services/gemini_service.py`)

   - Enhanced with `extract_pdf_chunk()` method
   - Implements timeout handling (120s per chunk)
   - Retry logic with exponential backoff (3 attempts)

3. **DocumentService** (`app/services/document_service.py`)

   - Orchestrates chunked processing
   - Tracks progress during processing
   - Aggregates results from all chunks
   - Handles partial failures gracefully

4. **Document Models** (`app/models/document.py`)
   - Added `ChunkProgress` model for tracking
   - New status: `PROCESSING_CHUNKS`, `PARTIAL_ERROR`
   - Enhanced metadata with chunking information

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Gemini Timeout and Retry Configuration
GEMINI_TIMEOUT_SECONDS=120        # Timeout per chunk (default: 120s)
GEMINI_MAX_RETRIES=3              # Number of retry attempts (default: 3)

# PDF Chunking Configuration
CHUNK_SIZE_PAGES=1                # Pages per chunk (default: 1)
LARGE_FILE_THRESHOLD_MB=5.0       # File size threshold (default: 5.0 MB)
LARGE_FILE_PAGE_THRESHOLD=1       # Page count threshold (default: 1)
```

### Thresholds

A PDF is processed with chunking if it meets **either** condition:

- **Page count** > 1 page
- **File size** > 5.0 MB

You can adjust these thresholds based on your needs.

## How It Works

### 1. Document Upload

```python
# User uploads a PDF
POST /api/documents/upload
```

### 2. Automatic Detection

```python
# System checks if chunking is needed
pdf_info = await chunking_service.get_pdf_info(file_data)

should_chunk = chunking_service.should_use_chunking(
    page_count=pdf_info["page_count"],
    file_size_mb=pdf_info["file_size_mb"]
)
```

### 3. Processing Strategy

#### Small Documents (1 page only)

- Processed in a single request
- Uses original `extract_pdf_content()` method
- Fast and efficient

#### Multi-Page Documents (> 1 page or ≥ 5 MB)

- Split into chunks (1 page each by default)
- Each chunk processed separately
- Progress tracked in real-time
- Results aggregated at the end

### 4. Chunk Processing Flow

```
1. Split PDF into chunks (e.g., 600 pages → 600 chunks of 1 page)
2. Initialize progress tracking
3. For each chunk:
   a. Update status: "Processing chunk X of Y"
   b. Extract text with retry logic
   c. Update progress
   d. Continue even if chunk fails
4. Aggregate all results
5. Calculate overall confidence
6. Update final status
```

### 5. Progress Tracking

During processing, the document status shows:

```json
{
  "status": "processing_chunks",
  "metadata": {
    "chunk_progress": {
      "total_chunks": 600,
      "completed_chunks": 300,
      "failed_chunks": 0,
      "current_chunk": 301,
      "progress_percentage": 50.0
    }
  }
}
```

## Error Handling

### Retry Logic

Each chunk is retried up to 3 times with exponential backoff:

1. **First attempt**: Immediate
2. **Second attempt**: Wait 1 second
3. **Third attempt**: Wait 2 seconds

For rate limit errors, longer waits are used (5, 10, 20 seconds).

### Partial Failures

If some chunks fail but others succeed:

- Status: `PARTIAL_ERROR`
- Extracted text includes successful chunks
- Error message lists failed chunk ranges
- Example: "Processed 28/30 chunks successfully. Failed chunks: 41-60, 121-140"

### Complete Failures

If all chunks fail:

- Status: `ERROR`
- Error message: "All chunks failed to process"
- No extracted text available

## API Response Examples

### Small Document (No Chunking)

```json
{
  "document_id": "abc123",
  "filename": "small.pdf",
  "status": "completed",
  "metadata": {
    "page_count": 25,
    "file_size": 1048576,
    "is_chunked": false,
    "quality": "high"
  }
}
```

### Large Document (With Chunking)

```json
{
  "document_id": "xyz789",
  "filename": "large.pdf",
  "status": "completed",
  "metadata": {
    "page_count": 600,
    "file_size": 2097152,
    "is_chunked": true,
    "chunk_size": 1,
    "chunk_progress": {
      "total_chunks": 600,
      "completed_chunks": 600,
      "failed_chunks": 0,
      "current_chunk": 600,
      "progress_percentage": 100.0
    },
    "quality": "high",
    "extraction_notes": "Processed in 600 chunks. Successful: 600, Failed: 0"
  }
}
```

### Partial Failure

```json
{
  "document_id": "def456",
  "filename": "problematic.pdf",
  "status": "partial_error",
  "metadata": {
    "page_count": 600,
    "is_chunked": true,
    "chunk_progress": {
      "total_chunks": 600,
      "completed_chunks": 595,
      "failed_chunks": 5
    },
    "extraction_notes": "Processed in 600 chunks. Successful: 595, Failed: 5. Failed chunks: 41-41, 121-121, 234-234, 456-456, 589-589"
  },
  "error_message": "Processed 595/600 chunks successfully. Failed chunks: 41-41, 121-121, 234-234, 456-456, 589-589"
}
```

## Performance Characteristics

### Single-Page Documents (1 page)

- **Processing time**: 10-30 seconds
- **Memory usage**: Low
- **API calls**: 1

### Multi-Page Documents (e.g., 600 pages, 600 chunks)

- **Processing time**: 50-300 minutes (5-30s per chunk)
- **Memory usage**: Low (one page at a time)
- **API calls**: 600 (one per page)
- **Parallelization**: Sequential (to avoid rate limits)
- **Progress tracking**: Highly granular (per-page updates)

## Benefits

✅ **Handles Large Documents**: No more timeout errors for 600+ page PDFs
✅ **Progress Tracking**: Real-time status updates during processing
✅ **Graceful Degradation**: Partial results if some chunks fail
✅ **Automatic Detection**: No manual configuration needed
✅ **Retry Logic**: Handles transient errors automatically
✅ **Backward Compatible**: Small files use original fast method
✅ **Configurable**: Adjust chunk size and thresholds as needed

## Monitoring and Logging

The system provides detailed logging:

```
INFO - Chunking recommended: 648 pages, 2.11 MB (thresholds: 1 page, 5.0 MB)
INFO - Processing large document with chunking strategy (648 pages, 2.11 MB)
INFO - Split document into 648 chunks
INFO - Processing chunk 1 of 648 (pages 1-1)
INFO - Successfully processed chunk 1 of 648 (1/648 complete)
...
INFO - Large document processing complete: completed (648/648 chunks)
```

## Troubleshooting

### Issue: All chunks failing

**Possible causes**:

- Invalid Gemini API key
- Network connectivity issues
- Corrupted PDF file

**Solution**: Check logs for specific error messages

### Issue: Some chunks failing consistently

**Possible causes**:

- Specific pages are corrupted
- Complex formatting in certain sections
- Rate limiting

**Solution**:

- Review failed chunk ranges
- Reduce chunk size for problematic documents
- Increase retry delays

### Issue: Processing too slow

**Possible causes**:

- Chunk size too small (too many API calls)
- Network latency

**Solution**:

- Increase `CHUNK_SIZE_PAGES` (e.g., to 5, 10, or 20 for faster processing)
- Ensure good network connection
- Note: With 1 page per chunk, processing is slower but provides maximum granularity

## Future Enhancements

Potential improvements:

1. **Parallel Processing**: Process multiple chunks simultaneously (with rate limit management)
2. **Smart Chunking**: Adjust chunk size based on document complexity
3. **Resume Capability**: Resume processing from last successful chunk
4. **Caching**: Cache successfully processed chunks
5. **Priority Queue**: Process important chunks first

## Testing

To test with a large PDF:

1. Upload a 600+ page PDF through the API or frontend
2. Monitor the logs for chunking activity
3. Check the document status for progress updates
4. Verify the final extracted text includes all pages

## Conclusion

The PDF chunking strategy successfully solves the timeout issue for large documents while maintaining high quality extraction and providing excellent user experience through progress tracking and graceful error handling.
