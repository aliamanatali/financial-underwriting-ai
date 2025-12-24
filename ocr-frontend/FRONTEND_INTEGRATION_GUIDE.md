# Frontend Integration with Celery Backend - Complete Guide

## Overview

The Next.js frontend has been successfully updated to integrate with the new Celery-based asynchronous document processing system.

## What's New

### 1. **Updated TypeScript Types** ([`lib/types.ts`](lib/types.ts))

- Added `DocumentStatus`, `TaskStatus`, and `ChunkStatus` type definitions
- Added `UploadResponse` with `task_id` field
- Added `ProcessingStatus` interface for status polling
- Added `ProcessingProgress` interface for detailed progress tracking
- Added `ChunkProgress` interface for chunk-level details

### 2. **Enhanced API Client** ([`lib/api.ts`](lib/api.ts))

- `getDocumentStatus(documentId)` - Get processing status
- `getDocumentProgress(documentId)` - Get detailed progress with chunk info
- Updated `uploadDocument()` to handle new response format with `task_id`

### 3. **Updated Components**

#### DocumentUpload ([`components/DocumentUpload.tsx`](components/DocumentUpload.tsx))

- Handles new upload response with `task_id`
- Shows "Processing in background..." message
- Auto-redirects to document detail page after 1 second
- Passes both `documentId` and `taskId` to success callback

#### DocumentList ([`components/DocumentList.tsx`](components/DocumentList.tsx))

- Shows processing status badges (PENDING, PROCESSING, COMPLETED, FAILED)
- Displays status icons with animations
- Auto-refreshes every 5 seconds if any documents are processing
- Proper cleanup of polling intervals on unmount

#### DocumentViewer ([`components/DocumentViewer.tsx`](components/DocumentViewer.tsx))

- Polls for progress every 2 seconds while processing
- Displays ProcessingProgress component during processing
- Shows extracted text when completed
- Shows error message if failed
- Stops polling when status is COMPLETED or FAILED
- Proper cleanup of polling intervals

#### ProcessingProgress (NEW: [`components/ProcessingProgress.tsx`](components/ProcessingProgress.tsx))

- Overall progress bar with percentage
- "Processing chunk X of Y" message
- Chunk-level status list with icons
- Completed vs total chunks counter
- Failed chunks warning
- Error messages display

## User Experience Flow

### 1. Upload Document

```
User uploads PDF → Sees "Upload successful! Processing in background..."
                 → Redirected to document detail page (1 second delay)
```

### 2. View Processing Progress

```
Document Detail Page:
├── Document metadata (filename, status, file size, pages)
├── Processing Progress Component
│   ├── Progress bar: "30%"
│   ├── Status: "Processing chunk 3 of 10"
│   ├── Chunks: "3 / 10 chunks completed"
│   └── Chunk Details:
│       ├── ✓ Chunk 1 (Pages 1-2) - COMPLETED
│       ├── ✓ Chunk 2 (Pages 3-4) - COMPLETED
│       ├── ⏳ Chunk 3 (Pages 5-6) - PROCESSING
│       └── ⏸ Chunk 4-10 - PENDING
└── Auto-refreshes every 2 seconds
```

### 3. View Completed Document

```
Document Detail Page:
├── Document metadata with "COMPLETED" status
├── Action buttons (Copy Text, Download Text)
└── Extracted text display
```

### 4. View Failed Document

```
Document Detail Page:
├── Document metadata with "FAILED" status
└── Error message with details
```

## Polling Logic

### Smart Polling Implementation

- **Document List**: Polls every 5 seconds if ANY documents are processing
- **Document Viewer**: Polls every 2 seconds while current document is processing
- **Auto-stop**: Polling stops when status becomes COMPLETED or FAILED
- **Cleanup**: All intervals are properly cleaned up on component unmount

## Testing the Integration

### Prerequisites

1. Backend server running on `http://localhost:8000`
2. Celery worker running: `celery -A app.celery_app worker --loglevel=info`
3. Redis running on `localhost:6379`
4. Frontend running on `http://localhost:3000`

### Test Scenarios

#### Test 1: Upload and Process Document

1. Navigate to `http://localhost:3000`
2. Upload a PDF file
3. Verify:
   - ✅ Success message shows "Processing in background..."
   - ✅ Auto-redirect to document detail page
   - ✅ Progress bar appears
   - ✅ Chunk status updates in real-time
   - ✅ Page auto-refreshes every 2 seconds
   - ✅ Extracted text appears when completed

#### Test 2: Document List Auto-Refresh

1. Upload a document
2. Navigate back to home page
3. Verify:
   - ✅ Document shows "PROCESSING" status with spinner
   - ✅ List auto-refreshes every 5 seconds
   - ✅ Status updates to "COMPLETED" when done
   - ✅ Auto-refresh stops when no processing documents

#### Test 3: Multi-Page Document

1. Upload a multi-page PDF (10+ pages)
2. Watch progress updates
3. Verify:
   - ✅ Chunk progress shows correctly
   - ✅ "Processing chunk X of Y" updates
   - ✅ Individual chunk statuses update
   - ✅ Progress percentage increases
   - ✅ Completed chunks counter updates

#### Test 4: Error Handling

1. Upload an invalid or corrupted PDF
2. Verify:
   - ✅ Status changes to "FAILED"
   - ✅ Error message displays
   - ✅ Polling stops
   - ✅ No extracted text shown

## API Endpoints Used

### Upload Document

```
POST /api/documents/upload
Response: {
  document_id: string,
  task_id: string,
  filename: string,
  status: "pending",
  message: string
}
```

### Get Document Status

```
GET /api/documents/{id}/status
Response: {
  status: "pending" | "processing" | "completed" | "failed",
  task_status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED",
  progress_percentage: number,
  message: string
}
```

### Get Document Progress

```
GET /api/documents/{id}/progress
Response: {
  document_id: string,
  status: string,
  progress_percentage: number,
  total_chunks: number,
  completed_chunks: number,
  failed_chunks: number,
  current_chunk: number | null,
  chunks: [
    {
      chunk_index: number,
      status: "pending" | "processing" | "completed" | "failed",
      pages: string,
      error?: string
    }
  ],
  error_message?: string
}
```

### Get Document Details

```
GET /api/documents/{id}
Response: {
  document_id: string,
  filename: string,
  status: string,
  created_at: string,
  updated_at: string,
  metadata: {...},
  error_message?: string
}
```

### Get Extracted Text

```
GET /api/documents/{id}/text
Response: {
  document_id: string,
  text: string,
  page_count: number,
  confidence?: number,
  metadata?: {...}
}
```

## Key Features Implemented

✅ **Immediate Upload Response** - No waiting for processing to complete
✅ **Real-time Progress Updates** - Via polling every 2 seconds
✅ **Chunk-level Progress Visualization** - See individual chunk status
✅ **Auto-refresh Document List** - Updates every 5 seconds when processing
✅ **Progress Bar with Percentage** - Visual feedback on completion
✅ **Error Handling and Display** - Clear error messages
✅ **Clean Polling Lifecycle Management** - Proper cleanup on unmount
✅ **Status Badges with Icons** - Visual indicators for all statuses
✅ **Responsive UI** - Works on all screen sizes

## Performance Considerations

- **Polling Intervals**: 2s for detail page, 5s for list page
- **Auto-stop Polling**: Stops when processing completes
- **Efficient Updates**: Only fetches progress when needed
- **Memory Management**: Proper cleanup of intervals

## Browser Compatibility

- Modern browsers with ES6+ support
- Requires JavaScript enabled
- Uses Fetch API for HTTP requests
- Uses async/await syntax

## Troubleshooting

### Issue: Progress not updating

**Solution**: Check that Celery worker is running and Redis is accessible

### Issue: Upload succeeds but no progress shown

**Solution**: Verify backend endpoints `/api/documents/{id}/status` and `/api/documents/{id}/progress` are working

### Issue: Polling continues after completion

**Solution**: Check that document status is correctly set to "completed" or "failed"

### Issue: Frontend shows old data

**Solution**: Clear browser cache or hard refresh (Cmd+Shift+R / Ctrl+Shift+R)

## Next Steps

1. Start Celery worker if not running
2. Test with various PDF files
3. Monitor backend logs for any errors
4. Verify all polling intervals work correctly
5. Test error scenarios

## Files Modified

1. `ocr-frontend/lib/types.ts` - Updated TypeScript types
2. `ocr-frontend/lib/api.ts` - Added new API methods
3. `ocr-frontend/components/DocumentUpload.tsx` - Handle async upload
4. `ocr-frontend/components/DocumentList.tsx` - Auto-refresh with polling
5. `ocr-frontend/components/DocumentViewer.tsx` - Progress polling
6. `ocr-frontend/components/ProcessingProgress.tsx` - NEW component
7. `ocr-frontend/app/documents/[id]/page.tsx` - Uses updated DocumentViewer

## Summary

The frontend is now fully integrated with the Celery-based asynchronous processing system. Users get immediate feedback on uploads, can see real-time progress updates, and have a smooth experience throughout the document processing lifecycle.
