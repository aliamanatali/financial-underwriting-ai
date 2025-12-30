# OCR Backend - Gemini Document Extraction API

A Python FastAPI backend for high-fidelity PDF text extraction using Google Gemini API. This project replicates the document extraction functionality from the MTD project, focusing on zero-hallucination document digitization.

## Features

- **Gemini-Powered Extraction**: Uses Google Gemini 1.5 Pro for accurate PDF text extraction
- **Zero Hallucination**: DocuMind prompt approach ensures faithful document digitization
- **Flexible Storage**: Supports both local file storage and MinIO object storage
- **Optional MongoDB**: Store document metadata in MongoDB or use in-memory storage
- **Async Processing**: Background task processing for document extraction
- **RESTful API**: Clean, well-documented API endpoints
- **Type Safety**: Full type hints and Pydantic validation

## Project Structure

```
ocr-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration and environment variables
│   ├── models/
│   │   ├── __init__.py
│   │   └── document.py            # Pydantic models for documents
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_service.py      # Gemini API integration
│   │   ├── storage_service.py     # File storage (local or MinIO)
│   │   └── document_service.py    # Document processing orchestration
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py          # Health check endpoint
│   │       └── documents.py       # Document upload and extraction endpoints
│   └── utils/
│       ├── __init__.py
│       └── logger.py              # Logging configuration
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

## Prerequisites

- Python 3.10 or higher
- Google Gemini API key ([Get one here](https://ai.google.dev/))
- (Optional) MongoDB for metadata storage
- (Optional) MinIO for object storage

## Installation

1. **Clone or navigate to the project directory**:

   ```bash
   cd ocr-backend
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your Gemini API key:

   ```bash
   GEMINI_API_KEY=your_actual_api_key_here
   ```

## Configuration

### Required Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key (required)

### Optional Environment Variables

#### Storage Options

- `UPLOAD_DIR`: Local storage directory (default: `./uploads`)
- `MINIO_ENDPOINT`: MinIO server endpoint (e.g., `localhost:9000`)
- `MINIO_ACCESS_KEY`: MinIO access key
- `MINIO_SECRET_KEY`: MinIO secret key
- `MINIO_BUCKET`: MinIO bucket name (default: `documents`)

#### Database Options

- `MONGODB_URI`: MongoDB connection string (e.g., `mongodb://localhost:27017/ocr_db`)
- `MONGODB_DATABASE`: Database name (default: `ocr_db`)

#### Server Options

- `PORT`: Server port (default: `8000`)
- `HOST`: Server host (default: `0.0.0.0`)
- `DEBUG`: Enable debug mode (default: `false`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

#### Gemini Options

- `GEMINI_MODEL`: Model to use (default: `gemini-3-pro-preview`)
- `GEMINI_TEMPERATURE`: Temperature for extraction (default: `0.0`)
- `GEMINI_MAX_OUTPUT_TOKENS`: Max output tokens (default: `65536`)

## Running the Server

### Development Mode

```bash
python -m app.main
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:

- **Interactive API docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc

## API Endpoints

### Health Check

**GET** `/health`

Check service health and availability.

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "healthy",
  "timestamp": "2024-12-24T07:00:00.000Z",
  "version": "1.0.0",
  "services": {
    "gemini": true,
    "mongodb": false,
    "minio": false,
    "local_storage": true
  }
}
```

### Upload Document

**POST** `/api/documents/upload`

Upload a PDF document for text extraction.

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/path/to/document.pdf"
```

Response:

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "status": "pending",
  "message": "Document uploaded successfully. Processing will begin shortly."
}
```

### Get Document Details

**GET** `/api/documents/{document_id}`

Retrieve document details and extraction results.

```bash
curl http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000
```

Response:

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "status": "completed",
  "extracted_text": "--- PAGE 1 ---\n[Full extracted text...]",
  "metadata": {
    "page_count": 10,
    "has_handwriting": false,
    "quality": "high",
    "file_size": 245678,
    "mime_type": "application/pdf",
    "extraction_notes": null
  },
  "created_at": "2024-12-24T07:00:00.000Z",
  "updated_at": "2024-12-24T07:00:30.000Z",
  "error_message": null
}
```

### Get Extracted Text

**GET** `/api/documents/{document_id}/text`

Get only the extracted text content.

```bash
curl http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000/text
```

Response:

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "--- PAGE 1 ---\n[Full extracted text...]",
  "page_count": 10,
  "confidence": "high"
}
```

### Delete Document

**DELETE** `/api/documents/{document_id}`

Delete a document and its associated file.

```bash
curl -X DELETE http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000
```

Response:

```json
{
  "success": true,
  "message": "Document 550e8400-e29b-41d4-a716-446655440000 deleted successfully"
}
```

### Reprocess Document

**POST** `/api/documents/{document_id}/reprocess`

Reprocess a document (re-extract text).

```bash
curl -X POST http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000/reprocess
```

Response:

```json
{
  "success": true,
  "message": "Document 550e8400-e29b-41d4-a716-446655440000 reprocessing initiated"
}
```

## Document Extraction Approach

This project uses the **DocuMind** prompt approach for zero-hallucination document extraction:

### Core Principles

1. **NO HALLUCINATION**: Never invent or infer information not present in the document
2. **NO SUMMARIZATION**: Extract full content, not summaries
3. **PRESERVE FIDELITY**: Maintain original spelling, punctuation, and formatting

### Output Format

The extracted text follows this structure:

```
--- PAGE 1 ---
[Exact text content from page 1]

[Handwritten: signature]
[Image: company logo]
[Table: financial data in markdown]

[Page Confidence: High | Justification: Clear text, no issues]

--- PAGE 2 ---
[Exact text content from page 2]
...

=== DOCUMENT EXTRACTION SUMMARY ===
TOTAL PAGES: 10
OVERALL DOCUMENT CONFIDENCE: High
DOCUMENT QUALITY: High
HANDWRITING DETECTED: No
EXTRACTION NOTES: None
```

### Special Annotations

- `[Handwritten: text]` - Handwritten content
- `[Stamp: "text"]` - Stamps or seals
- `[Watermark: "text"]` - Watermarks
- `[Image: description]` - Images/logos
- `[Table: ...]` - Tables (converted to markdown)
- `[Redaction box present]` - Redacted content
- `[Uncertain: possible text]` - Unclear content
- `[Illegible: X words]` - Unreadable text

## Storage Options

### Local Storage (Default)

By default, files are stored locally in the `./uploads` directory. No additional configuration needed.

### MinIO Object Storage

To use MinIO for object storage:

1. Install and run MinIO:

   ```bash
   docker run -p 9000:9000 -p 9001:9001 \
     -e MINIO_ROOT_USER=minioadmin \
     -e MINIO_ROOT_PASSWORD=minioadmin \
     minio/minio server /data --console-address ":9001"
   ```

2. Configure environment variables:
   ```bash
   MINIO_ENDPOINT=localhost:9000
   MINIO_ACCESS_KEY=minioadmin
   MINIO_SECRET_KEY=minioadmin
   MINIO_BUCKET=documents
   ```

## Database Options

### In-Memory Storage (Default)

By default, document metadata is stored in memory. This is suitable for development and testing.

### MongoDB

To use MongoDB for persistent metadata storage:

1. Install and run MongoDB:

   ```bash
   docker run -d -p 27017:27017 --name mongodb mongo:latest
   ```

2. Configure environment variable:
   ```bash
   MONGODB_URI=mongodb://localhost:27017/ocr_db
   ```

## Error Handling

The API provides detailed error messages:

- **400 Bad Request**: Invalid file type or empty file
- **404 Not Found**: Document not found
- **500 Internal Server Error**: Processing errors

Example error response:

```json
{
  "detail": "Only PDF files are supported"
}
```

## Logging

Logs are written to stdout with configurable log levels:

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

Example log output:

```
2024-12-24 07:00:00 - ocr-backend - INFO - Starting OCR Backend API
2024-12-24 07:00:00 - ocr-backend - INFO - Gemini Model: gemini-3-pro-preview
2024-12-24 07:00:00 - ocr-backend - INFO - Storage: Local
2024-12-24 07:00:30 - ocr-backend - INFO - Document uploaded: 550e8400-e29b-41d4-a716-446655440000
```

## Performance Considerations

- **Token Usage**: Gemini 1.5 Pro has a 1M token context window
- **Processing Time**: Extraction time depends on document size (typically 10-30 seconds per document)
- **Concurrent Requests**: Use multiple workers for production deployments
- **Rate Limits**: Be aware of Gemini API rate limits

## Troubleshooting

### Common Issues

1. **"GEMINI_API_KEY environment variable is required"**

   - Ensure you've set `GEMINI_API_KEY` in your `.env` file

2. **"Only PDF files are supported"**

   - Only PDF files can be uploaded for extraction

3. **"Document has not been processed yet"**

   - Wait for background processing to complete (check status with GET endpoint)

4. **MinIO connection errors**

   - Verify MinIO is running and credentials are correct
   - Check `MINIO_ENDPOINT` format (should be `host:port`)

5. **MongoDB connection errors**
   - Verify MongoDB is running
   - Check `MONGODB_URI` format

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests (when implemented)
pytest
```

### Testing with curl

#### Test Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "timestamp": "2024-12-24T08:00:00.000Z",
  "version": "1.0.0",
  "services": {
    "gemini": true,
    "mongodb": false,
    "minio": false,
    "local_storage": true
  }
}
```

#### Test Document Upload

```bash
# Upload a PDF document
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/path/to/sample.pdf" \
  -w "\n"
```

Expected response:

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "sample.pdf",
  "status": "pending",
  "message": "Document uploaded successfully. Processing will begin shortly."
}
```

#### Test Get Document Details

```bash
# Replace {document_id} with actual ID from upload response
curl http://localhost:8000/api/documents/{document_id} | jq
```

Expected response (after processing):

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "sample.pdf",
  "status": "completed",
  "extracted_text": "--- PAGE 1 ---\n...",
  "metadata": {
    "page_count": 10,
    "has_handwriting": false,
    "quality": "high",
    "file_size": 245678,
    "mime_type": "application/pdf"
  },
  "created_at": "2024-12-24T08:00:00.000Z",
  "updated_at": "2024-12-24T08:00:30.000Z"
}
```

#### Test Get Extracted Text Only

```bash
curl http://localhost:8000/api/documents/{document_id}/text | jq
```

Expected response:

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "--- PAGE 1 ---\n...",
  "page_count": 10,
  "confidence": "high"
}
```

#### Test List All Documents

```bash
curl http://localhost:8000/api/documents | jq
```

Expected response:

```json
[
  {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "sample.pdf",
    "status": "completed",
    "created_at": "2024-12-24T08:00:00.000Z"
  }
]
```

#### Test Delete Document

```bash
curl -X DELETE http://localhost:8000/api/documents/{document_id}
```

Expected response:

```json
{
  "success": true,
  "message": "Document {document_id} deleted successfully"
}
```

#### Test Reprocess Document

```bash
curl -X POST http://localhost:8000/api/documents/{document_id}/reprocess
```

Expected response:

```json
{
  "success": true,
  "message": "Document {document_id} reprocessing initiated"
}
```

### Integration Testing

#### Full Workflow Test

```bash
#!/bin/bash
# Save as test-workflow.sh

echo "1. Testing health endpoint..."
curl -s http://localhost:8000/health | jq .status

echo -e "\n2. Uploading document..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/documents/upload \
  -F "file=@sample.pdf")
DOC_ID=$(echo $RESPONSE | jq -r .document_id)
echo "Document ID: $DOC_ID"

echo -e "\n3. Waiting for processing (30 seconds)..."
sleep 30

echo -e "\n4. Fetching document details..."
curl -s http://localhost:8000/api/documents/$DOC_ID | jq .status

echo -e "\n5. Getting extracted text..."
curl -s http://localhost:8000/api/documents/$DOC_ID/text | jq .page_count

echo -e "\n6. Deleting document..."
curl -s -X DELETE http://localhost:8000/api/documents/$DOC_ID | jq .success

echo -e "\nTest complete!"
```

Make it executable and run:

```bash
chmod +x test-workflow.sh
./test-workflow.sh
```

### Code Style

This project follows Python best practices:

- Type hints throughout
- Async/await for I/O operations
- Pydantic for data validation
- Comprehensive docstrings

## License

This project is provided as-is for document extraction purposes.

## Acknowledgments

Based on the MTD (Motion to Dismiss) project's document extraction implementation, adapted for Python FastAPI.

## Support

For issues or questions:

1. Check the API documentation at `/docs`
2. Review the logs for error details
3. Verify environment configuration
4. Ensure Gemini API key is valid and has sufficient quota
