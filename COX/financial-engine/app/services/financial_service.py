from app.models.schemas import UnderwritingAnalysis, DealParameters
from typing import Dict, Any, List

class FinancialService:
    def check_deal_viability(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Checks if a deal meets the predefined criteria.
        """
        reasons = []
        status = "PASS"

        if deal_data.get("unit_count", 0) < 15 or deal_data.get("unit_count", 0) > 80:
            status = "FAIL"
            reasons.append(f"Unit count of {deal_data.get('unit_count', 0)} is outside the acceptable range (15-80).")

        if deal_data.get("loan_amount", 0) < 5_000_000:
            status = "FAIL"
            reasons.append(f"Loan amount of ${deal_data.get('loan_amount', 0):,} is below the minimum of $5,000,000.")

        if deal_data.get("year_built", 0) < 1970 and not deal_data.get("is_renovated", False):
            status = "FAIL"
            reasons.append(f"Property built in {deal_data.get('year_built', 0)} and has not been renovated.")

        return {"status": status, "reasons": reasons}

    def calculate_pro_forma(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
        """
        Calculates the Pro Forma financials based on historical data and deal parameters.
        """
        # 1. Calculate Gross Potential Rent (GPR)
        gpr = sum(
            item.market_rent * 12 for item in analysis.rent_roll
        )

        # 2. Calculate Effective Gross Income (EGI)
        vacancy_loss = gpr * analysis.deal_parameters.vacancy_rate
        egi = gpr - vacancy_loss

        # 3. Calculate Pro Forma Net Operating Income (NOI)
        total_expenses = sum(expense.value for expense in analysis.historical_expenses)
        pro_forma_noi = egi - total_expenses

        # 4. Calculate Cap Rate
        cap_rate = pro_forma_noi / analysis.property_meta.purchase_price if analysis.property_meta.purchase_price > 0 else 0

        return {
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
        Calculates the Historical financials based on historical data.
        """
        # 1. Calculate Historical Gross Income (HGI)
        hgi = sum(
            item.current_rent * 12 for item in analysis.rent_roll
        )

        # 2. Calculate Historical Net Operating Income (NOI)
        total_expenses = sum(expense.value for expense in analysis.historical_expenses) if analysis.historical_expenses else 0
        historical_noi = hgi - total_expenses

        # 3. Calculate Historical Cap Rate
        historical_cap_rate = historical_noi / analysis.property_meta.purchase_price if analysis.property_meta.purchase_price > 0 else 0

        return {
            "historical_noi": historical_noi,
            "historical_cap_rate": historical_cap_rate,
        }

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """
        Returns the audit trail for the financial calculations.
        """
        # This is a placeholder implementation. In a real scenario, you'd
        # have a more sophisticated way to track the audit trail.
        return [
            {"field": "Property Tax", "value": "$181,000", "source": "OM Page 4", "method": "Calculated based on purchase price"},
            {"field": "ProForma Revenue", "value": "$1,200,000", "source": "Rent Roll", "method": "Market Rent * Units * (1 - Vacancy Rate)"},
        ]