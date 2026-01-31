from fastapi import APIRouter, Depends, HTTPException
from app.services.ingestion_service import IngestionService
from app.services.financial_service import FinancialService
from app.services.excel_service import ExcelService
from app.services.memo_service import MemoService
from app.services.explainability_service import ExplainabilityService
from app.services.storage_service import storage_service
from app.services.progress_service import ProgressService
from app.models.schemas import UnderwritingAnalysis, DealParameters, DealPackage
from typing import Dict, Any
from app.dependencies import get_ingestion_service, get_financial_service, get_excel_service, get_memo_service, get_explainability_service, get_progress_service
import logging
from datetime import datetime
import os
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analysis/{document_id}", response_model=UnderwritingAnalysis)
async def perform_analysis(
    document_id: str,
    deal_parameters: DealParameters,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    financial_service: FinancialService = Depends(get_financial_service),
    excel_service: ExcelService = Depends(get_excel_service),
    memo_service: MemoService = Depends(get_memo_service),
    explainability_service: ExplainabilityService = Depends(get_explainability_service),
    progress_service: ProgressService = Depends(get_progress_service),
):
    """
    Performs a full underwriting analysis on a given deal.
    
    Pipeline:
    1. Ingest & Normalize: Extract data from OCR, normalize categories
    2. Check Viability: Apply deterministic gating criteria
    3. Calculate Financials: Pro forma and historical metrics
    4. Generate Output: Excel model
    5. Return: Full analysis with audit trail
    """
    logger.info(f"Starting analysis for document: {document_id}")
    logger.info(f"Received deal parameters: {deal_parameters.model_dump_json(indent=2)}")
    
    await progress_service.update_progress(document_id, 10, "Starting analysis...")

    # ===== STEP 1: INGEST & NORMALIZE =====
    try:
        await progress_service.update_progress(document_id, 20, "Extracting and normalizing data from document...")
        analysis = await ingestion_service.ingest_pdf_document(document_id)
        
        # Apply Overrides if present
        if deal_parameters.units_override is not None:
             analysis.property_meta.total_units = deal_parameters.units_override
             logger.info(f"Applied Units Override: {deal_parameters.units_override}")
             
             # Also update rent_roll_summary total_units to ensure consistency before calc
             if analysis.rent_roll_summary:
                 analysis.rent_roll_summary.total_units = deal_parameters.units_override
             
        if deal_parameters.purchase_price_override is not None:
             analysis.property_meta.purchase_price = deal_parameters.purchase_price_override
             logger.info(f"Applied Purchase Price Override: {deal_parameters.purchase_price_override}")

        logger.info(f"Ingestion complete. Property: {analysis.property_meta.address}, Units: {analysis.property_meta.total_units}")
        await progress_service.update_progress(document_id, 40, "Data extraction complete.")
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}")
        await progress_service.update_progress(document_id, 0, f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {str(e)}")

    # ===== STEP 2: CHECK DEAL VIABILITY (DETERMINISTIC) =====
    await progress_service.update_progress(document_id, 50, "Checking deal viability against criteria...")
    # Attach deal parameters to analysis
    analysis.deal_parameters = deal_parameters
    # Ensure the top-level exit_cap_rate is set from the start
    analysis.exit_cap_rate = deal_parameters.exit_cap_rate
    
    viability_check = financial_service.check_deal_viability(analysis)
    logger.info(f"Viability check: {viability_check['status']}")
    
    if viability_check["status"] == "FAIL":
        analysis.pass_fail_status = "FAIL"
        analysis.gating_reasons = viability_check["reasons"]
        logger.warning(f"Deal failed viability check: {viability_check['reasons']}")
        # Proceed to calculation anyway so we can show "What if it didn't fail" or "Sensitivity"
        # The frontend will display the FAIL status prominently.
    
    # ===== STEP 3: CALCULATE FINANCIALS =====
    try:
        await progress_service.update_progress(document_id, 60, "Calculating historical performance (T12)...")
        # Calculate historical (from T12)
        historical_data = financial_service.calculate_historical(analysis)
        logger.info(f"Historical NOI: ${historical_data['historical_noi']:,.2f}")
        analysis.historical_noi = historical_data["historical_noi"]
        analysis.historical_cap_rate = historical_data["historical_cap_rate"]
        logger.info(f"AFTER historical calculation, analysis.exit_cap_rate: {getattr(analysis, 'exit_cap_rate', 'NOT SET')}")
        
        await progress_service.update_progress(document_id, 70, "Calculating pro forma projections...")
        # Calculate pro forma (with market rents & standard assumptions)
        pro_forma_data = financial_service.calculate_pro_forma(analysis)
        logger.info(f"pro_forma_data dictionary from financial_service: {pro_forma_data}")

        analysis.pro_forma_noi = pro_forma_data["pro_forma_noi"]
        analysis.pro_forma_expenses = pro_forma_data["pro_forma_expenses"]
        analysis.cap_rate = pro_forma_data["cap_rate"]
        analysis.exit_cap_rate = pro_forma_data.get("exit_cap_rate")
        logger.info(f"Pro Forma NOI: ${analysis.pro_forma_noi:,.2f}, Cap Rate: {analysis.cap_rate:.2%}")
        logger.info(f"AFTER pro_forma calculation, analysis.exit_cap_rate: {analysis.exit_cap_rate}")
    except Exception as e:
        logger.error(f"Financial calculation failed: {str(e)}")
        await progress_service.update_progress(document_id, 0, f"Calculation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Financial calculation failed: {str(e)}")
    
    # ===== STEP 3.5: GENERATE EXPLAINABILITY & OUTPUTS =====
    try:
        await progress_service.update_progress(document_id, 80, "Generating insights and explanations...")
        
        # 1. Deterministic Explanations (Fast, Sync)
        analysis = explainability_service.generate_explanations(analysis)
        logger.info("Explainability metadata generated successfully.")
        
        # 2. Parallel Generation of AI Content (Slow, Async)
        await progress_service.update_progress(document_id, 90, "Generating AI commentary and memo...")
        
        async def task_commentary():
            await explainability_service.generate_analyst_commentary(analysis)
            
        async def task_memo():
            # Generate Investment Memo (Markdown)
            memo_content = await memo_service.generate_investment_memo(analysis)
            analysis.investment_memo = memo_content
            
        # Run AI tasks in parallel to save time
        await asyncio.gather(task_commentary(), task_memo())
        logger.info("AI content (Commentary & Memo) generated successfully.")
        
        # Note: Excel generation removed from critical path as it's not stored in the analysis object.
        # It is generated on-demand via /export/excel endpoint.
        
    except Exception as e:
        logger.error(f"Explainability/Memo generation failed: {str(e)}")
        # We don't stop the pipeline, but we log it.
        analysis.gating_reasons.append(f"AI Generation failed: {str(e)}")
    
    # ===== STEP 5: RETURN COMPLETE ANALYSIS =====
    await progress_service.update_progress(document_id, 100, "Analysis complete!")
    logger.info(f"Analysis complete. Final status: {analysis.pass_fail_status}")
    # FINAL CHECK: Ensure exit_cap_rate is correctly set and serialized
    analysis.exit_cap_rate = deal_parameters.exit_cap_rate
    
    logger.info(f"Analysis complete. Final status: {analysis.pass_fail_status}")
    logger.info(f"FINAL analysis object before return: {analysis.model_dump_json(indent=2)}")
    
    # ===== SAVE TO STORAGE =====
    # Save the analysis result so it can be retrieved later
    analysis_dict = analysis.model_dump()
    await storage_service.save_analysis_result(document_id, analysis_dict)

    # Also update/create a DealPackage entry for this single document analysis
    # This allows it to show up in the history list alongside multi-doc packages
    existing_package = await storage_service.get_deal_package(document_id)
    now = datetime.utcnow().isoformat()
    
    if existing_package:
        # Update existing
        package = DealPackage(**existing_package)
        package.updated_at = now
        package.normalization_status = "completed"
        # Ensure property name is set
        if not package.property_name or package.property_name == "Unknown":
            package.property_name = analysis.property_meta.address or f"Deal {document_id[:8]}"
    else:
        # Create new "wrapper" package for this single document
        package = DealPackage(
            package_id=document_id,
            property_name=analysis.property_meta.address or f"Deal {document_id[:8]}",
            created_at=now,
            updated_at=now,
            documents={}, # Single doc flow doesn't populate this yet, but that's fine
            normalization_status="completed",
            verification_progress=1.0
        )
    
    await storage_service.save_deal_package(package.model_dump())
    logger.info(f"Saved analysis and package wrapper for {document_id}")

    # Save audit logs to root directory
    try:
        # Assuming current working directory is inside financial-engine, root is one level up
        # or we just save to the CWD if that's what "root" implies in context of execution,
        # but user said "root directly". Assuming repo root.
        # Check if we are in financial-engine
        cwd = os.getcwd()
        if os.path.basename(cwd) == "financial-engine":
            root_dir = os.path.dirname(cwd)
        else:
            root_dir = cwd
            
        audit_file_path = os.path.join(root_dir, f"audit_logs_{document_id}.txt")
        
        with open(audit_file_path, "w", encoding="utf-8") as f:
            f.write(f"AUDIT LOGS FOR DOCUMENT: {document_id}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            if analysis.audit_trail:
                for log in analysis.audit_trail:
                    f.write(f"Field:      {log.get('field_name', 'N/A')}\n")
                    f.write(f"Value:      {log.get('extracted_value', 'N/A')}\n")
                    f.write(f"Source:     {log.get('source', 'N/A')}\n")
                    f.write(f"Method:     {log.get('method', 'N/A')}\n")
                    f.write(f"Confidence: {log.get('confidence_score', 'N/A')}\n")
                    f.write("-" * 40 + "\n")
            else:
                f.write("No audit trails found for this analysis.\n")
                
        logger.info(f"Successfully saved audit logs to: {audit_file_path}")
        
    except Exception as e:
        logger.error(f"Failed to save audit logs to file: {str(e)}")

@router.patch("/analysis/{document_id}")
async def update_analysis(
    document_id: str,
    analysis_data: UnderwritingAnalysis,
    storage_service: Any = Depends(lambda: storage_service) # Use singleton directly
):
    """
    Updates an existing analysis record.
    Used for saving manual edits, configuration changes (e.g. Rent Roll config),
    or overrides before export.
    """
    logger.info(f"Updating analysis for document: {document_id}")
    
    # Verify it exists first (optional, but good practice)
    # existing = await storage_service.get_analysis_result(document_id)
    # if not existing:
    #     raise HTTPException(status_code=404, detail="Analysis not found")

    # Save to storage
    analysis_dict = analysis_data.model_dump()
    await storage_service.save_analysis_result(document_id, analysis_dict)
    
    logger.info(f"Analysis updated successfully for {document_id}")
    return {"status": "success", "message": "Analysis updated"}
    # Return a dictionary created from the model, ensuring correct field names
    return analysis