from app.models.schemas import UnderwritingAnalysis, DealParameters, ProFormaExpenseItem
from typing import Dict, Any, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from app.services.audit_log_service import AuditLogService

class FinancialService:
    def __init__(self, audit_log_service: AuditLogService):
        self.audit_log_service = audit_log_service
    def check_deal_viability(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
        reasons = []
        status = "PASS"
        params = analysis.deal_parameters or DealParameters()
        
        unit_count = analysis.property_meta.total_units
        if not (params.min_unit_count <= unit_count <= params.max_unit_count):
            status = "FAIL"
            reasons.append(f"Unit count FAIL: {unit_count} units is outside the range of {params.min_unit_count}-{params.max_unit_count} units.")
        
        loan_amount = analysis.property_meta.current_loan_balance or params.loan_amount
        if loan_amount < 5_000_000:
            status = "FAIL"
            reasons.append(f"Loan amount FAIL: ${loan_amount:,.0f} is below minimum of $5,000,000.")
        
        year_built = analysis.property_meta.year_built
        if year_built < params.max_build_year and not analysis.property_meta.is_renovated:
            status = "FAIL"
            reasons.append(f"Property vintage FAIL: Built in {year_built} (before {params.max_build_year}) and not renovated.")
        
        return {"status": status, "reasons": reasons}

    def calculate_pro_forma(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
        if not analysis.deal_parameters:
            raise ValueError("Deal parameters required for pro forma calculation")
        
        self.audit_log_service.add_log(analysis, "Pro Forma Start", "Initiating pro forma calculation.", "System", "Orchestration")
        
        gpr = sum(item.market_rent * 12 for item in analysis.rent_roll)
        self.audit_log_service.add_log(analysis, "Pro Forma GPR", f"${gpr:,.2f}", "Rent Roll", "Sum of Market Rents")

        vacancy_loss = gpr * analysis.deal_parameters.vacancy_rate
        egi = gpr - vacancy_loss
        self.audit_log_service.add_log(analysis, "Pro Forma EGI", f"${egi:,.2f}", "Valiance Logic", f"GPR minus {analysis.deal_parameters.vacancy_rate:.1%} Vacancy")

        total_historical_expenses = sum(expense.amount for expense in analysis.historical_expenses)
        historical_noi = sum(item.current_rent * 12 for item in analysis.rent_roll) - total_historical_expenses
        
        pro_forma_expenses_list = self._calculate_pro_forma_expenses_breakdown(analysis, egi)
        pro_forma_expenses = sum(item.amount for item in pro_forma_expenses_list)
        pro_forma_noi = egi - pro_forma_expenses
        analysis.pro_forma_expenses = pro_forma_expenses
        analysis.pro_forma_expenses_detailed = pro_forma_expenses_list
        
        purchase_price = analysis.property_meta.purchase_price or 0
        cap_rate = pro_forma_noi / purchase_price if purchase_price > 0 else 0
        analysis.cap_rate = cap_rate
        analysis.exit_cap_rate = analysis.deal_parameters.exit_cap_rate

        return {
            "historical_noi": historical_noi,
            "gross_potential_rent": gpr,
            "effective_gross_income": egi,
            "pro_forma_expenses": pro_forma_expenses,
            "pro_forma_noi": pro_forma_noi,
            "cap_rate": cap_rate,
            "exit_cap_rate": analysis.deal_parameters.exit_cap_rate,
        }

    def _calculate_pro_forma_expenses_breakdown(self, analysis: UnderwritingAnalysis, egi: float) -> List[ProFormaExpenseItem]:
        expense_breakdown: List[ProFormaExpenseItem] = []
        total_expense_budget = egi * 0.38
        self.audit_log_service.add_log(analysis, "Target Expense Budget", f"${total_expense_budget:,.0f}", "Valiance Logic", "38% of EGI Rule")

        purchase_price = analysis.property_meta.purchase_price or 0
        if purchase_price > 0:
            estimated_tax = purchase_price * 0.0125
            tax_explanation = f"Calculated Property Tax based on purchase price of ${purchase_price:,.2f} at 1.25%."
        else:
            estimated_tax = total_expense_budget * 0.30
            tax_explanation = "Purchase price not available. Allocated 30% of expense budget to Property Tax."
        
        expense_breakdown.append(ProFormaExpenseItem(name="Property Tax", amount=estimated_tax))
        self.audit_log_service.add_log(analysis, "Pro Forma Expense: Property Tax", tax_explanation, "Valiance Logic", "Calculated based on purchase price or expense budget")

        remaining_budget = total_expense_budget - estimated_tax
        expense_allocations = {
            "Insurance": 0.15, "Utilities": 0.20, "Management Fee": 0.10,
            "Repairs & Maintenance": 0.15, "General & Administrative": 0.05, "Landscaping": 0.05
        }

        for name, percentage in expense_allocations.items():
            amount = remaining_budget * percentage
            expense_breakdown.append(ProFormaExpenseItem(name=name, amount=amount))
            self.audit_log_service.add_log(analysis, f"Pro Forma Expense: {name}", f"Allocated {percentage:.0%} of remaining budget: ${amount:,.2f}", "Valiance Logic", "Allocation of remaining budget")
            
        return expense_breakdown

    def calculate_pro_forma_with_expense_ratio(self, analysis: UnderwritingAnalysis, expense_ratio: float = 0.38) -> Dict[str, float]:
        gpr = sum(item.market_rent * 12 for item in analysis.rent_roll)
        vacancy_loss = gpr * analysis.deal_parameters.vacancy_rate
        egi = gpr - vacancy_loss
        pro_forma_expenses = egi * expense_ratio
        pro_forma_noi = egi - pro_forma_expenses
        purchase_price = analysis.property_meta.purchase_price or 0
        cap_rate = pro_forma_noi / purchase_price if purchase_price > 0 else 0

        return {
            "pro_forma_noi": pro_forma_noi,
            "pro_forma_expenses": pro_forma_expenses,
            "cap_rate": cap_rate,
            "exit_cap_rate": analysis.deal_parameters.exit_cap_rate,
        }

    def calculate_historical(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
        hgi = sum(item.current_rent * 12 for item in analysis.rent_roll)
        total_expenses = sum(expense.amount for expense in analysis.historical_expenses) if analysis.historical_expenses else 0
        analysis.historical_total_expenses = total_expenses
        historical_noi = hgi - total_expenses
        purchase_price = analysis.property_meta.purchase_price or 0
        historical_cap_rate = historical_noi / purchase_price if purchase_price > 0 else 0
        
        return {
            "gross_income": hgi,
            "total_expenses": total_expenses,
            "historical_noi": historical_noi,
            "historical_cap_rate": historical_cap_rate,
        }

    def get_audit_trail(self, analysis: UnderwritingAnalysis) -> List[Dict[str, Any]]:
        return analysis.audit_trail

# from app.models.schemas import UnderwritingAnalysis, DealParameters, ProFormaExpenseItem
# from typing import Dict, Any, List
# from app.services.audit_log_service import AuditLogService

# class FinancialService:
#     def __init__(self, audit_log_service: AuditLogService):
#         self.audit_log_service = audit_log_service

#     def check_deal_viability(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
#         reasons = []
#         status = "PASS"
#         params = analysis.deal_parameters or DealParameters()
        
#         # 1. Units
#         units = analysis.property_meta.total_units or 0
#         if units < params.min_unit_count:
#             status = "FAIL"
#             reasons.append(f"Unit count FAIL: {units} < {params.min_unit_count}")
        
#         # 2. Loan
#         loan = params.loan_amount
#         if loan < 5_000_000:
#             status = "FAIL"
#             reasons.append(f"Loan amount FAIL: ${loan:,.0f} < $5M")
            
#         return {"status": status, "reasons": reasons}

#     def calculate_historical(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
#         # 1. Revenue
#         hgi = sum((i.current_rent or 0) * 12 for i in analysis.rent_roll)
        
#         # 2. Expenses (Summing Standardized Expenses)
#         total_expenses = sum(e.amount for e in analysis.historical_expenses)
        
#         # 3. NOI
#         noi = hgi - total_expenses
        
#         # 4. Save
#         analysis.historical_gross_income = hgi
#         analysis.historical_total_expenses = total_expenses
#         analysis.historical_noi = noi
        
#         price = analysis.property_meta.purchase_price or 0
#         analysis.historical_cap_rate = noi / price if price > 0 else 0
        
#         return {
#             "historical_noi": noi,
#             "historical_cap_rate": analysis.historical_cap_rate,
#             "total_expenses": total_expenses,
#             "historical_gross_income": hgi
#         }

#     def calculate_pro_forma(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
#         if not analysis.deal_parameters:
#             analysis.deal_parameters = DealParameters()
#         params = analysis.deal_parameters
        
#         # --- REVENUE ---
#         gpr = sum((i.market_rent or 0) * 12 for i in analysis.rent_roll)
#         self.audit_log_service.add_log(analysis, "Pro Forma GPR", f"${gpr:,.0f}", "Rent Roll", "Sum of Market Rents")

#         vacancy_loss = gpr * params.vacancy_rate
#         egi = gpr - vacancy_loss
#         self.audit_log_service.add_log(analysis, "Pro Forma EGI", f"${egi:,.0f}", "Valiance Logic", f"GPR minus {params.vacancy_rate:.1%} Vacancy")

#         # --- EXPENSES (Targeting 38% Ratio) ---
#         target_expense_budget = egi * 0.38
#         self.audit_log_service.add_log(analysis, "Target Expense Budget", f"${target_expense_budget:,.0f}", "Valiance Logic", "38% of EGI Rule")
        
#         # Breakdown Calculation
#         breakdown = self._calculate_pro_forma_breakdown(analysis, target_expense_budget)
        
#         # Final Sum
#         pf_expenses = sum(item.amount for item in breakdown)
#         analysis.pro_forma_expenses_detailed = breakdown
#         analysis.pro_forma_expenses = pf_expenses
        
#         # --- NOI & CAP ---
#         pf_noi = egi - pf_expenses
#         analysis.pro_forma_noi = pf_noi
        
#         price = analysis.property_meta.purchase_price or 0
#         analysis.cap_rate = pf_noi / price if price > 0 else 0
#     def calculate_loan_parameters(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
#         """Calculates key loan metrics based on pro forma NOI and deal parameters."""
#         if not analysis.pro_forma_noi or not analysis.deal_parameters:
#             return {}

#         noi = analysis.pro_forma_noi
#         params = analysis.deal_parameters
        
#         # 1. Debt Service
#         # Assuming monthly payments for a 30-year amortization
#         loan_amount = params.loan_amount
#         monthly_interest_rate = params.interest_rate / 12
#         number_of_payments = params.amortization_period * 12
        
#         if monthly_interest_rate > 0:
#             monthly_payment = (loan_amount * monthly_interest_rate * (1 + monthly_interest_rate) ** number_of_payments) / \
#                               ((1 + monthly_interest_rate) ** number_of_payments - 1)
#         else:
#             monthly_payment = loan_amount / number_of_payments if number_of_payments > 0 else 0
            
#         annual_debt_service = monthly_payment * 12
#         self.audit_log_service.add_log(analysis, "Loan: Annual Debt Service", f"${annual_debt_service:,.2f}", "Loan Logic", "Calculated based on loan amount, interest rate, and amortization period")

#         # 2. Debt Service Coverage Ratio (DSCR)
#         dscr = noi / annual_debt_service if annual_debt_service > 0 else 0
#         self.audit_log_service.add_log(analysis, "Loan: DSCR", f"{dscr:.2f}x", "Loan Logic", "Pro Forma NOI / Annual Debt Service")

#         # 3. Debt Yield
#         debt_yield = noi / loan_amount if loan_amount > 0 else 0
#         self.audit_log_service.add_log(analysis, "Loan: Debt Yield", f"{debt_yield:.2%}", "Loan Logic", "Pro Forma NOI / Loan Amount")
        
#         # Save to analysis object
#         analysis.debt_yield = debt_yield
#         analysis.dscr = dscr
        
#         return {
#             "debt_yield": debt_yield,
#             "dscr": dscr,
#             "annual_debt_service": annual_debt_service
#         }

#     def run_full_analysis(self, analysis: UnderwritingAnalysis) -> UnderwritingAnalysis:
#         """Runs all financial calculations in the correct order."""
#         self.audit_log_service.add_log(analysis, "Analysis Start", "Starting full financial analysis", "System", "Orchestration")
        
#         self.calculate_historical(analysis)
#         self.calculate_pro_forma(analysis)
#         # Note: calculate_loan_parameters is called within calculate_pro_forma
        
#         self.audit_log_service.add_log(analysis, "Analysis Complete", "All financial calculations are complete", "System", "Orchestration")
#         return analysis
#         analysis.exit_cap_rate = params.exit_cap_rate

#         self.audit_log_service.add_log(analysis, "Pro Forma NOI", f"${pf_noi:,.0f}", "Calculation", "EGI - Total Expenses")

#         return {"pro_forma_noi": pf_noi}

#     def _calculate_pro_forma_breakdown(self, analysis: UnderwritingAnalysis, budget: float) -> List[ProFormaExpenseItem]:
#         breakdown = []
        
#         # 1. Taxes (Fixed)
#         price = analysis.property_meta.purchase_price or 0
#         tax = price * 0.0125 if price > 0 else budget * 0.30
#         breakdown.append(ProFormaExpenseItem(name="Property Tax", amount=tax))
        
#         # 2. Variable Allocations
#         remaining = budget - tax
#         if remaining < 0: remaining = 0
        
#         # Allocating the rest to match the 38% target naturally
#         allocations = {
#             "Insurance": 0.15,
#             "Utilities": 0.20,
#             "Management": 0.10,
#             "Repairs": 0.15,
#             "Admin": 0.05,
#             "Landscaping": 0.05,
#             "Reserves": 0.30  # Ensures we use 100% of the remaining budget
#         }
        
#         for name, pct in allocations.items():
#             amt = remaining * pct
#             breakdown.append(ProFormaExpenseItem(name=name, amount=amt))
            
#         return breakdown