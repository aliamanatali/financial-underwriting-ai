# Risk Analysis & Quality Assurance Report

## I. Hardcoded Values & "Magic Numbers"

This section will document any hardcoded values, "magic numbers," or other inflexible implementations that could lead to maintenance issues or unexpected behavior.

*   **`financial_service.py`**: The `check_deal_viability` method contains several hardcoded thresholds (e.g., `15`, `80`, `5_000_000`, `1970`). These should be moved to a configuration file to allow for easier modification without changing the code.
*   **`ingestion_service.py`**: The `ingest_pdf_document` method has a hardcoded `max_wait_time` of `300` seconds. This should be configurable. The polling interval of `5` seconds is also hardcoded.
*   **`excel_service.py`**: The `create_side_by_side_excel` method has a hardcoded vacancy rate of `0.03` in a formula. This should be sourced from the `DealParameters` model.
*   **`DealParameters` in `schemas.py`**: The default values for `growth_rate`, `exit_cap_rate`, `vacancy_rate`, and `loan_amount` are hardcoded. While sensible defaults are necessary, these should be clearly documented as "Valiance Standard" assumptions.

## II. Potential Failure Points & Edge Cases

This section will identify any potential failure points, edge cases, or scenarios that could lead to a degradation in quality or a failure of the system.

*   **LLM Hallucination:** The system relies heavily on an LLM to extract and normalize data. While the use of Pydantic models provides a strong defense against invalid data formats, it does not prevent the LLM from "hallucinating" incorrect or nonsensical values. The system should include additional validation checks to mitigate this risk.
*   **OCR Errors:** The `ocr-backend` is a critical component of the system. Any errors in the OCR process will propagate through the entire system and lead to incorrect financial analysis. The system should include a mechanism for users to review and correct OCR errors.
*   **Asynchronous Timeouts:** The `ingestion_service.py` has a hardcoded timeout of 300 seconds for document processing. This may not be sufficient for very large or complex documents. The system should include a more flexible timeout mechanism, and the frontend should provide clear feedback to the user if a timeout occurs.

## III. Logical Inconsistencies & Broken Workflows

This section will document any logical inconsistencies, broken workflows, or other issues that could lead to a user-facing failure.

*   **Mismatched API Client:** The `api.ts` in the frontend is not correctly implemented to handle the two-backend architecture. It does not distinguish between the `ocr-backend` and the `financial-engine`, and it does not correctly implement the asynchronous polling required for the document processing workflow. This is a critical issue that will prevent the system from functioning as intended.
*   **Inefficient Export Workflow:** The `ExportButtons.tsx` component re-runs the entire analysis every time a user clicks an export button. This is highly inefficient and should be refactored to use the existing analysis data.
*   **Missing User Feedback:** The frontend does not provide sufficient feedback to the user during the document processing and analysis stages. The user should be kept informed of the system's progress at all times.