# Final Audit Plan

## Day 1: The "Financial Brain" (Normalization & Logic)

### I. The "Valiance Schema" (Pydantic Models)

*   [ ] **`schemas.py`**:
    *   [ ] Verify that all Pydantic models are correctly defined and enforce strict data validation.
    *   [ ] Cross-reference the `ExpenseCategory` enum with the client's standard chart of accounts.
    *   [ ] Confirm that all default values in `DealParameters` are correct and clearly documented.

### II. The "Semantic Mapper" (Normalization Service)

*   [ ] **`normalization_service.py`**:
    *   [ ] Verify that the `normalize_expenses` method correctly maps raw expense data to the standardized categories.
    *   [ ] Test the fallback `_simple_mapping` to ensure it provides a reasonable baseline.
    *   [ ] Review the LLM prompt to ensure it is clear, concise, and provides sufficient context.

### III. The Financial Calculation Engine

*   [ ] **`financial_service.py`**:
    *   [ ] Verify that the `check_deal_viability` method correctly implements the pass/fail gating logic.
    *   [ ] Manually recalculate the `calculate_pro_forma` and `calculate_historical` methods with sample data to ensure their arithmetic is correct.
    *   [ ] Confirm that the `calculate_pro_forma_with_expense_ratio` method correctly applies the 38% expense ratio standard.

### IV. The Ingestion Service

*   [ ] **`ingestion_service.py`**:
    *   [ ] Verify that the `ingest_pdf_document` method correctly extracts and normalizes all required data.
    *   [ ] Stress-test the `compare_income_sources` method with a variety of data to ensure it correctly identifies discrepancies.

## Day 2: The "Output Factory" (Excel & Memo)

### I. Excel Model Generator

*   [ ] **`excel_service.py`**:
    *   [ ] Verify that the `create_side_by_side_excel` method generates a high-quality Excel file with correct formulas.
    *   [ ] Manually inspect a generated Excel file to ensure it matches the client's "Side-by-Side" view.

### II. Investment Memo Generator

*   [ ] **`memo_service.py`**:
    *   [ ] Verify that the `generate_investment_memo` method produces a high-quality, LLM-powered investment memo.
    *   [ ] Review the LLM prompt to ensure it is clear, concise, and provides sufficient context.
    *   [ ] Test the fallback template to ensure it provides a reasonable baseline.

### III. The "Explainability" Layer (Audit Trail)

*   [ ] **`audit_log_service.py`**:
    *   [ ] Verify that the `generate_audit_trail` method creates a comprehensive and accurate audit trail.
    *   [ ] Manually inspect a generated audit trail to ensure it correctly tracks the provenance of all key data points.

## Day 3: Frontend Integration (The User Experience)

### I. The User Journey

*   [ ] **`upload/page.tsx`**:
    *   [ ] Verify that the upload page correctly handles file uploads and initiates the analysis process.
*   [ ] **`documents/[id]/page.tsx`**:
    *   [ ] Verify that the document detail page correctly displays the progress of the OCR process.
*   [ ] **`analysis/[id]/page.tsx`**:
    *   [ ] Verify that the analysis page correctly displays the underwriting dashboard and audit trail.

### II. The API Client

*   [ ] **`api.ts`**:
    *   [ ] Verify that the API client correctly interacts with both the `ocr-backend` and `financial-engine`.
    *   [ ] Confirm that the `streamDocumentProgress` method correctly handles Server-Sent Events.

### III. The Components

*   [ ] **`UnderwritingDashboard.tsx`**:
    *   [ ] Verify that the dashboard correctly displays all required data.
*   [ ] **`AuditTrailWidget.tsx`**:
    *   [ ] Verify that the audit trail widget is interactive and user-friendly.
*   [ ] **`ExportButtons.tsx`**:
    *   [ ] Verify that the export buttons correctly trigger the download of the Excel and memo files.