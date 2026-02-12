from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.storage_service import storage_service
from app.services.gemini_client import GeminiClient
from app.models.schemas import UnderwritingAnalysis
from app.db.redis import redis_client
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Gemini Client
# We'll use the fast model for chat to ensure responsiveness
gemini_client = GeminiClient()

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    
class ChatResponse(BaseModel):
    response: str

def format_context_from_analysis(analysis: Dict[str, Any]) -> str:
    """
    Helper to convert analysis dictionary into a full context string for the LLM.
    Ensures 100% of available data (Pro Forma, Historical, Rent Roll, Conclusions) is included.
    """
    try:
        # Extract key sections
        property_meta = analysis.get("property_meta", {})
        rent_roll_summary = analysis.get("rent_roll_summary", {})
        conclusion = analysis.get("conclusion", {}) or {}
        
        # --- 0. Comprehensive Metrics ---
        metrics = {
            # Property
            "purchase_price": property_meta.get("purchase_price"),
            "total_units": property_meta.get("total_units"),
            "year_built": property_meta.get("year_built"),
            "building_size": property_meta.get("building_size"),
            "is_renovated": property_meta.get("is_renovated"),
            "current_loan_balance": property_meta.get("current_loan_balance"),
            
            # Pro Forma - Revenue (Top Line)
            "gross_potential_rent": analysis.get("gross_potential_rent"),
            "loss_to_lease": analysis.get("loss_to_lease"),
            "vacancy_loss": analysis.get("vacancy_loss"),
            "other_income": analysis.get("other_income"),
            "effective_gross_income": analysis.get("effective_gross_income"),
            
            # Pro Forma - Expenses & NOI
            "total_expenses": analysis.get("pro_forma_expenses"),
            "pro_forma_noi": analysis.get("pro_forma_noi"),
            "expense_ratio": 0.0, # Calculated below
            
            # Investment & Debt
            "total_project_cost": analysis.get("total_project_cost"),
            "loan_amount": analysis.get("loan_amount"),
            "equity_invested": analysis.get("equity_invested"),
            "annual_debt_service": analysis.get("annual_debt_service"),
            "cash_flow": analysis.get("cash_flow"),
            
            # Return Metrics
            "cap_rate": analysis.get("cap_rate"),
            "dscr": analysis.get("dscr"),
            "debt_yield": analysis.get("debt_yield"),
            "cash_on_cash": analysis.get("cash_on_cash_return"),
            "irr": analysis.get("irr"),
            "equity_multiple": analysis.get("moic"),
            "yield_on_cost": analysis.get("yield_on_cost"),
            
            # Exit
            "exit_valuation": analysis.get("exit_valuation"),
            "net_sale_proceeds": analysis.get("net_sale_proceeds"),
            
            # Historical
            "historical_noi": analysis.get("historical_noi"),
            "historical_total_expenses": analysis.get("historical_total_expenses"),
            "historical_cap_rate": analysis.get("historical_cap_rate"),
        }
        
        # Calculate Expense Ratio for context
        if metrics.get('effective_gross_income') and metrics.get('effective_gross_income') > 0:
            metrics['expense_ratio'] = (metrics.get('total_expenses') or 0) / metrics.get('effective_gross_income')

        gating = {
            "status": analysis.get("pass_fail_status"),
            "reasons": analysis.get("gating_reasons", [])
        }

        # --- 1. Unit Mix Summary ---
        unit_mix = analysis.get("unit_mix_summary", [])
        unit_mix_str = "No unit mix data available."
        if unit_mix:
            unit_mix_str = "| Unit Type | Count | Avg Rent | Market Rent |\n|---|---|---|---|\n"
            for u in unit_mix:
                u_type = u.get('unit_type', 'Unknown')
                count = u.get('count', 0)
                avg = u.get('avg_rent', 0)
                mkt = u.get('market_rent', 0)
                unit_mix_str += f"| {u_type} | {count} | ${avg:,.0f} | ${mkt:,.0f} |\n"

        # --- 2. Detailed Expenses (Pro Forma) ---
        expenses = analysis.get("pro_forma_expenses_detailed", [])
        expenses_str = "No detailed expenses available."
        if expenses:
            expenses_str = "| Expense Category | Amount |\n|---|---|\n"
            for e in expenses:
                name = e.get('name', 'Unknown')
                amt = e.get('amount', 0)
                expenses_str += f"| {name} | ${amt:,.0f} |\n"

        # --- 3. Historical Expenses (T12 Actuals) ---
        hist_expenses = analysis.get("historical_expenses", [])
        hist_str = "No historical expenses available."
        hist_full_str = ""
        if hist_expenses:
             # Aggregated View
             hist_map = {}
             for h in hist_expenses:
                 cat = h.get('mapped_category', 'Uncategorized')
                 amt = h.get('amount', 0)
                 hist_map[cat] = hist_map.get(cat, 0) + amt
            
             hist_str = "| T12 Category | Amount |\n|---|---|\n"
             for cat, amt in hist_map.items():
                 hist_str += f"| {cat} | ${amt:,.0f} |\n"
             
             # Full Normalized Data View
             hist_full_str = "| Original Text | Mapped Category | Amount | Year | Source | Confidence | Verified | Notes |\n|---|---|---|---|---|---|---|---|\n"
             for h in hist_expenses:
                 orig = str(h.get('original_text', '')).replace('|', ' ')
                 cat = h.get('mapped_category', 'Uncategorized')
                 amt = h.get('amount', 0)
                 year = h.get('expense_year', 'N/A')
                 src = str(h.get('source_document', 'N/A')).replace('|', ' ')
                 conf = h.get('confidence', 0)
                 verified = "Yes" if h.get('user_verified') else "No"
                 notes = str(h.get('audit_log', {}).get('method', '')).replace('|', ' ')
                 hist_full_str += f"| {orig} | {cat} | ${amt:,.2f} | {year} | {src} | {conf:.2f} | {verified} | {notes} |\n"

        # --- 3b. Rent Roll (Full Extended) ---
        rent_roll = analysis.get("rent_roll", [])
        rent_roll_full_str = "No individual rent roll data available."
        if rent_roll:
             rent_roll_full_str = "| Unit | Type | Tenant | Current | Market | Stabilized | SqFt | Start | End | Move In | Deposit | Notes |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n"
             for item in rent_roll:
                 u = str(item.get('unit_number', 'N/A')).replace('|', ' ')
                 t = str(item.get('unit_type', 'N/A')).replace('|', ' ')
                 tn = str(item.get('tenant_name', 'N/A')).replace('|', ' ')
                 cr = item.get('current_rent', 0)
                 mr = item.get('market_rent', 0)
                 sr = item.get('stabilized_rent', 0)
                 sf = item.get('unit_size', 0)
                 ls = str(item.get('lease_start') or 'N/A').replace('|', ' ')
                 le = str(item.get('lease_end') or 'N/A').replace('|', ' ')
                 mi = str(item.get('move_in_date') or 'N/A').replace('|', ' ')
                 dep = item.get('deposit', 0)
                 notes = str(item.get('comments') or '').replace('|', ' ')
                 rent_roll_full_str += f"| {u} | {t} | {tn} | ${cr:,.0f} | ${mr:,.0f} | ${sr:,.0f} | {sf} | {ls} | {le} | {mi} | ${dep:,.0f} | {notes} |\n"

        # --- 3c. Deal Parameters (Assumptions) ---
        params = analysis.get("deal_parameters", {})
        student_config = analysis.get("student_housing_config")
        params_str = "No deal parameters available."
        if params:
             params_str = json.dumps(params, indent=2)
        
        if student_config:
             params_str += "\n\n== STUDENT HOUSING CONFIG ==\n" + json.dumps(student_config, indent=2)

        # --- 3d. OM Pro Forma Data ---
        om_data = analysis.get("om_proforma", [])
        tax_assumptions = analysis.get("tax_assumptions")
        om_str = "No OM Pro Forma data extracted."
        if om_data:
             om_str = json.dumps(om_data, indent=2)
        
        if tax_assumptions:
             om_str += "\n\n== OM TAX ASSUMPTIONS ==\n" + json.dumps(tax_assumptions, indent=2)

        # --- 4. Sensitivity Analysis Matrix ---
        sens = analysis.get("sensitivity_analysis", {})
        sens_str = "No sensitivity analysis available."
        if sens and 'rows' in sens and 'columns' in sens and 'values' in sens:
            cols = sens['columns']
            rows = sens['rows']
            vals = sens['values']
            
            header = "| Exit Cap \\ Growth | " + " | ".join([f"{c:.1%}" for c in cols]) + " |\n"
            separator = "|---|" + "|".join(["---" for _ in cols]) + "|\n"
            
            body = ""
            for i, r_val in enumerate(rows):
                row_label = f"{r_val:.2%}"
                if i < len(vals):
                    row_data = " | ".join([f"{v:.2%}" for v in vals[i]])
                    body += f"| {row_label} | {row_data} |\n"
            
            sens_str = header + separator + body

        # --- 5. Strategic Conclusions & Checklist ---
        investment_checklist = conclusion.get("investment_checklist", {})
        key_decisions = conclusion.get("key_decisions", [])
        
        checklist_str = "No checklist available."
        if investment_checklist:
            checklist_str = json.dumps(investment_checklist, indent=2)
            
        decisions_str = "No key decisions recorded."
        if key_decisions:
            decisions_str = "| Metric | Decision | Reasoning | Impact |\n|---|---|---|---|\n"
            for d in key_decisions:
                m = d.get('metric', 'N/A')
                dec = d.get('decision', 'N/A')
                res = d.get('reasoning', 'N/A')
                imp = d.get('impact', 'N/A')
                decisions_str += f"| {m} | {dec} | {res} | {imp} |\n"

        # --- 6. Audit Log (Data Provenance) ---
        audit_trail = analysis.get("audit_trail", [])
        audit_str = "No audit trail available."
        if audit_trail:
            audit_str = "| Field | Value | Source | Method | Confidence | Page |\n|---|---|---|---|---|---|\n"
            for item in audit_trail:
                field = item.get('field_name', 'Unknown')
                val = str(item.get('extracted_value', 'N/A')).replace('|', ' ')
                src = item.get('source', 'Unknown')
                method = item.get('method', 'Unknown')
                conf = item.get('confidence_score')
                page = item.get('page_number', 'N/A')
                
                conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "N/A"
                
                audit_str += f"| {field} | {val} | {src} | {method} | {conf_str} | {page} |\n"

        # Format as readable text
        context = f"""
        == PROPERTY DETAILS ==
        Property Name: {property_meta.get("property_name", "Unknown")}
        Address: {property_meta.get("address", "Unknown")}
        Units: {metrics.get("total_units", "N/A")}
        Year Built: {metrics.get("year_built", "N/A")}
        Building Size: {metrics.get("building_size", 0):,.0f} SqFt
        Renovated: {metrics.get("is_renovated", False)}
        Current Loan Balance: ${metrics.get("current_loan_balance", 0):,.2f}
        
        == FINANCIAL SUMMARY (PRO FORMA) ==
        Purchase Price: ${metrics.get("purchase_price", 0):,.2f}
        Total Project Cost: ${metrics.get("total_project_cost", 0):,.2f}
        Equity Invested: ${metrics.get("equity_invested", 0):,.2f}
        
        Loan Amount: ${metrics.get("loan_amount", 0):,.2f}
        Annual Debt Service: ${metrics.get("annual_debt_service", 0):,.2f}
        
        Gross Potential Rent: ${metrics.get("gross_potential_rent", 0):,.2f}
        - Loss to Lease: ${metrics.get("loss_to_lease", 0):,.2f}
        - Vacancy Loss: ${metrics.get("vacancy_loss", 0):,.2f}
        + Other Income: ${metrics.get("other_income", 0):,.2f}
        = Effective Gross Income: ${metrics.get("effective_gross_income", 0):,.2f}
        
        - Total Expenses: ${metrics.get("total_expenses", 0):,.2f} (Ratio: {metrics.get("expense_ratio", 0):.1%})
        = Net Operating Income (NOI): ${metrics.get("pro_forma_noi", 0):,.2f}
        
        - Annual Debt Service: ${metrics.get("annual_debt_service", 0):,.2f}
        = Cash Flow: ${metrics.get("cash_flow", 0):,.2f}
        
        == RETURN METRICS ==
        Cap Rate (Entry): {metrics.get("cap_rate", 0):.2%}
        Yield on Cost: {metrics.get("yield_on_cost", 0):.2%}
        DSCR: {metrics.get("dscr", 0):.2f}x
        Debt Yield: {metrics.get("debt_yield", 0):.2%}
        Cash-on-Cash: {metrics.get("cash_on_cash", 0):.2%}
        IRR (5-Year): {metrics.get("irr", 0):.2%}
        Equity Multiple: {metrics.get("equity_multiple", 0):.2f}x
        
        == EXIT ASSUMPTIONS ==
        Exit Valuation: ${metrics.get("exit_valuation", 0):,.2f}
        Net Sale Proceeds: ${metrics.get("net_sale_proceeds", 0):,.2f}
        
        == HISTORICAL PERFORMANCE (T12) ==
        Historical NOI: ${metrics.get("historical_noi", 0):,.2f}
        Historical Total Expenses: ${metrics.get("historical_total_expenses", 0):,.2f}
        Historical Cap Rate: {metrics.get("historical_cap_rate", 0):.2%}
        
        == UNIT MIX SUMMARY ==
        {unit_mix_str}

        == PRO FORMA EXPENSES (DETAILED) ==
        {expenses_str}

        == HISTORICAL EXPENSES (AGGREGATED) ==
        {hist_str}

        == HISTORICAL EXPENSES (FULL NORMALIZED DATA) ==
        {hist_full_str}

        == FULL RENT ROLL DATA (EXTENDED) ==
        {rent_roll_full_str}

        == DEAL PARAMETERS (ASSUMPTIONS) ==
        {params_str}

        == OM PRO FORMA (EXTRACTED) ==
        {om_str}

        == SENSITIVITY ANALYSIS (IRR) ==
        {sens_str}
        
        == STRATEGIC ANALYSIS ==
        -- Checklist --
        {checklist_str}
        
        -- Key Decisions --
        {decisions_str}
        
        -- Analyst Commentary --
        {analysis.get("analyst_commentary", "No commentary available.")}

        == AUDIT LOG (DATA PROVENANCE) ==
        {audit_str}
        
        == RENT ROLL SUMMARY ==
        Occupancy: {rent_roll_summary.get("occupancy_rate", 0):.1%}
        Avg Rent/Unit: ${rent_roll_summary.get("avg_rent_per_unit", 0):,.2f}
        Total Annual Rent: ${rent_roll_summary.get("total_annual_rent", 0):,.2f}
        
        == UNDERWRITING STATUS ==
        Flow: {analysis.get("underwriting_flow", "Unknown")}
        Status: {gating.get("status")}
        Gating Issues: {", ".join(gating.get("reasons", []))}
        
        == INVESTMENT MEMO SUMMARY ==
        {analysis.get("investment_memo", "No memo generated yet.")[:4000]}
        
        == EXPLAINABILITY (CALCULATION LOGIC) ==
        {json.dumps(analysis.get("explainability", {}), indent=2)}
        """
        return context
    except Exception as e:
        logger.error(f"Error formatting context: {e}")
        return "Error extracting context from report."

@router.post("/analysis/{document_id}/chat")
async def chat_with_report(
    document_id: str,
    request: ChatRequest,
    storage: Any = Depends(lambda: storage_service)
):
    """
    Chat endpoint for a specific analysis report.
    Provides context-aware responses based on the analysis data.
    Uses Redis caching to store the formatted context for faster subsequent turns.
    RETURNS: StreamingResponse (Server-Sent Events)
    """
    logger.info(f"Chat request for document: {document_id}")
    
    # 0. Check Redis Cache for Context
    cache_key = f"chat_context:{document_id}"
    context_str = None
    
    try:
        if redis_client.client:
            context_str = await redis_client.get(cache_key)
            if context_str:
                logger.info(f"Using cached context for {document_id}")
    except Exception as e:
        logger.warning(f"Redis get failed: {e}")

    # 1. Fetch Analysis Data (if not cached)
    if not context_str:
        analysis_data = await storage.get_analysis_result(document_id)
        if not analysis_data:
            raise HTTPException(status_code=404, detail="Analysis report not found. Please wait for analysis to complete.")
        
        # 2. Build Context
        context_str = format_context_from_analysis(analysis_data)
        
        # Cache it (expire in 1 hour)
        try:
            if redis_client.client:
                await redis_client.set(cache_key, context_str, expire=3600)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
    
    # 3. Build Prompt
    system_instruction = """
    You are the "Valiance Financial Assistant", an expert real estate underwriter.
    You are currently discussing a specific deal report with the user.
    
    RULES:
    1. STRICTLY restrict your answers to the provided "REPORT CONTEXT". You have access to detailed financials, unit mix, and risk matrices.
    2. If the user asks about something not in the report, politely say you don't have that information in the current analysis.
    3. Be concise, professional, and analytical. Use the provided tables to answer specific questions about expenses or unit counts.
    4. You can explain general real estate concepts if asked (e.g., "What is a Cap Rate?"), but always tie it back to the current deal's numbers if applicable.
    5. Format your response with Markdown for readability (bold key numbers, lists, tables).
    """
    
    # Format history (last 10 messages max to fit context window)
    history_str = ""
    for msg in request.messages[-10:]:
        role_label = "User" if msg.role == "user" else "Assistant"
        history_str += f"{role_label}: {msg.content}\n"
    
    full_prompt = f"""
    {system_instruction}
    
    ====== REPORT CONTEXT ======
    {context_str}
    ===========================
    
    ====== CHAT HISTORY ======
    {history_str}
    
    Assistant:
    """
    
    # 4. Generate Response Stream
    async def event_generator():
        try:
            async for chunk in gemini_client.generate_content_stream_async(full_prompt, use_fast_model=True):
                 # Format as SSE data
                 data = json.dumps({"token": chunk})
                 yield f"data: {data}\n\n"
        except Exception as e:
             logger.error(f"Chat stream failed: {e}")
             err_data = json.dumps({"error": str(e)})
             yield f"data: {err_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")