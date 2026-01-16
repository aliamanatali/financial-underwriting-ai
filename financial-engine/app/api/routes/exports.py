from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, Response
from app.services.excel_service import ExcelService
from app.services.memo_service import MemoService
from app.services.audit_log_service import AuditLogService
from app.models.schemas import UnderwritingAnalysis
from app.dependencies import get_excel_service, get_memo_service, get_audit_log_service
from typing import Dict, Any
import io

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
    excel_data = await excel_service.create_side_by_side_excel(pro_forma_entries)

    return StreamingResponse(
        iter([excel_data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=financial_analysis.xlsx"}
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

    return StreamingResponse(
        iter([excel_data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=om_proforma.xlsx"}
    )

@router.post("/export/memo")
async def export_memo(
    analysis_data: UnderwritingAnalysis,
    memo_service: MemoService = Depends(get_memo_service),
):
    """
    Generates and returns an investment memo as markdown/HTML.
    
    Includes:
    - Executive Summary
    - Key Questions (Is there upside? What are risks? What's the strategy?)
    - SWOT Analysis
    - Investment Highlights
    - Risk Mitigation
    
    Uses LLM to generate sophisticated narrative or falls back to template.
    """
    # Use pre-generated memo if available to save time
    if analysis_data.investment_memo:
        memo_content = analysis_data.investment_memo
    else:
        memo_content = memo_service.generate_investment_memo(analysis_data)
    
    # Return as markdown text with proper encoding
    return Response(
        content=memo_content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=investment_memo.md"}
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