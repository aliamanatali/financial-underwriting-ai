from app.models.schemas import UnderwritingAnalysis, DealParameters
from typing import Dict, Any, List

class FinancialService:
    def check_deal_viability(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
        """
        Checks if a deal meets the predefined criteria.
        Uses DETERMINISTIC logic, not LLM-based guessing.
        
        Gating Criteria (All must pass):
        1. Unit Count: Must be between min_unit_count and max_unit_count
        2. Loan Amount: Must be >= $5,000,000
        3. Property Age: If < max_build_year (1970), must be renovated
        """
        reasons = []
        status = "PASS"
        
        # Get deal parameters (should be set by caller)
        params = analysis.deal_parameters
        if not params:
            # Use defaults if not set
            params = DealParameters()
        
        # Gate 1: Unit Count Check (DETERMINISTIC)
        unit_count = analysis.property_meta.total_units
        if unit_count < params.min_unit_count:
            status = "FAIL"
            reasons.append(
                f"Unit count FAIL: {unit_count} units is below minimum of {params.min_unit_count} units."
            )
        elif unit_count > params.max_unit_count:
            status = "FAIL"
            reasons.append(
                f"Unit count FAIL: {unit_count} units exceeds maximum of {params.max_unit_count} units."
            )
        
        # Gate 2: Loan Amount Check (DETERMINISTIC)
        loan_amount = params.loan_amount
        if loan_amount < 5_000_000:
            status = "FAIL"
            reasons.append(
                f"Loan amount FAIL: ${loan_amount:,.0f} is below minimum of $5,000,000."
            )
        
        # Gate 3: Property Vintage Check (DETERMINISTIC)
        year_built = analysis.property_meta.year_built
        is_renovated = analysis.property_meta.is_renovated
        
        if year_built < params.max_build_year and not is_renovated:
            status = "FAIL"
            reasons.append(
                f"Property vintage FAIL: Built in {year_built} (before {params.max_build_year}) and not renovated."
            )
        
        return {"status": status, "reasons": reasons}

    def calculate_pro_forma(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
        """
        Calculates the Pro Forma financials based on historical data and deal parameters.
        
        Formula:
        1. Gross Potential Rent (GPR) = Sum of Market Rents * 12 months
        2. Effective Gross Income (EGI) = GPR * (1 - Vacancy Rate)
        3. Total Operating Expenses = Sum of normalized expenses (historical T12)
        4. Pro Forma NOI = EGI - (Total Expenses OR Expenses as % of EGI)
        5. Cap Rate = NOI / Purchase Price
        """
        if not analysis.deal_parameters:
            raise ValueError("Deal parameters required for pro forma calculation")
        
        # 1. Calculate Gross Potential Rent (using MARKET rents, not current)
        gpr = sum(
            item.market_rent * 12 for item in analysis.rent_roll
        )
        
        # 2. Calculate Effective Gross Income (apply vacancy loss)
        vacancy_loss = gpr * analysis.deal_parameters.vacancy_rate
        egi = gpr - vacancy_loss
        
        # 3. Calculate Historical Net Operating Income (for reference)
        total_historical_expenses = sum(
            expense.amount for expense in analysis.historical_expenses
        )
        historical_noi = (sum(item.current_rent * 12 for item in analysis.rent_roll)) - total_historical_expenses
        
        # 4. Pro Forma NOI using 38% expense ratio (Valiance Standard)
        pro_forma_expenses = egi * 0.38
        pro_forma_noi = egi - pro_forma_expenses
        analysis.pro_forma_expenses = pro_forma_expenses
        
        # 5. Calculate Cap Rate
        exit_cap_rate = analysis.deal_parameters.exit_cap_rate
        if not exit_cap_rate:
            exit_cap_rate = 0.06
        cap_rate = pro_forma_noi / analysis.property_meta.purchase_price if analysis.property_meta.purchase_price and analysis.property_meta.purchase_price > 0 else 0
        
        return {
            "historical_noi": historical_noi,
            "gross_potential_rent": gpr,
            "effective_gross_income": egi,
            "pro_forma_expenses": pro_forma_expenses,
            "pro_forma_noi": pro_forma_noi,
            "cap_rate": cap_rate,
        }

    def calculate_pro_forma_with_expense_ratio(self, analysis: UnderwritingAnalysis, expense_ratio: float = 0.38) -> Dict[str, float]:
        """
        Calculates Pro Forma with an expense ratio override (Valiance Standard: 38%).
        """
        # 1. Calculate Gross Potential Rent (GPR)
        gpr = sum(item.market_rent * 12 for item in analysis.rent_roll)

        # 2. Calculate Effective Gross Income (EGI)
        vacancy_loss = gpr * analysis.deal_parameters.vacancy_rate
        egi = gpr - vacancy_loss

        # 3. Pro Forma Expenses using expense ratio
        pro_forma_expenses = egi * expense_ratio

        # 4. Calculate Pro Forma NOI
        pro_forma_noi = egi - pro_forma_expenses

        # 5. Calculate Cap Rate
        cap_rate = pro_forma_noi / analysis.property_meta.purchase_price if analysis.property_meta.purchase_price > 0 else 0

        return {
            "pro_forma_noi": pro_forma_noi,
            "pro_forma_expenses": pro_forma_expenses,
            "cap_rate": cap_rate,
        }

    def calculate_historical(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
        """
        Calculates the Historical financials based on actual data from T12.
        
        Formula:
        1. Historical Gross Income (HGI) = Sum of Current Rents * 12 months
        2. Historical NOI = HGI - Total Expenses (from historical_expenses)
        3. Historical Cap Rate = NOI / Purchase Price
        """
        # 1. Calculate Historical Gross Income
        hgi = sum(
            item.current_rent * 12 for item in analysis.rent_roll
        )
        
        # 2. Calculate Historical Net Operating Income
        total_expenses = sum(
            expense.amount for expense in analysis.historical_expenses
        ) if analysis.historical_expenses else 0
        analysis.historical_total_expenses = total_expenses
        historical_noi = hgi - total_expenses
        
        # 3. Calculate Historical Cap Rate
        historical_cap_rate = historical_noi / analysis.property_meta.purchase_price if analysis.property_meta.purchase_price > 0 else 0
        
        return {
            "gross_income": hgi,
            "total_expenses": total_expenses,
            "historical_noi": historical_noi,
            "historical_cap_rate": historical_cap_rate,
        }

    def get_audit_trail(self, analysis: UnderwritingAnalysis) -> List[Dict[str, Any]]:
        """
        Returns the audit trail for the financial analysis.
        This includes both ingestion and calculation logs.
        """
        # Return the audit trail from the analysis object
        # (It was populated during ingestion, we just pass it through)
        return analysis.audit_trail if analysis.audit_trail else []