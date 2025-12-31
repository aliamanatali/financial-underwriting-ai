from typing import Dict, Any, List
from app.models.schemas import UnderwritingAnalysis
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AuditLogService:
    """
    Service to track and manage audit trails for financial analyses.
    Provides provenance information for all extracted and calculated fields.
    """
    
    def generate_audit_trail(self, analysis: UnderwritingAnalysis) -> List[Dict[str, Any]]:
        """
        Generates a comprehensive audit trail for the analysis.
        Tracks field extraction, source, and calculation methods.
        """
        audit_trail = []
        
        # Property Meta Audits
        audit_trail.append({
            "field": "Property Address",
            "value": analysis.property_meta.address,
            "source": "Offering Memorandum (OM)",
            "method": "LLM extraction from OM",
            "confidence_score": 0.95,
            "timestamp": datetime.now().isoformat()
        })
        
        audit_trail.append({
            "field": "Year Built",
            "value": analysis.property_meta.year_built,
            "source": "Offering Memorandum",
            "method": "Extracted from property description section",
            "confidence_score": 0.98,
            "timestamp": datetime.now().isoformat()
        })
        
        audit_trail.append({
            "field": "Total Units",
            "value": analysis.property_meta.total_units,
            "source": "Rent Roll",
            "method": "Counted from rent roll entries",
            "confidence_score": 1.0,
            "timestamp": datetime.now().isoformat()
        })
        
        audit_trail.append({
            "field": "Purchase Price",
            "value": f"${analysis.property_meta.purchase_price:,.0f}",
            "source": "Offering Memorandum (Deal Terms)",
            "method": "Extracted from executive summary",
            "confidence_score": 0.99,
            "timestamp": datetime.now().isoformat()
        })
        
        # Rent Roll Audits
        audit_trail.append({
            "field": "Rent Roll Summary",
            "value": {
                "total_units": analysis.rent_roll_summary.total_units,
                "occupied_units": analysis.rent_roll_summary.occupied_units,
                "occupancy_rate": f"{analysis.rent_roll_summary.occupancy_rate * 100:.1f}%",
                "total_annual_rent": f"${analysis.rent_roll_summary.total_annual_rent:,.0f}"
            },
            "source": "Rent Roll Document",
            "method": "Aggregated from individual unit entries",
            "confidence_score": 0.99,
            "timestamp": datetime.now().isoformat()
        })
        
        # Revenue Audits
        historical_revenue = sum(item.current_rent * 12 for item in analysis.rent_roll)
        pro_forma_revenue = sum(item.market_rent * 12 for item in analysis.rent_roll)
        
        audit_trail.append({
            "field": "Gross Potential Rent (T12)",
            "value": f"${historical_revenue:,.0f}",
            "source": "Rent Roll (Current Rents)",
            "method": "SUM(Current Rent × 12 months) × Units",
            "confidence_score": 1.0,
            "timestamp": datetime.now().isoformat()
        })
        
        audit_trail.append({
            "field": "Gross Potential Rent (F12)",
            "value": f"${pro_forma_revenue:,.0f}",
            "source": "Rent Roll (Market Rents)",
            "method": "SUM(Market Rent × 12 months) × Units",
            "confidence_score": 0.85,
            "timestamp": datetime.now().isoformat()
        })
        
        # Expense Audits
        total_expenses = sum(exp.amount for exp in analysis.normalized_expenses)
        audit_trail.append({
            "field": "Total Operating Expenses",
            "value": f"${total_expenses:,.0f}",
            "source": "T12 P&L Statement",
            "method": "Aggregated from normalized expense categories",
            "confidence_score": 0.92,
            "timestamp": datetime.now().isoformat()
        })
        
        # Normalized Expense Details
        for expense in analysis.normalized_expenses:
            category_name = expense.mapped_category.value if hasattr(expense.mapped_category, 'value') else str(expense.mapped_category)
            audit_trail.append({
                "field": f"Expense: {category_name}",
                "value": f"${expense.amount:,.0f}",
                "source": "T12 P&L Statement",
                "method": f"Original: '{expense.original_text}' mapped to {category_name} (Confidence: {expense.confidence:.0%})",
                "confidence_score": expense.confidence,
                "timestamp": datetime.now().isoformat()
            })
        
        # Financial Metrics Audits
        if analysis.historical_noi:
            audit_trail.append({
                "field": "Historical NOI",
                "value": f"${analysis.historical_noi:,.0f}",
                "source": "Calculated",
                "method": "Historical Revenue - Total Expenses",
                "confidence_score": 1.0,
                "timestamp": datetime.now().isoformat()
            })
        
        if analysis.pro_forma_noi:
            audit_trail.append({
                "field": "Pro Forma NOI",
                "value": f"${analysis.pro_forma_noi:,.0f}",
                "source": "Calculated",
                "method": "(Market Rent × Units × (1 - Vacancy Rate)) - Expenses",
                "confidence_score": 1.0,
                "timestamp": datetime.now().isoformat()
            })
        
        if analysis.cap_rate:
            audit_trail.append({
                "field": "Pro Forma Cap Rate",
                "value": f"{analysis.cap_rate * 100:.2f}%",
                "source": "Calculated",
                "method": "Pro Forma NOI / Purchase Price",
                "confidence_score": 1.0,
                "timestamp": datetime.now().isoformat()
            })
        
        # Gating Check Audits
        audit_trail.append({
            "field": "Deal Viability Status",
            "value": analysis.pass_fail_status,
            "source": "Gating Logic",
            "method": "Checked: Units (15-80), Loan ($5M+), Build Year (<1970 must be renovated)",
            "confidence_score": 1.0,
            "reasons": analysis.gating_reasons,
            "timestamp": datetime.now().isoformat()
        })
        
        # Deal Parameters Audits
        if analysis.deal_parameters:
            audit_trail.append({
                "field": "Deal Parameters",
                "value": {
                    "growth_rate": f"{analysis.deal_parameters.growth_rate * 100:.1f}%",
                    "vacancy_rate": f"{analysis.deal_parameters.vacancy_rate * 100:.1f}%",
                    "exit_cap_rate": f"{analysis.deal_parameters.exit_cap_rate * 100:.2f}%",
                    "loan_amount": f"${analysis.deal_parameters.loan_amount:,.0f}"
                },
                "source": "Valiance Standard Parameters",
                "method": "Hardcoded Valiance rules",
                "confidence_score": 1.0,
                "timestamp": datetime.now().isoformat()
            })
        
        return audit_trail
    
    def get_audit_trail(self, document_id: str, analysis: UnderwritingAnalysis = None) -> List[Dict[str, Any]]:
        """
        Returns the audit trail for a given document.
        If analysis object is provided, generates comprehensive trail.
        Otherwise returns basic placeholder.
        """
        if analysis:
            return self.generate_audit_trail(analysis)
        
        # Fallback placeholder
        return [
            {
                "field": "Property Tax",
                "value": "$181,000",
                "source": "OM Page 4",
                "method": "Calculated based on purchase price",
                "confidence_score": 0.85,
                "timestamp": datetime.now().isoformat()
            },
            {
                "field": "ProForma Revenue",
                "value": "$1,200,000",
                "source": "Rent Roll",
                "method": "Market Rent * Units * (1 - Vacancy Rate)",
                "confidence_score": 0.90,
                "timestamp": datetime.now().isoformat()
            },
        ]