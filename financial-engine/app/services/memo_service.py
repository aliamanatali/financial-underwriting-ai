from typing import Dict, Any
from app.models.schemas import UnderwritingAnalysis
import logging

logger = logging.getLogger(__name__)

class MemoService:
    def __init__(self, gemini_service: "GeminiService" = None):
        self.gemini_service = gemini_service

    def generate_investment_memo(self, analysis_data: UnderwritingAnalysis) -> str:
        """
        Generates a markdown-formatted investment memo using an LLM.
        Falls back to template if LLM is unavailable.
        """
        try:
            if self.gemini_service:
                memo_content = self._generate_memo_with_llm(analysis_data)
            else:
                memo_content = self._generate_memo_template(analysis_data)
            return memo_content
        except Exception as e:
            logger.error(f"Error generating memo: {e}. Falling back to template.")
            return self._generate_memo_template(analysis_data)

    def _generate_memo_with_llm(self, analysis_data: UnderwritingAnalysis) -> str:
        """
        Uses LLM to generate a sophisticated investment memo.
        """
        # Calculate metrics
        cap_rate = analysis_data.cap_rate * 100 if analysis_data.cap_rate else 0
        historical_cap_rate = analysis_data.historical_cap_rate * 100 if analysis_data.historical_cap_rate else 0
        occupancy_rate = analysis_data.rent_roll_summary.occupancy_rate * 100
        upside = cap_rate - historical_cap_rate
        
        prompt = f"""
        Write a professional investment memo for a real estate deal with the following details:
        
        Property: {analysis_data.property_meta.address}
        Year Built: {analysis_data.property_meta.year_built}
        Total Units: {analysis_data.property_meta.total_units}
        Current Occupancy: {occupancy_rate:.1f}%
        Current Cap Rate: {historical_cap_rate:.2f}%
        Pro Forma Cap Rate: {cap_rate:.2f}%
        Upside Potential: {upside:.2f}%
        
        Deal Status: {'PASS' if analysis_data.pass_fail_status == 'PASS' else 'FAIL'}

        Investment Checklist:
        - Multifamily? {analysis_data.conclusion.investment_checklist.is_multifamily if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Near Campus? {analysis_data.conclusion.investment_checklist.near_campus if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Business Plan: {analysis_data.conclusion.investment_checklist.business_plan if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Below Market Rents? {analysis_data.conclusion.investment_checklist.rents_below_market if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Mismanaged? {analysis_data.conclusion.investment_checklist.is_mismanaged if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Diligence Issues: {analysis_data.conclusion.investment_checklist.diligence_issues if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Primary Risks: {analysis_data.conclusion.investment_checklist.primary_risks if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        - Price Per Unit: {analysis_data.conclusion.investment_checklist.price_per_unit_analysis if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'}
        
        Include the following sections:
        1. Executive Summary (2-3 sentences)
        2. Investment Checklist & Questions (Address the items above)
        3. Key Questions:
           - Is there upside potential? (Answer: Yes, upside of {upside:.2f}%)
           - What are the primary risks?
           - What is the value-add strategy?
        4. SWOT Analysis (Strengths, Weaknesses, Opportunities, Threats)
        4. Investment Highlights
        5. Risk Mitigation
        
        Write in professional, concise language suitable for an investment committee.
        
        IMPORTANT: Return ONLY the memo content in valid Markdown. Do not include any introductory text like "Here is the memo" or "Based on the details provided". Start directly with the # INVESTMENT MEMO title.
        """
        
        try:
            memo = self.gemini_service.generate_content(prompt)
            return memo
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def _generate_memo_template(self, analysis_data: UnderwritingAnalysis) -> str:
        """
        Generates a template-based memo (fallback).
        """
        cap_rate = analysis_data.cap_rate * 100 if analysis_data.cap_rate else 0
        historical_cap_rate = analysis_data.historical_cap_rate * 100 if analysis_data.historical_cap_rate else 0
        occupancy_rate = analysis_data.rent_roll_summary.occupancy_rate * 100
        upside = cap_rate - historical_cap_rate
        noi = analysis_data.pro_forma_noi if analysis_data.pro_forma_noi else 0
        
        memo = f"""# INVESTMENT MEMO

## Property: {analysis_data.property_meta.address}

### EXECUTIVE SUMMARY
This {analysis_data.property_meta.total_units}-unit multifamily asset presents a compelling value-add opportunity with strong fundamentals and clear path to value creation. Current occupancy is {occupancy_rate:.1f}% with Pro Forma cap rate of {cap_rate:.2f}%.

---

## INVESTMENT CHECKLIST

| Question | Status |
|----------|--------|
| **Is the property a multifamily investment?** | {analysis_data.conclusion.investment_checklist.is_multifamily if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Is it within 6 blocks of campus?** | {analysis_data.conclusion.investment_checklist.near_campus if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **What is the business plan to capture value?** | {analysis_data.conclusion.investment_checklist.business_plan if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Are existing rents below market?** | {analysis_data.conclusion.investment_checklist.rents_below_market if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Is it poorly run/mismanaged?** | {analysis_data.conclusion.investment_checklist.is_mismanaged if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **What diligence items remain unresolved?** | {analysis_data.conclusion.investment_checklist.diligence_issues if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **What are the primary risks?** | {analysis_data.conclusion.investment_checklist.primary_risks if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |
| **Price Per Unit Analysis** | {analysis_data.conclusion.investment_checklist.price_per_unit_analysis if analysis_data.conclusion and analysis_data.conclusion.investment_checklist else 'Unknown'} |

## KEY QUESTIONS

### Is there upside potential?
**YES** – The deal presents an upside potential of **{upside:.2f}%**, with opportunity to increase cap rate from {historical_cap_rate:.2f}% to {cap_rate:.2f}%.

**Pro Forma NOI: ${noi:,.0f}**
**Pro Forma Cap Rate: {cap_rate:.2f}%**

### What are the primary risks?
- **Market Risk**: Economic downturn could impact rental demand and vacancy rates.
- **Interest Rate Risk**: Rising rates could affect refinance and acquisition financing.
- **Operational Risk**: Asset management execution is critical to achieving projections.
- **Structural/Physical Risk**: Building age ({analysis_data.property_meta.year_built}) requires ongoing capital reserves for maintenance.

### What is the value-add strategy?
1. **Rent Growth**: Market rent achievement through tenant turnover and lease-ups.
2. **Expense Optimization**: Implement cost controls and operational efficiencies.
3. **Capital Improvements**: Strategic CapEx to improve NOI and rents.
4. **Occupancy Stabilization**: Reduce vacancy through targeted marketing and tenant retention.

---

## SWOT ANALYSIS

### Strengths
✓ {analysis_data.property_meta.total_units}-unit portfolio provides diversified revenue base
✓ Strong current occupancy rate of {occupancy_rate:.1f}%
✓ Potential for above-market rent growth
✓ Established property with proven operations

### Weaknesses
✗ Property age ({analysis_data.property_meta.year_built}) may require capital reserves
✗ Limited upside without rent growth execution
✗ Market-dependent tenant demand

### Opportunities
→ Market rent achievement upside of {upside:.2f}%
→ Operational efficiencies and cost reduction
→ Value-add capital improvements
→ Favorable financing environment for refinance

### Threats
← Economic recession impacting rents and occupancy
← Rising operating expenses and inflation
← Increased competition from new supply
← Interest rate increases impacting cap rates

---

## INVESTMENT HIGHLIGHTS

• **Strong Fundamentals**: {occupancy_rate:.1f}% occupancy with stable tenant base
• **Clear Value Creation Path**: {upside:.2f}% upside to pro forma cap rate
• **Market Opportunity**: Location supports rent growth and market rate achievement
• **Proven Asset Class**: Multifamily provides stable cash flow and inflation hedge

---

## DEAL STATUS: {analysis_data.pass_fail_status}

{f'**GATING CONCERNS**: {", ".join(analysis_data.gating_reasons)}' if analysis_data.gating_reasons else '✓ Deal passes all gating criteria'}

"""
        return memo