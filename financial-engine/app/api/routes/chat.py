from fastapi import APIRouter, Depends, HTTPException, Body
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
    """
    try:
        # Extract key sections
        property_meta = analysis.get("property_meta", {})
        rent_roll_summary = analysis.get("rent_roll_summary", {})
        financial_metrics = {
            "pro_forma_noi": analysis.get("pro_forma_noi"),
            "cap_rate": analysis.get("cap_rate"),
            "dscr": analysis.get("dscr"),
            "debt_yield": analysis.get("debt_yield"),
            "cash_on_cash": analysis.get("cash_on_cash_return"),
            "irr": analysis.get("irr"),
            "equity_multiple": analysis.get("moic"),
            "purchase_price": property_meta.get("purchase_price"),
            "total_units": property_meta.get("total_units"),
        }
        
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
        # Aggregated by category to give context on "actuals" vs "pro forma"
        hist_expenses = analysis.get("historical_expenses", [])
        hist_str = "No historical expenses available."
        if hist_expenses:
             hist_map = {}
             for h in hist_expenses:
                 cat = h.get('mapped_category', 'Uncategorized')
                 amt = h.get('amount', 0)
                 hist_map[cat] = hist_map.get(cat, 0) + amt
            
             hist_str = "| T12 Category | Amount |\n|---|---|\n"
             for cat, amt in hist_map.items():
                 hist_str += f"| {cat} | ${amt:,.0f} |\n"

        # --- 4. Sensitivity Analysis Matrix ---
        sens = analysis.get("sensitivity_analysis", {})
        sens_str = "No sensitivity analysis available."
        if sens and 'rows' in sens and 'columns' in sens and 'values' in sens:
            # Header: | Exit Cap \ Growth | 2% | 3% | 4% |
            cols = sens['columns'] # e.g. [0.02, 0.03, 0.04]
            rows = sens['rows']    # e.g. [0.055, 0.06, 0.065]
            vals = sens['values']  # Matrix
            
            header = "| Exit Cap \\ Growth | " + " | ".join([f"{c:.1%}" for c in cols]) + " |\n"
            separator = "|---|" + "|".join(["---" for _ in cols]) + "|\n"
            
            body = ""
            for i, r_val in enumerate(rows):
                row_label = f"{r_val:.2%}"
                if i < len(vals):
                    row_data = " | ".join([f"{v:.2%}" for v in vals[i]])
                    body += f"| {row_label} | {row_data} |\n"
            
            sens_str = header + separator + body

        # Format as readable text
        context = f"""
        == PROPERTY DETAILS ==
        Address: {property_meta.get("address", "Unknown")}
        Units: {property_meta.get("total_units", "N/A")}
        Year Built: {property_meta.get("year_built", "N/A")}
        
        == FINANCIAL METRICS (PRO FORMA) ==
        Purchase Price: ${financial_metrics.get("purchase_price", 0):,.2f}
        NOI: ${financial_metrics.get("pro_forma_noi", 0):,.2f}
        Cap Rate: {financial_metrics.get("cap_rate", 0):.2%}
        DSCR: {financial_metrics.get("dscr", 0):.2f}x
        Debt Yield: {financial_metrics.get("debt_yield", 0):.2%}
        Cash-on-Cash: {financial_metrics.get("cash_on_cash", 0):.2%}
        IRR: {financial_metrics.get("irr", 0):.2%}
        Equity Multiple: {financial_metrics.get("equity_multiple", 0):.2f}x
        
        == UNIT MIX SUMMARY ==
        {unit_mix_str}

        == PRO FORMA EXPENSES (DETAILED) ==
        {expenses_str}

        == HISTORICAL EXPENSES (T12 ACTUALS) ==
        {hist_str}

        == SENSITIVITY ANALYSIS (IRR) ==
        {sens_str}
        
        == RENT ROLL SUMMARY ==
        Occupancy: {rent_roll_summary.get("occupancy_rate", 0):.1%}
        Avg Rent/Unit: ${rent_roll_summary.get("avg_rent_per_unit", 0):,.2f}
        Total Annual Rent: ${rent_roll_summary.get("total_annual_rent", 0):,.2f}
        
        == UNDERWRITING STATUS ==
        Status: {gating.get("status")}
        Gating Issues: {", ".join(gating.get("reasons", []))}
        
        == INVESTMENT MEMO SUMMARY ==
        {analysis.get("investment_memo", "No memo generated yet.")[:4000]}
        """
        return context
    except Exception as e:
        logger.error(f"Error formatting context: {e}")
        return "Error extracting context from report."

@router.post("/analysis/{document_id}/chat", response_model=ChatResponse)
async def chat_with_report(
    document_id: str,
    request: ChatRequest,
    storage: Any = Depends(lambda: storage_service)
):
    """
    Chat endpoint for a specific analysis report.
    Provides context-aware responses based on the analysis data.
    Uses Redis caching to store the formatted context for faster subsequent turns.
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
    
    # 4. Generate Response
    # Use fast model for chat to ensure good UX
    try:
        response_text = await gemini_client.generate_content_async(full_prompt, use_fast_model=True)
        return ChatResponse(response=response_text)
    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")