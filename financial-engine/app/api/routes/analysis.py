from fastapi import APIRouter, Depends, HTTPException
from app.services.normalization_service import NormalizationService
from app.services.financial_service import FinancialService
from app.services.excel_service import ExcelService
from app.models.financial_analysis import UnderwritingAnalysis, DealData, DealDataInput, DealParameters, RentRollSummary
from typing import Dict, Any
from app.dependencies import get_normalization_service, get_financial_service, get_excel_service

router = APIRouter()

@router.post("/analysis", response_model=UnderwritingAnalysis)
async def perform_analysis(
    data: Dict[str, Any],
    normalization_service: NormalizationService = Depends(get_normalization_service),
    financial_service: FinancialService = Depends(get_financial_service),
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Performs a full underwriting analysis on a given deal.
    """
    # 1. Check deal viability
    viability_check = financial_service.check_deal_viability(data)
    if viability_check["status"] == "FAIL":
        raise HTTPException(status_code=400, detail=viability_check["reasons"])

    # 2. Normalize expenses
    normalized_expenses = normalization_service.normalize_expenses(data.get("raw_expenses", []))

    # 3. Calculate Pro Forma
    deal_data = DealData(
        purchase_price=data.get("purchase_price", 0),
        closing_costs=data.get("closing_costs", 0),
        holding_period_years=data.get("holding_period_years", 5),
        sell_cap_rate=data.get("sell_cap_rate", 0.05),
        historical_noi=data.get("historical_noi", 0),
        rent_roll_summary=RentRollSummary(**data.get("rent_roll_summary", {})),
        normalized_expenses=normalized_expenses,
        deal_parameters=DealParameters(**data.get("deal_parameters", {})),
    )
    pro_forma_data = financial_service.calculate_pro_forma(deal_data)

    # 4. Construct the initial analysis result (without pro_forma_entries)
    analysis_result = UnderwritingAnalysis(
        document_id=data.get("document_id"),
        pass_fail_status="PASS",
        reasons=[],
        normalized_expenses=normalized_expenses,
        rent_roll_summary=data.get("rent_roll_summary"),
        pro_forma_noi=pro_forma_data["pro_forma_noi"],
        cap_rate=pro_forma_data["cap_rate"],
        pro_forma_entries=[],
        audit_trail=[]
    )
    
    # 5. Generate the side-by-side view and update the analysis result
    # The create_side_by_side_excel method expects the pro_forma_entries list directly.
    # The list is already available in the analysis_result object, which was created with an empty list.
    excel_service.create_side_by_side_excel(analysis_result.pro_forma_entries)
    analysis_result.audit_trail = financial_service.get_audit_trail()

    return analysis_result

@router.post("/analysis_v2", response_model=UnderwritingAnalysis)
async def perform_analysis_v2(
    deal_data: DealDataInput,
    normalization_service: NormalizationService = Depends(get_normalization_service),
    financial_service: FinancialService = Depends(get_financial_service),
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Performs a full underwriting analysis using the new DealDataInput model.
    """
    # The new DealDataInput model is already validated by Pydantic.
    # We can now create the internal DealData model from it.
    internal_deal_data = DealData(
        purchase_price=deal_data.property_meta.purchase_price,
        closing_costs=deal_data.closing_costs,
        holding_period_years=deal_data.holding_period_years,
        sell_cap_rate=deal_data.sell_cap_rate,
        historical_noi=deal_data.historical_noi,
        rent_roll_summary=deal_data.rent_roll_summary,
        normalized_expenses=deal_data.normalized_expenses,
        deal_parameters=deal_data.deal_parameters,
    )

    pro_forma_data = financial_service.calculate_pro_forma(internal_deal_data)

    analysis_result = UnderwritingAnalysis(
        document_id="v2_test", # This can be updated to come from the input
        pass_fail_status="PASS",
        reasons=[],
        normalized_expenses=deal_data.normalized_expenses,
        rent_roll_summary=deal_data.rent_roll_summary,
        pro_forma_noi=pro_forma_data["pro_forma_noi"],
        cap_rate=pro_forma_data["cap_rate"],
        pro_forma_entries=[],
        audit_trail=[]
    )
    
    excel_service.create_side_by_side_excel(analysis_result.pro_forma_entries)
    analysis_result.audit_trail = financial_service.get_audit_trail()

    return analysis_result