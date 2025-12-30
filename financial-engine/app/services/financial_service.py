from app.models.financial_analysis import UnderwritingAnalysis, DealParameters
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

    def calculate_pro_forma(self, deal_data: "DealData") -> Dict[str, float]:
        """
        Calculates the Pro Forma financials based on historical data and deal parameters.
        """
        # 1. Calculate Gross Potential Rent (GPR)
        gpr = sum(deal_data.rent_roll_summary.average_rent_per_unit_type.values()) * 12

        # 2. Calculate Effective Gross Income (EGI)
        vacancy_loss = gpr * deal_data.deal_parameters.vacancy_rate
        egi = gpr - vacancy_loss

        # 3. Calculate Pro Forma Net Operating Income (NOI)
        total_expenses = sum(expense.amount for expense in deal_data.normalized_expenses)
        pro_forma_noi = egi - total_expenses

        # 4. Calculate Cap Rate
        cap_rate = pro_forma_noi / deal_data.purchase_price if deal_data.purchase_price > 0 else 0

        return {
            "pro_forma_noi": pro_forma_noi,
            "cap_rate": cap_rate,
        }

    def get_audit_trail(self) -> List["AuditTrail"]:
        """
        Returns the audit trail for the financial calculations.
        """
        # This is a placeholder implementation. In a real scenario, you'd
        # have a more sophisticated way to track the audit trail.
        return [
            {"field": "Property Tax", "value": "$181,000", "source": "OM Page 4", "method": "Calculated based on purchase price"},
            {"field": "ProForma Revenue", "value": "$1,200,000", "source": "Rent Roll", "method": "Market Rent * Units * (1 - Vacancy Rate)"},
        ]