from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, Response
from app.services.excel_service import ExcelService
from app.services.memo_service import MemoService
from app.services.audit_log_service import AuditLogService
from app.models.schemas import UnderwritingAnalysis
from app.dependencies import get_excel_service, get_memo_service, get_audit_log_service
from typing import Dict, Any
import io
import urllib.parse

router = APIRouter()

@router.post("/export/excel")
async def export_excel(
    analysis_data: UnderwritingAnalysis,
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Generates and returns an Excel file with a side-by-side financial analysis.
    
    Side-by-Side View:
    - Column A: T12 (Historical) - Actual trailing 12-month data
    - Column B: F12 (Pro Forma) - Projected future-12-month data
    
    Includes:
    - Revenue analysis with vacancy impact
    - Expense breakdown by category
    - NOI and Cap Rate calculations
    - Professional formatting and styling
    """
    pro_forma_entries = excel_service.generate_side_by_side_view(analysis_data)
    excel_data = await excel_service.create_side_by_side_excel(pro_forma_entries, analysis_data)

    filename = "financial_analysis.xlsx"
    encoded_filename = urllib.parse.quote(filename)
    return StreamingResponse(
        iter([excel_data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}"
        }
    )

@router.post("/export/om-proforma")
async def export_om_proforma(
    analysis_data: UnderwritingAnalysis,
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Generates and returns an Excel file with the OM Proforma tables.
    """
    excel_data = await excel_service.create_om_proforma_excel(analysis_data)

    filename = "om_proforma.xlsx"
    encoded_filename = urllib.parse.quote(filename)
    return StreamingResponse(
        iter([excel_data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}"
        }
    )

@router.post("/export/rent-roll")
async def export_rent_roll(
    analysis_data: UnderwritingAnalysis,
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Generates and returns an Excel file with the detailed Rent Roll and Summary.
    """
    print(f"DEBUG: Export Rent Roll called. Config: {analysis_data.student_housing_config}")
    if analysis_data.student_housing_config and analysis_data.student_housing_config.unit_type_configs:
        for c in analysis_data.student_housing_config.unit_type_configs:
            print(f"DEBUG Config Item: {c.unit_type} -> {c.occupancy_type} / {c.unit_config_label}")
    excel_data = await excel_service.create_rent_roll_excel(analysis_data)

    filename = "rent_roll_detail.xlsx"
    encoded_filename = urllib.parse.quote(filename)
    return StreamingResponse(
        iter([excel_data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}"
        }
    )

@router.post("/export/rent-roll/preview")
async def preview_rent_roll(
    analysis_data: UnderwritingAnalysis,
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Returns preview data for the Rent Roll (columns + rows) in JSON format.
    Used for frontend grid display before downloading Excel.
    """
    preview_data = excel_service.get_rent_roll_preview_data(analysis_data)
    return preview_data

@router.post("/export/memo")
async def export_memo(
    analysis_data: UnderwritingAnalysis,
    memo_service: MemoService = Depends(get_memo_service),
):
    """
    Generates and returns an investment memo as PDF.
    
    Includes:
    - Executive Summary
    - Key Questions (Is there upside? What are risks? What's the strategy?)
    - SWOT Analysis
    - Investment Highlights
    - Risk Mitigation
    
    Uses LLM to generate sophisticated narrative or falls back to template.
    """
    pdf_content = memo_service.generate_investment_memo_pdf(analysis_data)
    
    filename = "investment_memo.pdf"
    encoded_filename = urllib.parse.quote(filename)
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}"
        }
    )

@router.post("/export/audit-trail")
async def export_audit_trail(
    analysis_data: UnderwritingAnalysis,
    audit_log_service: AuditLogService = Depends(get_audit_log_service),
):
    """
    Returns the comprehensive audit trail for the analysis.
    
    Tracks provenance for all fields:
    - Extraction source (OM, Rent Roll, P&L, etc.)
    - Calculation method
    - Confidence score
    - Timestamp
    
    Enables full explainability: "Where did the numbers come from?"
    """
    audit_trail = audit_log_service.generate_audit_trail(analysis_data)
    
    return {
        "document_id": analysis_data.document_id,
        "analysis_status": analysis_data.pass_fail_status,
        "audit_trail_entries": audit_trail,
        "total_entries": len(audit_trail)
    }

@router.get("/export/audit-trail/{document_id}")
async def get_audit_trail_by_id(
    document_id: str,
    audit_log_service: AuditLogService = Depends(get_audit_log_service),
):
    """
    Returns the audit trail for a given document ID.
    Fallback endpoint when full analysis object is not available.
    """
    audit_trail = audit_log_service.get_audit_trail(document_id)
    return {
        "document_id": document_id,
        "audit_trail": audit_trail,
    }