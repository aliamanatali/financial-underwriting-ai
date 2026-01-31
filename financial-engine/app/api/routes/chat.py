from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.storage_service import storage_service
from app.services.gemini_client import GeminiClient
from app.models.schemas import UnderwritingAnalysis
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
    Helper to convert analysis dictionary into a context string for the LLM.
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
        
        # Format as readable text
        context = f"""
        == PROPERTY DETAILS ==
        Address: {property_meta.get("address", "Unknown")}
        Units: {property_meta.get("total_units", "N/A")}
        Year Built: {property_meta.get("year_built", "N/A")}
        
        == FINANCIAL METRICS ==
        Purchase Price: ${financial_metrics.get("purchase_price", 0):,.2f}
        NOI (Pro Forma): ${financial_metrics.get("pro_forma_noi", 0):,.2f}
        Cap Rate: {financial_metrics.get("cap_rate", 0):.2%}
        DSCR: {financial_metrics.get("dscr", 0):.2f}x
        Debt Yield: {financial_metrics.get("debt_yield", 0):.2%}
        Cash-on-Cash: {financial_metrics.get("cash_on_cash", 0):.2%}
        IRR: {financial_metrics.get("irr", 0):.2%}
        Equity Multiple: {financial_metrics.get("equity_multiple", 0):.2f}x
        
        == RENT ROLL SUMMARY ==
        Occupancy: {rent_roll_summary.get("occupancy_rate", 0):.1%}
        Avg Rent/Unit: ${rent_roll_summary.get("avg_rent_per_unit", 0):,.2f}
        Total Annual Rent: ${rent_roll_summary.get("total_annual_rent", 0):,.2f}
        
        == UNDERWRITING STATUS ==
        Status: {gating.get("status")}
        Gating Issues: {", ".join(gating.get("reasons", []))}
        
        == INVESTMENT MEMO SUMMARY ==
        {analysis.get("investment_memo", "No memo generated yet.")[:2000]}
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
    """
    logger.info(f"Chat request for document: {document_id}")
    
    # 1. Fetch Analysis Data
    analysis_data = await storage.get_analysis_result(document_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Analysis report not found. Please wait for analysis to complete.")
    
    # 2. Build Context
    context_str = format_context_from_analysis(analysis_data)
    
    # 3. Build Prompt
    system_instruction = """
    You are the "Valiance Financial Assistant", an expert real estate underwriter.
    You are currently discussing a specific deal report with the user.
    
    RULES:
    1. STRICTLY restrict your answers to the provided "REPORT CONTEXT". Do not make up facts about the property not in the context.
    2. If the user asks about something not in the report, politely say you don't have that information in the current analysis.
    3. Be concise, professional, and analytical.
    4. You can explain general real estate concepts if asked (e.g., "What is a Cap Rate?"), but always tie it back to the current deal's numbers if applicable.
    5. Format your response with Markdown for readability (bold key numbers, lists).
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