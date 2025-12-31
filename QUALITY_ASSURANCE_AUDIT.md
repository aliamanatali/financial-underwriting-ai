# Quality Assurance Audit Plan

## I. Financial Engine Audit

### A. API Routes

1.  **`analysis.py`**:
    *   Verify that the `perform_analysis` endpoint correctly orchestrates the ingestion, viability check, and financial calculation services.
    *   Confirm that all exceptions are caught and handled gracefully.
2.  **`exports.py`**:
    *   Verify that the `export_excel` and `export_memo` endpoints correctly generate and return the required files.
    *   Confirm that the `get_audit_trail` endpoint correctly retrieves and returns the audit trail.
3.  **`ingest.py`**:
    *   Verify that the `ingest_and_analyze_document` endpoint correctly handles file uploads and initiates the analysis process.

### B. Services

1.  **`audit_log_service.py`**:
    *   Verify that the `generate_audit_trail` method creates a comprehensive and accurate audit trail.
2.  **`excel_service.py`**:
    *   Verify that the `create_side_by_side_excel` method generates a high-quality Excel file with correct formulas.
3.  **`financial_service.py`**:
    *   Verify that the `check_deal_viability`, `calculate_pro_forma`, and `calculate_historical` methods are all logically sound and arithmetically correct.
4.  **`ingestion_service.py`**:
    *   Verify that the `ingest_pdf_document` method correctly extracts and normalizes all required data.
5.  **`memo_service.py`**:
    *   Verify that the `generate_investment_memo` method produces a high-quality, LLM-powered investment memo.
6.  **`normalization_service.py`**:
    *   Verify that the `normalize_expenses` method correctly maps raw expense data to the standardized categories.

### C. Models

1.  **`schemas.py`**:
    *   Verify that all Pydantic models are correctly defined and enforce strict data validation.

## II. OCR Backend Audit

### A. API Routes

1.  **`documents.py`**:
    *   Verify that all endpoints for document upload, status checking, and text retrieval are fully functional.

### B. Services

1.  **`document_service.py`**:
    *   Verify that the `process_document` method correctly orchestrates the document processing pipeline.
2.  **`pdf_chunking_service.py`**:
    *   Verify that the `split_pdf` method correctly chunks large PDF files.

### C. Tasks

1.  **`document_tasks.py`**:
    *   Verify that the Celery tasks for document processing are robust and handle errors gracefully.

## III. Frontend Audit

### A. Pages

1.  **`upload/page.tsx`**:
    *   Verify that the upload page correctly handles file uploads and initiates the analysis process.
2.  **`analysis/[id]/page.tsx`**:
    *   Verify that the analysis page correctly displays the underwriting dashboard and audit trail.

### B. Components

1.  **`UnderwritingDashboard.tsx`**:
    *   Verify that the dashboard correctly displays all required data.
2.  **`AuditTrailWidget.tsx`**:
    *   Verify that the audit trail widget is interactive and user-friendly.
3.  **`ExportButtons.tsx`**:
    *   Verify that the export buttons correctly trigger the download of the Excel and memo files.

### C. Lib

1.  **`api.ts`**:
    *   Verify that the API client correctly interacts with both the `ocr-backend` and `financial-engine`.
