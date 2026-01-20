from app.models.schemas import (
    UnderwritingAnalysis, 
    ExplainabilityMetadata, 
    ExplanationSource,
    ExplanationCalculation,
    DealParameters,
    ExpenseCategory,
    Conclusion,
    DecisionImpact,
    InvestmentChecklist
)
from typing import List, Dict, Any, Optional
from app.services.gemini_client import GeminiClient

class ExplainabilityService:
    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini_client = gemini_client

    async def generate_explanations(self, analysis: UnderwritingAnalysis) -> UnderwritingAnalysis:
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
        self._explain_historical_total_expenses()

        # --- Profitability Metrics ---
        self._explain_noi()
        self._explain_historical_noi()
        self._explain_cap_rate()
        self._explain_historical_cap_rate()

        # --- Debt & Cash Flow ---
        self._explain_loan_amount()
        self._explain_debt_service()
        self._explain_cash_flow()
        self._explain_dscr()
        self._explain_debt_yield()

        # --- Returns ---
        self._explain_irr()
        self._explain_moic()

        # --- Conclusion ---
        self._generate_conclusion()
        
        # --- Analyst Commentary (GenAI) ---
        if self.gemini_client:
            await self._generate_analyst_commentary()

        analysis.explainability = self.explanations
        return analysis

    async def _generate_analyst_commentary(self):
        """
        Generates a 3-paragraph analyst commentary using GenAI.
        """
        # Prepare context
        context = {
            "address": self.analysis.property_meta.address,
            "purchase_price": self.analysis.property_meta.purchase_price,
            "units": self.analysis.property_meta.total_units,
            "noi": self.analysis.pro_forma_noi,
            "cap_rate": self.analysis.cap_rate,
            "dscr": self.analysis.dscr,
            "status": self.analysis.pass_fail_status,
            "gating_reasons": self.analysis.gating_reasons,
            "loss_to_lease": self.analysis.loss_to_lease,
            "growth_rate": self.params.growth_rate,
            "irr": self.analysis.irr,
            "moic": self.analysis.moic
        }
        
        prompt = f"""
        Context Data:
        {context}

        Prompt: "Act as a Senior Investment Analyst. Write a 3-paragraph summary explaining why you approved or rejected this deal. Discuss potential physical/structural considerations based on property age and highlight the upside in rent."
        
        Guidance for AI:
        - If the status is PASS, you generally approve. If FAIL, you reject.
        - DO NOT fabricate specific findings from a structural report (e.g., do not mention specific foundation or roof issues unless they are in the data).
        - Instead, based on the Year Built ({self.analysis.property_meta.year_built}), recommend standard due diligence (e.g., "Given the 1970s vintage, a Property Condition Assessment is recommended to evaluate plumbing and roof systems").
        - "Upside in rent" refers to the Loss to Lease (Current vs Market).
        """
        
        try:
            commentary = await self.gemini_client.generate_content_async(prompt)
            self.analysis.analyst_commentary = commentary
        except Exception as e:
            print(f"Failed to generate commentary: {e}")
            self.analysis.analyst_commentary = "Analyst commentary unavailable due to service error."

    def _add_explanation(self, key: str, meta: ExplainabilityMetadata):
        self.explanations[key] = meta

    def _get_source(self, field_name: str, default_source: str) -> str:
        """
        Helper to find the source of a field from the audit trail.
        Returns the specific document or method if found, otherwise the default.
        """
        if not self.analysis.audit_trail:
            return default_source
            
        # Search audit trail for the field
        # We look for partial matches or exact matches on field_name
        for log in self.analysis.audit_trail:
            if isinstance(log, dict) and log.get('field_name') == field_name:
                source = log.get('source', 'Unknown')
                method = log.get('method', 'Extraction')
                return f"{source} ({method})"
                
        return default_source

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
        
        # Historical GPR (Annualized Current Rent)
        historical_gpr = self.analysis.rent_roll_summary.total_annual_rent if self.analysis.rent_roll_summary else 0.0
        self._add_explanation("Historical Gross Potential Rent", ExplainabilityMetadata(
            metric="Historical Gross Potential Rent",
            value=historical_gpr,
            source=ExplanationSource(
                document="Rent Roll",
                fields_used=["Current Rent"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Sum(Current Monthly Rent * 12)",
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

    def _explain_historical_total_expenses(self):
        val = self.analysis.historical_total_expenses or 0.0
        
        # Check if we have detailed historical expenses
        if self.analysis.historical_expenses:
             inputs = {item.mapped_category: item.amount for item in self.analysis.historical_expenses}
             source_doc = "Historical Financials (T12)"
             formula = "Sum(Historical Expense Items)"
             classification = "Sourced"
        else:
             inputs = {"Total Expenses": val}
             source_doc = "Historical Financials"
             formula = "Extracted Total Expenses"
             classification = "Sourced"

        self._add_explanation("Historical Total Operating Expenses", ExplainabilityMetadata(
            metric="Historical Total Operating Expenses",
            value=val,
            source=ExplanationSource(
                document=source_doc,
                fields_used=["Operating Expenses"],
                data_type="Sourced"
            ),
            calculation=ExplanationCalculation(
                formula=formula,
                inputs=inputs
            ),
            adjustments=[],
            classification=classification
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

    def _explain_historical_noi(self):
        val = self.analysis.historical_noi or 0.0
        # Try to reconstruct calculation if components exist, otherwise treat as sourced
        # Note: We don't have historical_egi explicitly stored usually, but we can approximate or just explain the NOI directly if it came from T12
        
        # Assuming NOI is derived from Revenue - Expenses if we calculated it, or sourced if extracted
        # In this system, historical_noi is typically calculated from (Rent Roll Summary Annual Rent - Historical Expenses) or similar proxy
        # But let's check how it's defined in financial_service.py usually.
        # Typically: historical_noi = (rent_roll_summary.total_annual_rent) - historical_total_expenses
        
        revenue = self.analysis.rent_roll_summary.total_annual_rent if self.analysis.rent_roll_summary else 0.0
        expenses = self.analysis.historical_total_expenses or 0.0
        
        self._add_explanation("Historical Net Operating Income (NOI)", ExplainabilityMetadata(
            metric="Historical Net Operating Income (NOI)",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["Historical Revenue", "Historical Expenses"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Historical Revenue - Historical Expenses",
                inputs={
                    "Historical Revenue": revenue,
                    "Historical Expenses": expenses
                }
            ),
            adjustments=["Revenue based on current rent roll annualized"],
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
        
    def _explain_historical_cap_rate(self):
        val = self.analysis.historical_cap_rate or 0.0
        noi = self.analysis.historical_noi or 0.0
        purchase_price = self.analysis.property_meta.purchase_price or 0.0
        
        classification = "Derived"
        adjustments = []
        if purchase_price == 0:
            classification = "Invalid / Not Meaningful"
            adjustments.append("Purchase Price missing")
            
        self._add_explanation("Historical Cap Rate", ExplainabilityMetadata(
            metric="Historical Cap Rate",
            value=val,
            source=ExplanationSource(
                document="Calculation",
                fields_used=["Historical NOI", "Purchase Price"],
                data_type="Derived"
            ),
            calculation=ExplanationCalculation(
                formula="Historical NOI / Purchase Price",
                inputs={
                    "Historical NOI": noi,
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
        
        # Check if user explicitly provided loan amount
        if hasattr(self.params, 'loan_amount') and self.params.loan_amount is not None and self.params.loan_amount > 0:
            formula = "User-Specified Loan Amount"
            inputs = {"Loan Amount": self.params.loan_amount}
            adjustments = ["User manually set loan amount in deal parameters"]
            data_type = "User Input"
        elif purchase_price == 0:
            formula = "Implied Value (NOI / Exit Cap) * LTV"
            noi = self.analysis.pro_forma_noi or 0.0
            exit_cap = self.params.exit_cap_rate
            inputs = {"NOI": noi, "Exit Cap Rate": exit_cap, "LTV": ltv}
            adjustments = ["Purchase Price missing, using Implied Value"]
            data_type = "Derived with Assumptions"
        else:
            formula = "Purchase Price * LTV"
            inputs = {"Purchase Price": purchase_price, "LTV": ltv}
            adjustments = []
            data_type = "Derived with Assumptions"

        self._add_explanation("Loan Amount", ExplainabilityMetadata(
            metric="Loan Amount",
            value=val,
            source=ExplanationSource(
                document="Assumption Engine" if data_type != "User Input" else "User Parameters",
                fields_used=["Purchase Price", "LTV"] if data_type != "User Input" else ["Loan Amount"],
                data_type=data_type
            ),
            calculation=ExplanationCalculation(
                formula=formula,
                inputs=inputs
            ),
            adjustments=adjustments,
            classification=data_type
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

    def _generate_conclusion(self):
        """
        Generates a high-level conclusion and decision impact analysis.
        """
        decisions = []
        
        # 1. Viability Decision
        status = self.analysis.pass_fail_status
        if status == "PASS":
            summary = "The deal meets all preliminary underwriting criteria and shows potential for viable returns."
            decisions.append(DecisionImpact(
                metric="Deal Viability",
                decision="Proceed to Underwriting",
                reasoning="All gating criteria (DSCR, Debt Yield, etc.) were met.",
                impact="The deal qualifies for further due diligence and loan structuring."
            ))
        else:
            reasons = ", ".join(self.analysis.gating_reasons)
            summary = f"The deal does not meet current underwriting standards due to: {reasons}."
            decisions.append(DecisionImpact(
                metric="Deal Viability",
                decision="Declined / Requires Waiver",
                reasoning=f"Failed gating criteria: {reasons}",
                impact="Immediate rejection unless mitigating factors or waivers are applied."
            ))

        # 2. NOI & Operations
        noi_change = (self.analysis.pro_forma_noi or 0) - (self.analysis.historical_noi or 0)
        noi_direction = "increased" if noi_change > 0 else "decreased"
        decisions.append(DecisionImpact(
            metric="Operational Efficiency (NOI)",
            decision=f"Projected NOI {noi_direction} by ${abs(noi_change):,.0f}",
            reasoning="Adjustments made to market rents, vacancy, and expense normalization.",
            impact=f"A {noi_direction} NOI directly affects the valuation and loan amount sizing."
        ))

        # 3. Leverage / Debt Service
        dscr = self.analysis.dscr or 0
        if dscr < 1.0:
            decisions.append(DecisionImpact(
                metric="Debt Service Coverage",
                decision=f"Low DSCR of {dscr:.2f}x",
                reasoning="Net Operating Income is insufficient to cover the proposed debt service.",
                impact="High risk of default; requires lower loan amount or increased equity."
            ))
        elif dscr < 1.25:
            decisions.append(DecisionImpact(
                metric="Debt Service Coverage",
                decision=f"Moderate DSCR of {dscr:.2f}x",
                reasoning="Cash flow is tight but positive.",
                impact="Loan may be sized correctly but leaves little room for operational variance."
            ))
        else:
            decisions.append(DecisionImpact(
                metric="Debt Service Coverage",
                decision=f"Strong DSCR of {dscr:.2f}x",
                reasoning="Healthy margin between NOI and debt obligations.",
                impact="Supports the requested loan amount with lower risk."
            ))

        # 4. Valuation
        cap_rate = self.analysis.cap_rate or 0
        decisions.append(DecisionImpact(
            metric="Valuation (Cap Rate)",
            decision=f"Entry Cap Rate at {cap_rate:.2%}",
            reasoning=f"Based on purchase price of ${self.analysis.property_meta.purchase_price:,.0f} and Pro Forma NOI.",
            impact=f"Reflects the market pricing and initial yield. Compare with market benchmark of {self.params.exit_cap_rate:.2%}."
        ))

        # 5. Investment Checklist
        # Derive answers where possible, otherwise use placeholders
        total_units = self.analysis.property_meta.total_units or 1
        purchase_price = self.analysis.property_meta.purchase_price or 0
        price_per_unit = purchase_price / total_units if total_units > 0 else 0
        
        # Simple logic for "Mismanaged" based on Expense Ratio
        egi = self.analysis.effective_gross_income or 1
        opex = self.analysis.pro_forma_expenses or 0
        exp_ratio = opex / egi if egi > 0 else 0
        mismanaged_status = "Likely (High Expenses)" if exp_ratio > 0.50 else "Stable Operations"
        
        # Logic for "Rents Below Market"
        ltl = self.analysis.loss_to_lease or 0
        gpr = self.analysis.gross_potential_rent or 1
        ltl_pct = ltl / gpr if gpr > 0 else 0
        rents_status = f"Yes ({ltl_pct:.1%} below market)" if ltl_pct > 0.05 else "No (At Market)"
        
        # Vintage check
        year_built = self.analysis.property_meta.year_built or 0
        diligence_note = "None"
        if year_built < 1980:
            diligence_note = f"Structural Inspection Required (Year Built {year_built})"
        
        # Dynamic near_campus determination
        # TODO: Integrate with geocoding API to determine proximity to universities
        address = self.analysis.property_meta.address or ""
        near_campus = self._determine_campus_proximity(address)
        
        # Dynamic primary risks based on deal characteristics
        primary_risks = self._identify_primary_risks()
            
        # Dynamic Source Resolution
        multifamily_source = self._get_source("Total Units", "Offering Memorandum (Unit Count)")
        
        # Check if address came from a specific doc
        address_source = self._get_source("Property Address", "Offering Memorandum")
        campus_source = f"Google Maps Analysis ({address_source})"
        
        # Rent Roll Analysis Sources
        rent_roll_source = "Rent Roll"
        if self.analysis.rent_roll:
            # Check if we have an audit log for rent roll ingestion?
            # Usually rent roll is a whole file, so we default to "Rent Roll"
            pass
            
        checklist = InvestmentChecklist(
            is_multifamily="Yes" if total_units >= 5 else "No (1-4 Units)",
            is_multifamily_source=multifamily_source,
            
            near_campus=near_campus,
            near_campus_source=campus_source,
            
            business_plan=f"Capture ${ltl:,.0f} Loss-to-Lease" if ltl > 0 else "Stabilized Asset Hold",
            business_plan_source="Rent Roll vs Market Rent Analysis",
            
            rents_below_market=rents_status,
            rents_below_market_source="Rent Roll vs Market Rent Analysis",
            
            is_mismanaged=mismanaged_status,
            is_mismanaged_source="Expense Ratio Analysis (T12/Pro Forma)",
            
            diligence_issues=diligence_note,
            diligence_issues_source=f"Property Vintage (Year Built: {year_built})",
            
            primary_risks=primary_risks,
            primary_risks_source="Risk Assessment Model (DSCR, LTV, Age)",
            
            price_per_unit_analysis=f"${price_per_unit:,.0f}/unit",
            price_per_unit_source=f"Calculated from Purchase Price & {multifamily_source}"
        )

        self.analysis.conclusion = Conclusion(
            summary=summary,
            key_decisions=decisions,
            investment_checklist=checklist
        )
    
    def _determine_campus_proximity(self, address: str) -> str:
        """
        Determines if the property is near a university campus.
        Currently uses keyword matching; can be enhanced with geocoding API.
        
        Args:
            address: Property address string
            
        Returns:
            String indicating campus proximity status
        """
        if not address:
            return "Unknown (Address Not Provided)"
        
        # Common university-related keywords
        university_keywords = [
            'university', 'college', 'campus', 'state', 'tech',
            'berkeley', 'stanford', 'ucla', 'usc', 'caltech',
            'mit', 'harvard', 'yale', 'princeton', 'columbia'
        ]
        
        address_lower = address.lower()
        
        # Check for university keywords in address
        for keyword in university_keywords:
            if keyword in address_lower:
                return f"Likely (Address contains '{keyword}')"
        
        # TODO: Integrate with Google Maps API or similar to calculate actual distance
        # Example: Use geocoding to get lat/lng, then calculate distance to nearest universities
        
        return "Unknown (Requires Geocoding Analysis)"
    
    def _identify_primary_risks(self) -> str:
        """
        Dynamically identifies primary risks based on deal characteristics.
        
        Returns:
            Comma-separated string of identified risks
        """
        risks = []
        
        # 1. Interest Rate Risk (based on loan structure)
        interest_rate = self.params.sofr_rate + self.params.bridge_spread
        if interest_rate > 0.06:  # 6%+
            risks.append("High Interest Rate Risk")
        elif self.params.bridge_spread > 0:  # Bridge loan
            risks.append("Interest Rate Volatility")
        
        # 2. Execution Risk (based on loss-to-lease and property condition)
        ltl = self.analysis.loss_to_lease or 0
        gpr = self.analysis.gross_potential_rent or 1
        ltl_pct = ltl / gpr if gpr > 0 else 0
        
        if ltl_pct > 0.15:  # >15% below market
            risks.append("Execution Risk (Significant Rent-Up Required)")
        elif ltl_pct > 0.05:
            risks.append("Moderate Execution Risk")
        
        # 3. Property Age Risk
        year_built = self.analysis.property_meta.year_built or 0
        current_year = 2026  # Could use datetime.now().year
        property_age = current_year - year_built if year_built > 0 else 0
        
        if property_age > 50:
            risks.append("Deferred Maintenance Risk")
        elif property_age > 30:
            risks.append("Capital Expenditure Risk")
        
        # 4. Leverage Risk (based on DSCR and LTV)
        dscr = self.analysis.dscr or 0
        ltv = self.params.ltv
        
        if dscr < 1.15:
            risks.append("Tight Cash Flow / Default Risk")
        
        if ltv > 0.75:
            risks.append("High Leverage Risk")
        
        # 5. Market Risk (based on cap rate spread)
        entry_cap = self.analysis.cap_rate or 0
        exit_cap = self.params.exit_cap_rate
        
        if entry_cap > 0 and exit_cap > 0:
            cap_compression = entry_cap - exit_cap
            if cap_compression < 0:  # Assuming cap rate expansion
                risks.append("Market Valuation Risk")
        
        # 6. Operational Risk (based on expense ratio)
        egi = self.analysis.effective_gross_income or 1
        opex = self.analysis.pro_forma_expenses or 0
        exp_ratio = opex / egi if egi > 0 else 0
        
        if exp_ratio > 0.55:
            risks.append("High Operating Expense Risk")
        
        # Return formatted risk string
        if not risks:
            return "Standard Market Risks"
        
        return ", ".join(risks)