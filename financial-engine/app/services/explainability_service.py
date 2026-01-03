from app.models.schemas import (
    UnderwritingAnalysis, 
    ExplainabilityMetadata, 
    ExplanationSource, 
    ExplanationCalculation,
    DealParameters,
    ExpenseCategory
)
from typing import List, Dict, Any, Optional

class ExplainabilityService:
    def generate_explanations(self, analysis: UnderwritingAnalysis) -> UnderwritingAnalysis:
        """
        Populates the explainability metadata for all key financial metrics.
        This is run post-calculation to trace and explain the values.
        """
        self.analysis = analysis
        self.params = analysis.deal_parameters or DealParameters()
        self.explanations: Dict[str, ExplainabilityMetadata] = {}

        # --- Revenue Metrics ---
        self._explain_gpr()
        self._explain_loss_to_lease()
        self._explain_vacancy_loss()
        self._explain_egi()

        # --- Expense Metrics ---
        self._explain_taxes()
        self._explain_mgmt_fee()
        self._explain_total_expenses()

        # --- Profitability Metrics ---
        self._explain_noi()
        self._explain_cap_rate()

        # --- Debt & Cash Flow ---
        self._explain_loan_amount()
        self._explain_debt_service()
        self._explain_cash_flow()
        self._explain_dscr()
        self._explain_debt_yield()

        # --- Returns ---
        self._explain_irr()
        self._explain_moic()

        analysis.explainability = self.explanations
        return analysis

    def _add_explanation(self, key: str, meta: ExplainabilityMetadata):
        self.explanations[key] = meta

    # --- Revenue Implementations ---

    def _explain_gpr(self):
        val = self.analysis.gross_potential_rent or 0.0
        self._add_explanation("Gross Potential Rent", ExplainabilityMetadata(
            metric="Gross Potential Rent (GPR)",
            value=val,
            source=ExplanationSource(
                document="Rent Roll",
                fields_used=["Market Rent", "Unit Count"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Sum(Unit Market Rent * 12)",
                inputs={"Total Units": len(self.analysis.rent_roll)}
            ),
            adjustments=[],
            classification="Derived"
        ))

    def _explain_loss_to_lease(self):
        val = self.analysis.loss_to_lease or 0.0
        gpr = self.analysis.gross_potential_rent or 0.0
        current_rent_annual = sum((item.current_rent or 0) * 12 for item in self.analysis.rent_roll)
        
        self._add_explanation("Loss to Lease", ExplainabilityMetadata(
            metric="Loss to Lease",
            value=val,
            source=ExplanationSource(
                document="Rent Roll",
                fields_used=["Market Rent", "Current Rent"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Gross Potential Rent - Annualized Current Rent",
                inputs={
                    "Gross Potential Rent": gpr,
                    "Annualized Current Rent": current_rent_annual
                }
            ),
            adjustments=[],
            classification="Derived"
        ))

    def _explain_vacancy_loss(self):
        val = self.analysis.vacancy_loss or 0.0
        gpr = self.analysis.gross_potential_rent or 0.0
        rate = self.params.vacancy_rate
        
        self._add_explanation("Vacancy Loss", ExplainabilityMetadata(
            metric="Vacancy Loss",
            value=val,
            source=ExplanationSource(
                document="Assumption Engine",
                fields_used=["Vacancy Rate", "GPR"],
                data_type="Derived with Assumptions"
            ),
            calculation=ExplanationCalculation(
                formula="Gross Potential Rent * Vacancy Rate",
                inputs={
                    "Gross Potential Rent": gpr,
                    "Vacancy Rate": rate
                }
            ),
            adjustments=["Standard 3% vacancy assumption applied"],
            classification="Derived with Assumptions"
        ))

    def _explain_egi(self):
        val = self.analysis.effective_gross_income or 0.0
        gpr = self.analysis.gross_potential_rent or 0.0
        ltl = self.analysis.loss_to_lease or 0.0
        vac = self.analysis.vacancy_loss or 0.0
        
        self._add_explanation("Effective Gross Income", ExplainabilityMetadata(
            metric="Effective Gross Income (EGI)",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["GPR", "Loss to Lease", "Vacancy Loss"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="GPR - Loss to Lease - Vacancy Loss",
                inputs={
                    "Gross Potential Rent": gpr,
                    "Loss to Lease": ltl,
                    "Vacancy Loss": vac
                }
            ),
            adjustments=[],
            classification="Derived"
        ))

    # --- Expense Implementations ---

    def _explain_taxes(self):
        # Find tax item in detailed expenses
        tax_item = next((item for item in self.analysis.pro_forma_expenses_detailed if item.name == "Property Taxes"), None)
        val = tax_item.amount if tax_item else 0.0
        purchase_price = self.analysis.property_meta.purchase_price or 0.0
        rate = self.params.tax_rate
        
        self._add_explanation("Property Taxes", ExplainabilityMetadata(
            metric="Property Taxes",
            value=val,
            source=ExplanationSource(
                document="Assumption Engine",
                fields_used=["Purchase Price", "Tax Rate"],
                data_type="Derived with Assumptions"
            ),
            calculation=ExplanationCalculation(
                formula="Purchase Price * Tax Rate",
                inputs={
                    "Purchase Price": purchase_price,
                    "Tax Rate": rate
                }
            ),
            adjustments=["Prop 13 Reset Assumption"],
            classification="Derived with Assumptions"
        ))

    def _explain_mgmt_fee(self):
        mgmt_item = next((item for item in self.analysis.pro_forma_expenses_detailed if item.name == "Management Fee"), None)
        val = mgmt_item.amount if mgmt_item else 0.0
        egi = self.analysis.effective_gross_income or 0.0
        rate = self.params.management_fee_rate
        
        self._add_explanation("Management Fee", ExplainabilityMetadata(
            metric="Management Fee",
            value=val,
            source=ExplanationSource(
                document="Assumption Engine",
                fields_used=["EGI", "Management Fee Rate"],
                data_type="Derived with Assumptions"
            ),
            calculation=ExplanationCalculation(
                formula="EGI * Management Fee Rate",
                inputs={
                    "Effective Gross Income": egi,
                    "Rate": rate
                }
            ),
            adjustments=["Standard 4% Management Fee"],
            classification="Derived with Assumptions"
        ))

    def _explain_total_expenses(self):
        val = self.analysis.pro_forma_expenses or 0.0
        
        # Identify T12 usage
        t12_used = any(item.name not in ["Property Taxes", "Management Fee"] for item in self.analysis.pro_forma_expenses_detailed)
        source_doc = "T12 + Assumption Engine" if t12_used else "Assumption Engine Only"
        
        inputs = {item.name: item.amount for item in self.analysis.pro_forma_expenses_detailed}
        
        self._add_explanation("Total Operating Expenses", ExplainabilityMetadata(
            metric="Total Operating Expenses",
            value=val,
            source=ExplanationSource(
                document=source_doc,
                fields_used=["Taxes", "Management Fee", "T12 Operating Expenses"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Sum(All Expense Line Items)",
                inputs=inputs
            ),
            adjustments=[],
            classification="Derived"
        ))

    # --- Profitability Implementations ---

    def _explain_noi(self):
        val = self.analysis.pro_forma_noi or 0.0
        egi = self.analysis.effective_gross_income or 0.0
        opex = self.analysis.pro_forma_expenses or 0.0
        
        self._add_explanation("Net Operating Income (NOI)", ExplainabilityMetadata(
            metric="Net Operating Income (NOI)",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["EGI", "Total Expenses"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Effective Gross Income - Total Operating Expenses",
                inputs={
                    "Effective Gross Income": egi,
                    "Total Operating Expenses": opex
                }
            ),
            adjustments=[],
            classification="Derived"
        ))

    def _explain_cap_rate(self):
        val = self.analysis.cap_rate or 0.0
        noi = self.analysis.pro_forma_noi or 0.0
        purchase_price = self.analysis.property_meta.purchase_price or 0.0
        
        classification = "Derived"
        adjustments = []
        if purchase_price == 0:
            classification = "Invalid / Not Meaningful"
            adjustments.append("Purchase Price missing")
            
        self._add_explanation("Entry Cap Rate", ExplainabilityMetadata(
            metric="Entry Cap Rate",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["NOI", "Purchase Price"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="NOI / Purchase Price",
                inputs={
                    "NOI": noi,
                    "Purchase Price": purchase_price
                }
            ),
            adjustments=adjustments,
            classification=classification
        ))

    # --- Debt & Cash Flow Implementations ---

    def _explain_loan_amount(self):
        val = self.analysis.loan_amount or 0.0
        purchase_price = self.analysis.property_meta.purchase_price or 0.0
        ltv = self.params.ltv
        
        formula = "Purchase Price * LTV"
        inputs = {"Purchase Price": purchase_price, "LTV": ltv}
        adjustments = []
        
        if purchase_price == 0:
            formula = "Implied Value (NOI / Exit Cap) * LTV"
            noi = self.analysis.pro_forma_noi or 0.0
            exit_cap = self.params.exit_cap_rate
            inputs = {"NOI": noi, "Exit Cap Rate": exit_cap, "LTV": ltv}
            adjustments.append("Purchase Price missing, using Implied Value")

        self._add_explanation("Loan Amount", ExplainabilityMetadata(
            metric="Loan Amount",
            value=val,
            source=ExplanationSource(
                document="Assumption Engine",
                fields_used=["Purchase Price", "LTV"],
                data_type="Derived with Assumptions"
            ),
            calculation=ExplanationCalculation(
                formula=formula,
                inputs=inputs
            ),
            adjustments=adjustments,
            classification="Derived with Assumptions"
        ))

    def _explain_debt_service(self):
        val = self.analysis.annual_debt_service or 0.0
        loan = self.analysis.loan_amount or 0.0
        rate = self.params.sofr_rate + self.params.bridge_spread
        
        self._add_explanation("Annual Debt Service", ExplainabilityMetadata(
            metric="Annual Debt Service",
            value=val,
            source=ExplanationSource(
                document="Assumption Engine",
                fields_used=["Loan Amount", "Interest Rate"],
                data_type="Derived with Assumptions"
            ),
            calculation=ExplanationCalculation(
                formula="Loan Amount * Interest Rate (Interest Only)",
                inputs={
                    "Loan Amount": loan,
                    "Interest Rate": rate
                }
            ),
            adjustments=["Interest Only Loan Assumption"],
            classification="Derived with Assumptions"
        ))

    def _explain_cash_flow(self):
        val = self.analysis.cash_flow or 0.0
        noi = self.analysis.pro_forma_noi or 0.0
        ds = self.analysis.annual_debt_service or 0.0
        
        self._add_explanation("Cash Flow", ExplainabilityMetadata(
            metric="Levered Cash Flow",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["NOI", "Debt Service"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="NOI - Annual Debt Service",
                inputs={
                    "NOI": noi,
                    "Annual Debt Service": ds
                }
            ),
            adjustments=[],
            classification="Derived"
        ))

    def _explain_dscr(self):
        val = self.analysis.dscr or 0.0
        noi = self.analysis.pro_forma_noi or 0.0
        ds = self.analysis.annual_debt_service or 0.0
        
        classification = "Derived"
        if ds == 0:
            classification = "Invalid / Not Meaningful"

        self._add_explanation("DSCR", ExplainabilityMetadata(
            metric="Debt Service Coverage Ratio (DSCR)",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["NOI", "Debt Service"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="NOI / Annual Debt Service",
                inputs={
                    "NOI": noi,
                    "Annual Debt Service": ds
                }
            ),
            adjustments=[],
            classification=classification
        ))

    def _explain_debt_yield(self):
        val = self.analysis.debt_yield or 0.0
        noi = self.analysis.pro_forma_noi or 0.0
        loan = self.analysis.loan_amount or 0.0

        classification = "Derived"
        if loan == 0:
            classification = "Invalid / Not Meaningful"

        self._add_explanation("Debt Yield", ExplainabilityMetadata(
            metric="Debt Yield",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["NOI", "Loan Amount"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="NOI / Loan Amount",
                inputs={
                    "NOI": noi,
                    "Loan Amount": loan
                }
            ),
            adjustments=[],
            classification=classification
        ))

    # --- Return Implementations ---

    def _explain_irr(self):
        val = self.analysis.irr or 0.0
        hold = self.params.hold_period
        exit_cap = self.params.exit_cap_rate
        
        self._add_explanation("IRR", ExplainabilityMetadata(
            metric="Internal Rate of Return (IRR)",
            value=val,
            source=ExplanationSource(
                document="Projection Engine",
                fields_used=["Cash Flows", "Hold Period", "Exit Cap"],
                data_type="Derived with Assumptions"
            ),
            calculation=ExplanationCalculation(
                formula=f"IRR of {hold}-Year Cash Flows + Net Sale Proceeds",
                inputs={
                    "Hold Period": hold,
                    "Exit Cap Rate": exit_cap,
                    "Growth Rate": self.params.growth_rate
                }
            ),
            adjustments=[f"Assumes {hold}-year hold", f"Exit at {exit_cap:.1%} Cap Rate"],
            classification="Derived with Assumptions"
        ))

    def _explain_moic(self):
        val = self.analysis.moic or 0.0
        equity = self.analysis.equity_invested or 0.0
        
        self._add_explanation("MOIC", ExplainabilityMetadata(
            metric="Multiple on Invested Capital (MOIC)",
            value=val,
            source=ExplanationSource(
                document="Projection Engine",
                fields_used=["Total Inflows", "Equity Invested"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Total Cash Inflows / Equity Invested",
                inputs={
                    "Equity Invested": equity,
                    "Hold Period": self.params.hold_period
                }
            ),
            adjustments=[],
            classification="Derived"
        ))