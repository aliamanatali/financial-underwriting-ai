import numpy_financial as npf # type: ignore
import math
from app.models.schemas import UnderwritingAnalysis, DealParameters, ProFormaExpenseItem, ExpenseCategory
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

from app.services.audit_log_service import AuditLogService

class FinancialService:
    def __init__(self, audit_log_service: AuditLogService):
        self.audit_log_service = audit_log_service

    def _sanitize_value(self, value: Optional[float]) -> float:
        """
        Safely sanitize float values to ensure they are JSON compliant.
        Replaces NaN and Infinity with 0.0.
        """
        if value is None:
            return 0.0
        try:
            if isinstance(value, (float, int)):
                if math.isnan(value) or math.isinf(value):
                    return 0.0
        except Exception:
            return 0.0
        return value

    def check_deal_viability(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
        """
        Checks hard gating criteria (Unit Count, Loan Amount, etc.)
        """
        reasons = []
        status = "PASS"
        # Ensure parameters exist, else use defaults
        params = analysis.deal_parameters or DealParameters()
        
        # 1. Unit Count Check
        unit_count = analysis.property_meta.total_units or 0
        if not (params.min_unit_count <= unit_count <= params.max_unit_count):
            status = "FAIL"
            reasons.append(f"Unit count FAIL: {unit_count} units is outside range {params.min_unit_count}-{params.max_unit_count}.")
        
        # 2. Loan Amount Check (Preliminary, based on Purchase Price if available)
        # Note: True Loan Amount is calculated in Step 4, but we can check rough sizing here.
        purchase_price = analysis.property_meta.purchase_price or 0
        
        # Only check if Purchase Price is known. If 0/Missing, we defer to Step 4 (Implied Valuation).
        if purchase_price > 0:
            estimated_loan = purchase_price * params.ltv
            if estimated_loan < params.min_loan_amount:
                status = "FAIL"
                reasons.append(f"Loan amount FAIL: Estimated loan ${estimated_loan:,.0f} is below minimum of ${params.min_loan_amount:,.0f}.")
        
        # 3. Vintage Check
        year_built = analysis.property_meta.year_built or 0
        if year_built > 0 and year_built < params.max_build_year and not analysis.property_meta.is_renovated:
            status = "FAIL"
            reasons.append(f"Property vintage FAIL: Built in {year_built} (before {params.max_build_year}) and not renovated.")
        
        return {"status": status, "reasons": reasons}

    def calculate_historical(self, analysis: UnderwritingAnalysis) -> Dict[str, float]:
        """
        Calculates T12 historical performance based on extracted data.
        """
        hgi = sum(item.current_rent * 12 for item in analysis.rent_roll)
        
        total_expenses = 0.0
        if analysis.historical_expenses:
            total_expenses = sum(expense.amount for expense in analysis.historical_expenses)
            if total_expenses == 0:
                logger.warning("Historical expenses list is present but total amount is 0. Check normalization.")
        else:
            logger.warning("No historical expenses found in analysis object.")

        historical_noi = hgi - total_expenses
        
        purchase_price = analysis.property_meta.purchase_price or 0
        historical_cap_rate = historical_noi / purchase_price if purchase_price > 0 else 0
        
        # Save to Analysis Object
        analysis.historical_total_expenses = self._sanitize_value(total_expenses)
        analysis.historical_noi = self._sanitize_value(historical_noi)
        analysis.historical_cap_rate = self._sanitize_value(historical_cap_rate)
        
        return {
            "gross_income": hgi,
            "total_expenses": total_expenses,
            "historical_noi": historical_noi,
            "historical_cap_rate": analysis.historical_cap_rate,
        }

    def calculate_pro_forma(self, analysis: UnderwritingAnalysis) -> Dict[str, Any]:
        """
        Executes the 5-Step Deterministic Financial Model.
        """
        if not analysis.deal_parameters:
            analysis.deal_parameters = DealParameters()
        
        # Sanitize parameters to prevent NaN propagation
        self._sanitize_parameters(analysis.deal_parameters)
            
        self.audit_log_service.add_log(analysis, "Pro Forma Start", "Initiating 5-Step Calculation", "System", "Orchestration")

        # Step 1: Revenue Logic
        self._calculate_revenue(analysis)
        
        # Step 2: Expense Logic
        self._calculate_expenses(analysis)
        
        # Step 3: Profitability Metrics (NOI)
        self._calculate_profitability(analysis)
        
        # Step 4: Debt & Cash Flow
        self._calculate_debt_and_cash_flow(analysis)
        
        # Step 5: Time-Based Returns (IRR & MOIC)
        self._calculate_returns(analysis)
        
        return {
            "status": "Success",
            "pro_forma_noi": analysis.pro_forma_noi,
            "pro_forma_expenses": analysis.pro_forma_expenses,
            "cap_rate": analysis.cap_rate,
            "exit_cap_rate": analysis.deal_parameters.exit_cap_rate if analysis.deal_parameters else 0.0,
            "irr": analysis.irr,
            "moic": analysis.moic
        }

    def _sanitize_parameters(self, params: DealParameters):
        """Helper to ensure no NaN values in deal parameters"""
        if math.isnan(params.growth_rate): params.growth_rate = 0.03
        if math.isnan(params.vacancy_rate): params.vacancy_rate = 0.05
        if math.isnan(params.management_fee_rate): params.management_fee_rate = 0.04
        if math.isnan(params.tax_rate): params.tax_rate = 0.012
        if math.isnan(params.exit_cap_rate): params.exit_cap_rate = 0.06
        if math.isnan(params.ltv): params.ltv = 0.65
        if math.isnan(params.sofr_rate): params.sofr_rate = 0.05
        if math.isnan(params.bridge_spread): params.bridge_spread = 0.02
        if math.isnan(params.closing_costs): params.closing_costs = 0.0
        if math.isnan(params.renovation_budget): params.renovation_budget = 0.0

    # --- Step 1: Revenue Logic ---
    def _calculate_revenue(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()

        # 1. Gross Potential Rent (GPR)
        # Formula: Total Units * Market Rent per Unit * 12
        # Note: We sum up individual units from Rent Roll for accuracy
        gpr = sum((item.market_rent or 0) * 12 for item in analysis.rent_roll)
        analysis.gross_potential_rent = self._sanitize_value(gpr)
        self.audit_log_service.add_log(analysis, "GPR", f"${gpr:,.0f}", "Rent Roll", "Sum of (Market Rent * 12)")

        # 2. Loss to Lease
        # Formula: GPR - (Current Rent Roll Sum * 12)
        current_rent_annual = sum((item.current_rent or 0) * 12 for item in analysis.rent_roll)
        loss_to_lease = gpr - current_rent_annual
        analysis.loss_to_lease = self._sanitize_value(loss_to_lease)
        self.audit_log_service.add_log(analysis, "Loss to Lease", f"${loss_to_lease:,.0f}", "Calculation", "GPR - Current Rent Annualized")

        # 3. Vacancy Loss
        # Formula: GPR * 0.03 (Valiance Constraint)
        vacancy_loss = gpr * params.vacancy_rate
        analysis.vacancy_loss = self._sanitize_value(vacancy_loss)
        self.audit_log_service.add_log(analysis, "Vacancy Loss", f"${vacancy_loss:,.0f}", "Valiance Rule", f"{params.vacancy_rate:.1%} of GPR")

        # 4. Effective Gross Income (EGI)
        # Formula: GPR - LossToLease - VacancyLoss + Other Income
        # Note: Assuming 'Other Income' is 0 for now as it's not in the base extraction yet,
        # but could be added from T12 extraction if available.
        other_income = 0
        egi = gpr - loss_to_lease - vacancy_loss + other_income
        analysis.effective_gross_income = self._sanitize_value(egi)
        self.audit_log_service.add_log(analysis, "EGI", f"${egi:,.0f}", "Calculation", "GPR - LossToLease - VacancyLoss")

    # --- Step 2: Expense Logic ---
    def _calculate_expenses(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()
        egi = analysis.effective_gross_income or 0
        purchase_price = analysis.property_meta.purchase_price or 0
        
        expense_breakdown: List[ProFormaExpenseItem] = []

        # 1. Property Taxes (Prop 13 Reset)
        # Formula: (Purchase Price * Tax Rate) + Special Assessments
        pro_forma_tax = self._sanitize_value(purchase_price * params.tax_rate)
        expense_breakdown.append(ProFormaExpenseItem(name="Property Taxes", amount=pro_forma_tax))
        self.audit_log_service.add_log(analysis, "Expense: Taxes", f"${pro_forma_tax:,.0f}", "Valiance Rule", f"Purchase Price * {params.tax_rate:.2%}")

        # 2. Management Fee
        # Formula: EGI * 0.04
        mgmt_fee = self._sanitize_value(egi * params.management_fee_rate)
        expense_breakdown.append(ProFormaExpenseItem(name="Management Fee", amount=mgmt_fee))
        self.audit_log_service.add_log(analysis, "Expense: Mgmt Fee", f"${mgmt_fee:,.0f}", "Valiance Rule", f"{params.management_fee_rate:.1%} of EGI")

        # 3. Other Operating Expenses (Sourced from T12)
        # We aggregate historical expenses by category, excluding Taxes and Mgmt Fees which are recalculated.
        other_expenses_map: Dict[str, float] = {}
        has_t12_data = False
        
        if analysis.historical_expenses:
            has_t12_data = True
            for expense in analysis.historical_expenses:
                # Skip if it's Taxes or Mgmt Fee - we use the calculated values above
                if expense.mapped_category in [ExpenseCategory.REAL_ESTATE_TAXES, ExpenseCategory.MANAGEMENT_FEES]:
                    continue
                    
                cat_name = expense.mapped_category.value
                other_expenses_map[cat_name] = other_expenses_map.get(cat_name, 0.0) + expense.amount
        else:
             self.audit_log_service.add_log(analysis, "Data Warning", "No T12 Expenses Found", "Extraction", "Using only calculated Taxes & Mgmt Fee")
             analysis.gating_reasons.append("CRITICAL: No T12 Expense Data extracted. Pro Forma expenses may be understated.")
        
        # Add aggregated other expenses to breakdown
        total_other_opex = 0.0
        for name, amount in other_expenses_map.items():
            safe_amount = self._sanitize_value(amount)
            expense_breakdown.append(ProFormaExpenseItem(name=name, amount=safe_amount))
            total_other_opex += safe_amount
            
        if has_t12_data:
            self.audit_log_service.add_log(analysis, "Other OpEx", f"${total_other_opex:,.0f}", "Aggregation", "Sum of T12 Expenses (Excl. Tax/Mgmt)")

        total_opex = sum(item.amount for item in expense_breakdown)
        analysis.pro_forma_expenses = self._sanitize_value(total_opex)
        analysis.pro_forma_expenses_detailed = expense_breakdown
        
        # 4. Expense Ratio Evaluation (Check, don't force)
        expense_ratio = total_opex / egi if egi > 0 else 0
        
        if expense_ratio < 0.20:
             analysis.gating_reasons.append(f"WARNING: Expense Ratio {expense_ratio:.1%} is suspiciously low (<20%). Check if T12 data was extracted.")
        elif expense_ratio > 0.60:
            analysis.gating_reasons.append(f"WARNING: Expense Ratio {expense_ratio:.1%} is unusually high (>60%)")
        
        self.audit_log_service.add_log(analysis, "Total OpEx", f"${total_opex:,.0f}", "Summation", f"Calculated Ratio: {expense_ratio:.1%}")

    # --- Step 3: Profitability Metrics (NOI) ---
    def _calculate_profitability(self, analysis: UnderwritingAnalysis):
        egi = analysis.effective_gross_income or 0
        opex = analysis.pro_forma_expenses or 0
        purchase_price = analysis.property_meta.purchase_price or 0
        params = analysis.deal_parameters or DealParameters()

        # 1. Net Operating Income (NOI)
        # Formula: EGI - OpEx
        noi = egi - opex
        analysis.pro_forma_noi = self._sanitize_value(noi)
        self.audit_log_service.add_log(analysis, "NOI", f"${noi:,.0f}", "Calculation", "EGI - OpEx")

        # 2. Yield on Cost (Unlevered Yield)
        # Formula: NOI / Total Project Cost
        # Total Project Cost = Purchase Price + Closing Costs + Renovation Budget
        total_project_cost = purchase_price + params.closing_costs + params.renovation_budget
        analysis.total_project_cost = total_project_cost
        
        yield_on_cost = noi / total_project_cost if total_project_cost > 0 else 0
        analysis.yield_on_cost = self._sanitize_value(yield_on_cost)
        self.audit_log_service.add_log(analysis, "Yield on Cost", f"{yield_on_cost:.2%}", "Calculation", "NOI / Total Project Cost")

        # 3. Entry Cap Rate
        # Formula: NOI / Purchase Price
        entry_cap_rate = noi / purchase_price if purchase_price > 0 else 0
        analysis.cap_rate = self._sanitize_value(entry_cap_rate)
        self.audit_log_service.add_log(analysis, "Entry Cap Rate", f"{entry_cap_rate:.2%}", "Calculation", "NOI / Purchase Price")

    # --- Step 4: Debt & Cash Flow ---
    def _calculate_debt_and_cash_flow(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()
        purchase_price = analysis.property_meta.purchase_price or 0
        noi = analysis.pro_forma_noi or 0
        total_project_cost = analysis.total_project_cost or 0

        # 1. Loan Amount Logic
        # CASE A: Purchase Price is known -> Standard LTV calculation
        if purchase_price > 0:
            loan_amount = purchase_price * params.ltv
            method = f"Purchase Price * {params.ltv:.0%} LTV"
        
        # CASE B: Purchase Price is missing (0) -> Back-solve from NOI/Cap Rate (Implied Value)
        else:
            # Assume a market cap rate (e.g., 5.5% or exit cap rate) to estimate value
            # If NOI is negative, implied value is 0 (cannot have negative property value for loan purposes)
            implied_value = max(0.0, noi / params.exit_cap_rate if params.exit_cap_rate > 0 else 0)
            loan_amount = implied_value * params.ltv
            method = f"Implied Value (NOI/{params.exit_cap_rate:.1%}) * {params.ltv:.0%} LTV (Price Missing)"
            
            # Update purchase price in meta so other metrics (Cap Rate) work?
            # Ideally, we flag this as an estimate.
            if implied_value > 0:
                logger.warning(f"Purchase Price missing. Using Implied Value ${implied_value:,.0f} for Loan calc.")
                # We won't overwrite extracted Purchase Price to preserve data integrity,
                # but we will use this implied loan amount.

        analysis.loan_amount = self._sanitize_value(loan_amount)
        self.audit_log_service.add_log(analysis, "Loan Amount", f"${loan_amount:,.0f}", "Calculation", method)

        # Gating Logic
        if loan_amount < params.min_loan_amount:
            # Check if this is a hard fail or just a warning? Usually hard fail for lending criteria.
            # We set status to FAIL but proceed with calcs.
            analysis.pass_fail_status = "FAIL"
            analysis.gating_reasons.append(f"Loan Amount ${loan_amount:,.0f} < ${params.min_loan_amount:,.0f}")

        # 2. Debt Service (Interest Only - "Bridge Debt")
        # Formula: SOFR + Spread
        interest_rate = params.sofr_rate + params.bridge_spread
        annual_debt_service = loan_amount * interest_rate
        analysis.annual_debt_service = self._sanitize_value(annual_debt_service)
        self.audit_log_service.add_log(analysis, "Debt Service", f"${annual_debt_service:,.0f}", "Calculation", f"Loan * {interest_rate:.2%} (IO)")

        # 3. Levered Cash Flow
        # Formula: NOI - Annual Debt Service
        cash_flow = noi - annual_debt_service
        analysis.cash_flow = self._sanitize_value(cash_flow)
        self.audit_log_service.add_log(analysis, "Cash Flow", f"${cash_flow:,.0f}", "Calculation", "NOI - Debt Service")

        # 4. Cash on Cash Return
        # Formula: Cash Flow / Equity Invested
        # Equity Invested = Total Project Cost - Loan Amount
        equity_invested = total_project_cost - loan_amount
        analysis.equity_invested = self._sanitize_value(equity_invested)
        
        coc = cash_flow / equity_invested if equity_invested > 0 else 0
        analysis.cash_on_cash_return = self._sanitize_value(coc)
        self.audit_log_service.add_log(analysis, "Cash on Cash", f"{coc:.2%}", "Calculation", "Cash Flow / Equity Invested")
        
        # Additional Metrics
        analysis.dscr = self._sanitize_value(noi / annual_debt_service if annual_debt_service > 0 else 0)
        analysis.debt_yield = self._sanitize_value(noi / loan_amount if loan_amount > 0 else 0)

    # --- Step 5: Time-Based Returns (IRR & MOIC) ---
    def _calculate_returns(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()

        # VALIDATION: Ensure rent_growth is valid before projection
        if params.growth_rate is None or math.isnan(params.growth_rate):
             params.growth_rate = 0.03
             
        # Generate Sensitivity Matrix
        self._generate_sensitivity_matrix(analysis)
        
        # 1. Revenue Growth Logic
        # 5-Year Array/Loop
        cash_flows = []
        equity_invested = analysis.equity_invested or 0
        
        # Year 0: Investment (Negative)
        cash_flows.append(-equity_invested)
        
        # Current NOI is Year 1 Base
        current_noi = analysis.pro_forma_noi or 0
        
        # IMPORTANT: We assume NOI grows at the same rate as Revenue for simplicity in this model,
        # OR we could grow Revenue and Expenses separately.
        # Given the prompt says "Rents grow 3% annually", we'll apply growth to NOI for simplicity 
        # unless full pro-forma tables are needed. 
        # Re-reading prompt: "Year N Revenue = Year N-1 Revenue * 1.03".
        # It doesn't specify Expense growth, but usually expenses grow too (at 2-3%).
        # Let's assume NOI grows at 3% to keep it consistent with Revenue growth, 
        # or implies Revenue grows and Expenses stay flat (which is aggressive).
        # Better approach: Grow Revenue by 3%, Expenses by 3% (Standard), so NOI grows by 3%.
        
        annual_noi = current_noi
        
        # Years 1-4 Cash Flow
        for year in range(1, params.hold_period):
            # Cash Flow = NOI - Debt Service
            cf = annual_noi - (analysis.annual_debt_service or 0)
            cash_flows.append(cf)
            
            # Grow NOI for next year
            annual_noi *= (1 + params.growth_rate)
            
        # Year 5 (Exit Year)
        year_5_noi = annual_noi
        # Note: Sell on Year 6 NOI (forward NOI)
        year_6_noi = year_5_noi * (1 + params.growth_rate)
        
        # 2. Exit Valuation
        # Formula: Year 6 NOI / Exit Cap Rate
        if params.exit_cap_rate and params.exit_cap_rate > 0:
            sale_price = year_6_noi / params.exit_cap_rate
        else:
            sale_price = 0.0
        analysis.exit_valuation = self._sanitize_value(sale_price)
        
        # 3. Net Sale Proceeds
        # Formula: Sale Price - Sales Costs (2%) - Outstanding Loan Balance
        sales_costs = sale_price * params.sales_cost_rate
        loan_balance = analysis.loan_amount or 0 # Interest Only, so balance is constant
        net_proceeds = sale_price - sales_costs - loan_balance
        analysis.net_sale_proceeds = self._sanitize_value(net_proceeds)
        
        # Year 5 Cash Flow includes Operations + Sale
        year_5_cf = (year_5_noi - (analysis.annual_debt_service or 0)) + net_proceeds
        cash_flows.append(year_5_cf)
        
        # 4. MOIC
        # Formula: Sum(Positive Cash Flows) / Equity Invested
        # Note: cash_flows[0] is negative equity.
        total_inflows = sum(cf for cf in cash_flows if cf > 0)
        moic = total_inflows / equity_invested if equity_invested > 0 else 0
        analysis.moic = self._sanitize_value(moic)
        
        # 5. IRR
        try:
            # Check for zero cash flows or all negative/all positive which breaks IRR
            if not cash_flows or all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
                irr = 0.0
            else:
                irr = npf.irr(cash_flows)
                # Handle complex results
                if isinstance(irr, complex):
                    irr = 0.0
                elif irr is None or math.isnan(irr) or math.isinf(irr):
                    irr = 0.0
                else:
                    irr = float(irr)
        except Exception:
            irr = 0.0
            
        analysis.irr = self._sanitize_value(irr)
        
        self.audit_log_service.add_log(analysis, "IRR", f"{irr:.2%}", "Numpy Financial", "IRR of 5-Year Cash Flows")
        self.audit_log_service.add_log(analysis, "MOIC", f"{moic:.2f}x", "Calculation", "Total Inflows / Equity Invested")

    def _calculate_irr_simulation(self, analysis: UnderwritingAnalysis, growth_rate: float, exit_cap_rate: float) -> float:
        """
        Helper to simulate IRR for Sensitivity Analysis.
        Does not modify analysis object.
        """
        params = analysis.deal_parameters or DealParameters()
        
        equity_invested = analysis.equity_invested or 0
        current_noi = analysis.pro_forma_noi or 0
        annual_debt_service = analysis.annual_debt_service or 0
        loan_amount = analysis.loan_amount or 0
        
        cash_flows = []
        # Year 0
        cash_flows.append(-equity_invested)
        
        annual_noi = current_noi
        
        # Years 1 to (Hold-1)
        for year in range(1, params.hold_period):
            cf = annual_noi - annual_debt_service
            cash_flows.append(cf)
            annual_noi *= (1 + growth_rate)
            
        # Year 5 (Exit)
        year_exit_noi = annual_noi
        
        # Sell on forward NOI (Year 6)
        # Note: If exit cap is applied to T12 (Year 5 actual), use year_exit_noi.
        # If applied to Forward 12 (Year 6), use year_forward_noi.
        # Standard practice is often Forward 12 for pricing.
        year_forward_noi = year_exit_noi * (1 + growth_rate)
        
        if exit_cap_rate > 0:
            sale_price = year_forward_noi / exit_cap_rate
        else:
            sale_price = 0.0
            
        sales_costs = sale_price * params.sales_cost_rate
        net_proceeds = sale_price - sales_costs - loan_amount
        
        # Year 5 Cash Flow
        year_exit_cf = (year_exit_noi - annual_debt_service) + net_proceeds
        cash_flows.append(year_exit_cf)
        
        try:
            # Check for zero cash flows or all negative/all positive which breaks IRR
            if not cash_flows or all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
                return 0.0
                
            irr = npf.irr(cash_flows)
            
            # Handle complex results (rare but possible with weird polynomials)
            if isinstance(irr, complex):
                return 0.0
                
            if irr is None or math.isnan(irr) or math.isinf(irr):
                return 0.0
                
            return float(irr)
        except Exception as e:
            logger.warning(f"IRR Simulation failed: {str(e)}")
            return 0.0

    def _generate_sensitivity_matrix(self, analysis: UnderwritingAnalysis):
        params = analysis.deal_parameters or DealParameters()
        base_exit_cap = params.exit_cap_rate
        base_growth = params.growth_rate
        
        # Rows: Exit Cap Rate (Base-0.5%, Base, Base+0.5%)
        # Columns: Rent Growth (Base-1%, Base, Base+1%)
        
        row_steps = [-0.005, 0.0, 0.005]
        col_steps = [-0.01, 0.0, 0.01]
        
        exit_caps = [max(0, base_exit_cap + step) for step in row_steps]
        growth_rates = [base_growth + step for step in col_steps]
        
        values = []
        for cap in exit_caps:
            row_vals = []
            for growth in growth_rates:
                irr = self._calculate_irr_simulation(analysis, growth, cap)
                row_vals.append(irr)
            values.append(row_vals)
            
        analysis.sensitivity_analysis = {
            "rows": exit_caps,
            "columns": growth_rates,
            "values": values
        }

    def get_audit_trail(self, analysis: UnderwritingAnalysis) -> List[Dict[str, Any]]:
        return analysis.audit_trail