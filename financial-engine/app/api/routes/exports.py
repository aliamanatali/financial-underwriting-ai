from fastapi import APIRouter, Depends
from fastapi.responses import Response
from app.services.excel_service import ExcelService
from typing import Dict, Any

router = APIRouter()

def get_excel_service():
    return ExcelService()

@router.post("/export/excel", response_class=StreamingResponse)
async def export_excel(
    analysis_data: "UnderwritingAnalysis",
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Generates and returns an Excel file with a side-by-side financial analysis.
    """
    pro_forma_entries = excel_service.generate_side_by_side_view(
        {"pro_forma_noi": analysis_data.pro_forma_noi},
        analysis_data
    )
    excel_data = excel_service.create_side_by_side_excel(pro_forma_entries)

    return StreamingResponse(
        iter([excel_data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=financial_report.xlsx"}
    )