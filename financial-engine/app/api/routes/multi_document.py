"""
Multi-Document Upload and Normalization API Routes.
Handles the ingestion of ZIP files containing 8 folders of documents for a deal package.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging
import zipfile
import io
import os
from pathlib import Path
import shutil
import asyncio
import math
from starlette.concurrency import run_in_threadpool

from app.models.schemas import (
    DocumentType,
    DocumentMetadata,
    DealPackage,
    DocumentNormalizationResult,
    NormalizedDataItem,
    OMProformaTable,
    UnderwritingAnalysis, DealParameters, PropertyMeta,
    RentRollItem, RentRollSummary, StandardizedExpense,
    ExpenseCategory, AuditLog,
    StudentHousingConfig
)
from app.services.ingestion_service import IngestionService
from app.services.normalization_service import NormalizationService
from app.services.gemini_service import GeminiService
from app.services.multi_document_extraction_service import MultiDocumentExtractionService
from app.services.storage_service import storage_service
from app.services.explainability_service import ExplainabilityService
from app.services.progress_service import ProgressService
from app.services.classification_service import ClassificationService
from app.services.batch_logging_service import BatchLoggingService
from app.dependencies import get_gemini_service, get_openai_service, get_progress_service, get_explainability_service, get_classification_service, get_batch_logging_service
from app.services.zip_processing_service import ZipProcessingService, FOLDER_MAPPING

# Import Services for Logic Function
from app.services.financial_service import FinancialService
from app.services.audit_log_service import AuditLogService
from app.services.excel_service import ExcelService
from app.services.memo_service import MemoService
from app.services.synthesis_service import SynthesisService

router = APIRouter(prefix="/api/v1/multi-document", tags=["Multi-Document Ingestion"])
logger = logging.getLogger(__name__)

# In-memory file storage cache for processing session (backed by GCP storage)
# We keep file content cache to avoid repeated downloads during the same processing session
# but we remove the metadata cache (deal_packages_cache) to ensure consistency.
file_storage_cache = {}

# Initialize services
zip_service = ZipProcessingService()
TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)


@router.post("/packages/upload-zip", response_model=DealPackage)
async def upload_zip_package(
    file: UploadFile = File(...),
    property_name: Optional[str] = Form(None),
    classification_service: ClassificationService = Depends(get_classification_service),
    batch_logging_service: BatchLoggingService = Depends(get_batch_logging_service)
):
    """
    Upload a ZIP file containing the 8-folder structure.
    """
    
    # Validate file type
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    
    # Extract property name from filename if not provided
    if not property_name:
        property_name = file.filename.replace('.zip', '').replace('_Inputs', '')
    
    # Create temp file for processing
    temp_zip_path = os.path.join(TEMP_UPLOAD_DIR, f"temp_{uuid.uuid4()}.zip")
    
    try:
        # Stream upload to temp file to avoid memory issues
        with open(temp_zip_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        # Process ZIP using the service
        package, file_data_map = await zip_service.process_zip_file(
            temp_zip_path,
            property_name,
            classification_service=classification_service,
            batch_logging_service=batch_logging_service
        )
        
        # Update file cache
        file_storage_cache.update(file_data_map)
        
        return package
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing ZIP file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing ZIP file: {str(e)}")
    finally:
        # Cleanup temp file
        if os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_zip_path}: {e}")


@router.post("/packages/upload-chunk/init")
async def init_chunk_upload(
    filename: str = Form(...),
    total_chunks: int = Form(...),
):
    """Initialize a chunked upload session."""
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(TEMP_UPLOAD_DIR, upload_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    logger.info(f"Initialized chunked upload {upload_id} for {filename} ({total_chunks} chunks)")
    return {"upload_id": upload_id}


@router.post("/packages/upload-chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
):
    """Upload a single chunk of the file."""
    upload_dir = os.path.join(TEMP_UPLOAD_DIR, upload_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    chunk_path = os.path.join(upload_dir, f"part_{chunk_index}")
    
    try:
        with open(chunk_path, "wb") as f:
            content = await chunk.read()
            f.write(content)
        
        return {"message": "Chunk received", "chunk_index": chunk_index}
    except Exception as e:
        logger.error(f"Error saving chunk {chunk_index} for {upload_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save chunk")


@router.post("/packages/upload-chunk/complete")
async def complete_chunk_upload(
    upload_id: str = Form(...),
    original_filename: str = Form(...),
    property_name: Optional[str] = Form(None),
    is_smart_upload: bool = Form(False),
    progress_service: ProgressService = Depends(get_progress_service),
    classification_service: ClassificationService = Depends(get_classification_service),
    batch_logging_service: BatchLoggingService = Depends(get_batch_logging_service)
):
    """Complete the chunked upload and process the file(s)."""
    upload_dir = os.path.join(TEMP_UPLOAD_DIR, upload_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    logger.info(f"Completing chunked upload {upload_id} for {original_filename} (Smart Upload: {is_smart_upload})")
    
    try:
        # Get all chunk files
        chunk_files = sorted(
            [f for f in os.listdir(upload_dir) if f.startswith("part_")],
            key=lambda x: int(x.split("_")[1])
        )
        
        if not chunk_files:
             raise HTTPException(status_code=400, detail="No chunks found")

        # Combine chunks into a single file
        combined_path = os.path.join(upload_dir, "combined_upload.tmp")
        
        def combine_chunks():
            with open(combined_path, "wb") as outfile:
                for chunk_file in chunk_files:
                    chunk_path = os.path.join(upload_dir, chunk_file)
                    with open(chunk_path, "rb") as infile:
                        shutil.copyfileobj(infile, outfile)
        
        await run_in_threadpool(combine_chunks)
        
        # Determine property name
        if not property_name:
             property_name = original_filename.replace('.zip', '').replace('_Inputs', '')

        if is_smart_upload:
            # Check if it is a zip
            if not zipfile.is_zipfile(combined_path):
                 # Read file content
                 with open(combined_path, "rb") as f:
                     content = f.read()
                 
                 files = [(original_filename, content)]
                 
                 package, file_data_map = await zip_service.process_smart_upload(
                    files=files,
                    property_name=property_name,
                    classification_service=classification_service,
                    progress_service=progress_service,
                    task_id=upload_id
                 )
            else:
                # Use memory-efficient streaming/batch processing for ZIPs
                package, file_data_map = await zip_service.process_smart_zip(
                    zip_path=combined_path,
                    property_name=property_name,
                    classification_service=classification_service,
                    progress_service=progress_service,
                    task_id=upload_id,
                    batch_logging_service=batch_logging_service
                )
        else:
            # Standard "Structured Zip" processing
            package, file_data_map = await zip_service.process_zip_file(
                combined_path,
                property_name,
                progress_service=progress_service,
                task_id=upload_id,
                batch_logging_service=batch_logging_service
            )
        
        # Update file cache
        file_storage_cache.update(file_data_map)
        
        # Cleanup
        try:
            shutil.rmtree(upload_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {upload_dir}: {str(e)}")
        
        return package
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chunked upload {upload_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/packages/smart-upload/validate-files")
async def validate_smart_upload_files(
    files: List[UploadFile] = File(...),
    classification_service: ClassificationService = Depends(get_classification_service)
):
    """
    Endpoint to pre-validate and classify files before actual upload/processing if needed.
    """
    results = []
    filenames = [f.filename for f in files]
    
    # Batch classify
    classification_map = await classification_service.classify_files_batch(filenames=filenames)
    
    for file in files:
        doc_type = classification_map.get(file.filename, "Unknown")
        results.append({
            "filename": file.filename,
            "detected_type": doc_type,
            "status": "valid" if doc_type != "Unknown" else "needs_review"
        })
    
    return {"files": results}


@router.post("/packages/{package_id}/documents")
async def upload_additional_documents(
    package_id: str,
    files: List[UploadFile] = File(...),
    classification_service: ClassificationService = Depends(get_classification_service),
):
    """
    Upload additional documents to an existing package.
    Uses AI classification to determine where to place the files.
    """
    try:
        # Read all files into memory (assuming they are reasonable size for now)
        file_data = []
        for file in files:
            content = await file.read()
            file_data.append((file.filename, content))
            
        package, file_map = await zip_service.add_files_to_package(
            package_id=package_id,
            files=file_data,
            classification_service=classification_service
        )
        
        # Update file cache
        file_storage_cache.update(file_map)
        
        return package
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding documents to package {package_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add documents: {str(e)}")


@router.get("/packages/{package_id}", response_model=DealPackage)
async def get_deal_package(package_id: str):
    """
    Retrieve a deal package with all its documents.
    """
    # Load from storage service (Source of Truth)
    package_data = await storage_service.get_deal_package(package_id)
    if package_data:
        package = DealPackage(**package_data)
        return package
    
    raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")


@router.get("/packages")
async def list_deal_packages(
    limit: int = 5,
    offset: int = 0
):
    """
    List deal packages with pagination.
    """
    # Get paginated packages from storage service
    packages_data, total = await storage_service.list_deal_packages(limit=limit, offset=offset)
    
    # Convert to DealPackage objects
    packages = []
    for pkg_data in packages_data:
        try:
            package = DealPackage(**pkg_data)
            packages.append(package)
        except Exception as e:
            logger.error(f"Error parsing package data: {str(e)}")
            continue
    
    # Calculate pagination metadata
    has_more = (offset + limit) < total
    
    logger.info(f"Returning {len(packages)} packages (offset={offset}, limit={limit}, total={total})")
    
    return {
        "packages": [pkg.model_dump() for pkg in packages],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more
    }


@router.post("/packages/{package_id}/normalize")
async def normalize_package_documents(
    package_id: str,
    document_type: Optional[DocumentType] = None,
    gemini_service: GeminiService = Depends(get_gemini_service),
    openai_service: Any = Depends(get_openai_service),
    progress_service: ProgressService = Depends(get_progress_service),
    explainability_service: ExplainabilityService = Depends(get_explainability_service),
    batch_logging_service: BatchLoggingService = Depends(get_batch_logging_service)
):
    """
    Normalize documents in a package and automatically generate financial report.
    """
    await progress_service.update_progress(package_id, 5, "Initializing normalization...")
    
    # Load from storage service
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
    
    # Initialize extraction service
    extraction_service = MultiDocumentExtractionService(gemini_service=gemini_service, batch_logging_service=batch_logging_service)
    
    # Collect documents to process
    documents_to_process = []
    
    # Determine which document types to process
    if document_type:
        target_types = [document_type]
    else:
        # If no specific type is provided, process all available document types in the package
        target_types = list(package.documents.keys())
        
        # If package has no documents at all, raise error
        if not target_types:
            raise HTTPException(
                status_code=400,
                detail=f"No documents found in package {package_id}"
            )
            
    # Helper to load file content
    async def load_file_content(doc_metadata):
        doc_id = doc_metadata.document_id
        if doc_id in file_storage_cache:
            return file_storage_cache[doc_id]
        
        filename = doc_metadata.filename
        extension = Path(filename).suffix
        storage_path = f"deal-packages/{package_id}/documents/{doc_id}{extension}"
        
        try:
            content = await storage_service.get_document_file(storage_path)
            if content:
                file_data = {
                    "content": content,
                    "filename": filename,
                    "document_type": doc_metadata.document_type,
                    "package_id": package_id
                }
                file_storage_cache[doc_id] = file_data
                return file_data
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {str(e)}")
        return None

    # Collect documents by category for segmented processing
    rent_roll_docs = []
    financial_docs = [] # T12, Tax, Utilities, etc.
    om_docs = []
    
    documents_count = 0
    
    for doc_type in target_types:
        if doc_type not in package.documents:
            continue
        
        for doc_metadata in package.documents[doc_type]:
            file_data = await load_file_content(doc_metadata)
            if not file_data:
                continue
                
            filename = file_data["filename"]
            # Determine file type
            if filename.endswith((".xlsx", ".xls")):
                file_type = "excel"
            elif filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
                file_type = "visual"
            elif filename.lower().endswith(".csv"):
                file_type = "csv"
            else:
                logger.warning(f"Unsupported file type: {filename}")
                continue
                
            doc_info = {
                "content": file_data["content"],
                "filename": filename,
                "type": file_type,
                "document_category": doc_metadata.document_type,
                "document_id": doc_metadata.document_id
            }
            
            documents_count += 1
            
            if doc_metadata.document_type == DocumentType.RENT_ROLL:
                rent_roll_docs.append(doc_info)
            elif doc_metadata.document_type == DocumentType.OFFERING_MEMORANDUM:
                om_docs.append(doc_info)
                # OMs also contain financials, so add to financial_docs too for extraction
                financial_docs.append(doc_info)
            else:
                # All other docs (Financials, Tax Bills, Utilities, etc.) go to financial extraction
                financial_docs.append(doc_info)

    if documents_count == 0:
        logger.warning(f"No processable documents found for package {package_id}")
        return DocumentNormalizationResult(
            document_id="multiple",
            document_type=document_type or DocumentType.FINANCIALS,
            normalized_items=[],
            total_items=0,
            verified_items=0,
            confidence_average=0.0
        )
    
    logger.info(f"Processing {documents_count} documents: {len(rent_roll_docs)} Rent Rolls, {len(financial_docs)} Financials/Other")
    
    await progress_service.update_progress(package_id, 20, f"Processing {documents_count} documents folder by folder...")
    
    # --- Simplified Parallel Processing with Basic Progress Aggregation ---
    
    # 1. Separate documents
    om_documents = [d for d in financial_docs if d.get("document_category") == DocumentType.OFFERING_MEMORANDUM]
    remaining_financial_docs = [d for d in financial_docs if d.get("document_category") != DocumentType.OFFERING_MEMORANDUM]
    
    # NEW: Determine Underwriting Flow (Flow A vs Flow B)
    if om_documents:
        # Flow A: OM-Driven (Single Source of Truth)
        logger.info("OM Detected. Enforcing Flow A: OM-Driven. Ignoring non-OM documents.")
        package.underwriting_flow = "OM_DRIVEN"
        
        # Strictly ignore other files
        rent_roll_docs = []
        remaining_financial_docs = []
        
    else:
        # Flow B: Non-OM (Multi-Source Aggregation)
        logger.info("No OM Detected. Using Flow B: Multi-Source Aggregation.")
        package.underwriting_flow = "MULTI_SOURCE"

    # Shared State for Parallel Progress Tracking
    progress_lock = asyncio.Lock()
    task_progress = {"om": 0.0, "rr": 0.0, "fin": 0.0}
    global_completed_files = set()
    global_active_files = {}  # task_key -> current_file
    
    async def update_aggregate_progress(task_key, percent, msg, details=None):
        async with progress_lock:
            # 1. Update Percentage
            task_progress[task_key] = percent
            # OM: 10pts, RentRoll: 15pts, Financials: 15pts -> Total 40pts + Base 20
            total_added = (task_progress["om"] * 0.10) + (task_progress["rr"] * 0.15) + (task_progress["fin"] * 0.15)
            global_pct = 20 + int(total_added)
            
            # 2. Update File Tracking
            if details:
                # Merge completed files (Accumulate, never replace with partials)
                if 'completed_files' in details:
                    global_completed_files.update(details['completed_files'])
                
                # Update active file for this task
                if 'current_file' in details:
                    global_active_files[task_key] = details['current_file']
                elif 'active_files' in details and details['active_files']:
                    # Take the first one if multiple
                    global_active_files[task_key] = details['active_files'][0]
                else:
                    # Clear active file for this task if not provided or empty
                    if task_key in global_active_files:
                        del global_active_files[task_key]
            
            # Construct Unified Details
            # We want to show ALL completed files from ALL tasks
            unified_details = {
                "completed_files": list(global_completed_files),
                "active_files": list(global_active_files.values()),
                "status": "processing"
            }
            
            # Send Update
            await progress_service.update_progress(package_id, global_pct, msg, details=unified_details)

    class SimpleProgressAdapter:
        def __init__(self, key):
            self.key = key
            
        async def update_progress(self, task_id, pct, msg, details=None):
            await update_aggregate_progress(self.key, pct, msg, details)

    # Task A: Process OM Documents
    async def process_om_task():
        if not om_documents:
            await update_aggregate_progress("om", 100, "OM processing skipped")
            return None, [], [], [], None, False
        try:
            logger.info(f"Starting OM Extraction task ({len(om_documents)} docs)...")
            res = await extraction_service.process_financial_documents(
                om_documents,
                progress_service=SimpleProgressAdapter("om"),
                task_id=package_id,
                progress_start=0, progress_end=100,
                initial_completed_files=[], # Don't pass global list, we handle merging in adapter
                total_files_override=documents_count
            )
            extracted_expenses, extracted_proforma, completed_files, verified_year, is_partial = res
            
            # Extract Address
            address = None
            for item in extracted_expenses:
                if item.field_type == "property_meta" and item.normalized_value == "Property Address":
                    if item.metadata and item.metadata.get("text_value"):
                        address = item.metadata.get("text_value")
                        logger.info(f"Found Target Property Address from OM: {address}")
                        break
            
            return address, extracted_expenses, extracted_proforma, completed_files, verified_year, is_partial
        except Exception as e:
            logger.error(f"Error in OM Task: {e}")
            return None, [], [], [], None, False

    # Task B: Process Rent Rolls (Dependent on OM)
    async def process_rent_rolls_task(om_task_future):
        if not rent_roll_docs:
            await update_aggregate_progress("rr", 100, "Rent Roll processing skipped")
            return [], []
        
        await update_aggregate_progress("rr", 0, "Rent Roll waiting for OM analysis...")
        
        # Wait for OM task to finish to get the address
        om_result = await om_task_future
        target_address = om_result[0] if om_result else None
        # Note: We don't need to pass om_completed_files here because the adapter merges them globally
        
        logger.info(f"Starting Rent Roll Processing (Target Address: {target_address})...")
        
        return await extraction_service.process_rent_roll_documents(
            rent_roll_docs,
            progress_service=SimpleProgressAdapter("rr"),
            task_id=package_id,
            progress_start=0, progress_end=100,
            initial_completed_files=[],
            total_files_override=documents_count,
            target_property_address=target_address
        )

    # Task C: Process Remaining Financials
    async def process_financials_task():
        if not remaining_financial_docs:
            await update_aggregate_progress("fin", 100, "Financials processing skipped")
            return [], [], [], None, False
        
        logger.info("Starting Remaining Financials Processing immediately...")
        return await extraction_service.process_financial_documents(
            remaining_financial_docs,
            progress_service=SimpleProgressAdapter("fin"),
            task_id=package_id,
            progress_start=0, progress_end=100,
            initial_completed_files=[],
            total_files_override=documents_count
        )

    try:
        # Launch Tasks
        om_task = asyncio.create_task(process_om_task())
        fin_task = asyncio.create_task(process_financials_task())
        rr_task = asyncio.create_task(process_rent_rolls_task(om_task))
        
        logger.info("Launching parallel extraction tasks...")
        results = await asyncio.gather(om_task, rr_task, fin_task)
        
        # Unpack Results
        (om_address, extracted_om_expenses, extracted_om_proforma, om_completed_files, om_verified_year, om_is_partial) = results[0]
        (extracted_rent_roll, rr_completed_files) = results[1]
        (extracted_other_financials, other_om_proforma, other_fin_completed_files, other_verified_year, other_is_partial) = results[2]
        
        # Determine Primary Fiscal Year
        # Priority: OM Year > Other Financials Year
        package.primary_fiscal_year = om_verified_year or other_verified_year
        package.is_partial_year = om_is_partial if om_verified_year else other_is_partial
        
        if package.primary_fiscal_year:
             logger.info(f"SYNTHESIZED FISCAL YEAR: {package.primary_fiscal_year} (Partial: {package.is_partial_year})")

        # Merge Financials
        all_financials = extracted_om_expenses + extracted_other_financials
        
        # Create a mapping of filename to document_id for quick lookup
        filename_to_id_map = {}
        for doc_list in package.documents.values():
            for doc_meta in doc_list:
                filename_to_id_map[doc_meta.filename] = doc_meta.document_id

        # Assign unique IDs and ensure document_id is in metadata
        for idx, item in enumerate(all_financials):
            item.id = str(uuid.uuid4())
            # Ensure metadata exists
            if item.metadata is None:
                item.metadata = {}
            
            # Check if document_id is already present
            if "document_id" not in item.metadata or not item.metadata["document_id"]:
                if item.source_document in filename_to_id_map:
                    item.metadata["document_id"] = filename_to_id_map[item.source_document]

        package.financials_data = all_financials
        
        # Merge OM Proforma
        all_om_proforma = extracted_om_proforma + other_om_proforma
        if all_om_proforma:
            package.om_proforma_data = all_om_proforma

        # Extract Rent Roll items from OM extracted expenses/metadata
        # We need to make sure OM rent roll items are included in the package rent roll data
        # so that SynthesisService can prioritize them.
        synthesis_service_local = SynthesisService()
        om_rent_roll_items = synthesis_service_local.extract_rent_roll_from_normalized_items(extracted_om_expenses)
        
        if om_rent_roll_items:
            logger.info(f"Extracted {len(om_rent_roll_items)} rent roll items from OM Normalized Data. Adding to package rent roll.")
            # Tag them as OM source explicitly to ensure priority if filename doesn't contain OM
            for item in om_rent_roll_items:
                if item.source_file and "OM" not in item.source_file.upper() and "OFFERING" not in item.source_file.upper():
                     item.source_file = f"OM - {item.source_file}"
            extracted_rent_roll.extend(om_rent_roll_items)
            
        # Save Rent Roll
        package.rent_roll_data = extracted_rent_roll
        
        # Collect all completed files
        all_completed_files = list(set(om_completed_files + rr_completed_files + other_fin_completed_files))
        
        logger.info(f"Processing Complete. Saved {len(all_financials)} financial items.")

    except Exception as e:
         logger.error(f"Error in parallel processing: {e}")
         await progress_service.update_progress(package_id, 0, f"Processing failed: {str(e)}")
         raise HTTPException(status_code=500, detail=f"Error processing documents: {str(e)}")

    # Consolidate normalized_data for backward compatibility / Verification UI
    package.normalized_data = package.financials_data
    
    package.normalization_status = "in_progress"
    
    # Update cache and persist to GCP
    package_dict = package.model_dump()
    await storage_service.save_deal_package(package_dict)
    
    await progress_service.update_progress(package_id, 60, "Normalization complete. Generating financial report...")
    
    # ===== AUTOMATICALLY GENERATE FINANCIAL REPORT =====
    # Use default deal parameters for initial analysis
    from app.models.schemas import DealParameters
    
    default_params = DealParameters(
        growth_rate=0.03,
        exit_cap_rate=0.06,
        vacancy_rate=0.03,
        loan_amount=5000000,
        min_unit_count=15,
        max_unit_count=8000,
        max_build_year=1970,
        management_fee_rate=0.04,
        tax_rate=0.012,
        ltv=0.65,
        sofr_rate=0.05,
        bridge_spread=0.02,
        closing_costs=0.0,
        renovation_budget=0.0
    )
    
    try:
        # Call the analyze logic internally
        analysis_result = await _analyze_deal_package_logic(
            package_id=package_id,
            deal_parameters=default_params.model_dump(),
            gemini_service=gemini_service,
            openai_service=openai_service,
            progress_service=progress_service,
            explainability_service=explainability_service,
            progress_base=60,
            completed_files=all_completed_files
        )
        
        logger.info(f"Financial report generated successfully for package {package_id}")
        
        # Return a combined result so frontend gets both the analysis AND the normalized items for verification
        return {
            "analysis": analysis_result.model_dump(),
            "normalized_items": package.financials_data,
            "total_items": len(package.financials_data),
            "verified_items": 0,
            "confidence_average": 0.0
        }
        
    except Exception as e:
        logger.error(f"Error generating financial report: {str(e)}", exc_info=True)
        # If analysis fails, still return normalization result
        await progress_service.update_progress(package_id, 100, "Normalization complete. Analysis generation failed.")
        
        result = DocumentNormalizationResult(
            document_id="multiple",
            document_type=document_type or DocumentType.FINANCIALS,
            normalized_items=package.financials_data,
            total_items=len(package.financials_data),
            verified_items=0,
            confidence_average=0.0
        )
        return result


class VerifyItemRequest(BaseModel):
    user_correction: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

@router.put("/packages/{package_id}/verify-item/{item_id}")
async def verify_normalized_item(
    package_id: str,
    item_id: str,
    request_data: VerifyItemRequest
):
    """
    Mark a normalized item as verified by the user.
    """
    user_correction = request_data.user_correction
    payload = request_data.payload
    
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
    
    # Find and update the item in both lists to ensure consistency
    item_found = False
    
    # Target lists to update
    lists_to_update = [package.normalized_data]
    if hasattr(package, 'financials_data') and package.financials_data:
        lists_to_update.append(package.financials_data)
        
    logger.info(f"Updating item {item_id} in package {package_id}. Correction: {user_correction}, Payload: {payload}")
    for data_list in lists_to_update:
      for item in data_list:
        if item.id == item_id:
            logger.info(f"Found item {item_id}. Original amount: {item.metadata.get('amount') if item.metadata else 'N/A'}")
            item.user_verified = True
            if user_correction is not None:
                item.user_correction = user_correction
            
            # Handle additional fields from payload
            if payload:
                if "amount" in payload:
                    if item.metadata is None:
                        item.metadata = {}
                    # Force amount to float if possible
                    try:
                        item.metadata["amount"] = float(payload["amount"])
                    except:
                        item.metadata["amount"] = payload["amount"]
                    logger.info(f"Updated amount to: {item.metadata['amount']}")
                if "raw_text" in payload:
                    item.raw_text = payload["raw_text"]
                if "category_group" in payload:
                    try:
                        from app.models.schemas import CategoryGroup
                        item.category_group = CategoryGroup(payload["category_group"])
                    except: pass
            
            item_found = True
            break
            
    if not item_found:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in package")
        
    # Recalculate progress
    total_items = len(package.normalized_data)
    verified_items = sum(1 for item in package.normalized_data if item.user_verified)
    package.verification_progress = (verified_items / total_items) * 100 if total_items > 0 else 0
    
    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    return {
        "item_id": item_id,
        "verified": True,
        "user_correction": user_correction,
        "verification_progress": package.verification_progress,
        "message": "Item verified successfully"
    }


@router.post("/packages/{package_id}/verify-items-batch")
async def verify_items_batch(
    package_id: str,
    items: List[Dict[str, Any]]
):
    """
    Batch verify multiple normalized items at once.
    Supports updating amounts and raw text as well.
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
    
    # Track results
    verified_count = 0
    not_found_ids = []
    
    # Create a map of item_id to verification data for quick lookup
    verification_map = {item.get("item_id"): item for item in items if item.get("item_id")}
    
    # Update all items in both lists to ensure consistency
    # Target lists to update
    lists_to_update = [package.normalized_data]
    if hasattr(package, 'financials_data') and package.financials_data:
        lists_to_update.append(package.financials_data)

    for data_list in lists_to_update:
      for item in data_list:
        if item.id in verification_map:
            item_data = verification_map[item.id]
            item.user_verified = True
            
            user_correction = item_data.get("user_correction")
            if user_correction is not None:
                item.user_correction = user_correction
            
            # Handle payload/additional fields
            payload = item_data.get("payload")
            if payload:
                if "amount" in payload:
                    if item.metadata is None:
                        item.metadata = {}
                    try:
                        item.metadata["amount"] = float(payload["amount"])
                    except:
                        item.metadata["amount"] = payload["amount"]
                if "raw_text" in payload:
                    item.raw_text = payload["raw_text"]
                if "category_group" in payload:
                    try:
                        from app.models.schemas import CategoryGroup
                        item.category_group = CategoryGroup(payload["category_group"])
                    except: pass
                    
            verified_count += 1
    
    # Check for items that weren't found
    found_ids = {item.id for item in package.normalized_data if item.user_verified}
    requested_ids = set(verification_map.keys())
    not_found_ids = list(requested_ids - found_ids)
    
    # Recalculate progress
    total_items = len(package.normalized_data)
    total_verified = sum(1 for item in package.normalized_data if item.user_verified)
    package.verification_progress = (total_verified / total_items) * 100 if total_items > 0 else 0
    
    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    logger.info(f"Batch verified {verified_count} items for package {package_id}")
    
    return {
        "verified_count": verified_count,
        "total_verified": total_verified,
        "total_items": total_items,
        "verification_progress": package.verification_progress,
        "not_found_ids": not_found_ids,
        "message": f"Successfully verified {verified_count} items"
    }


@router.post("/packages/{package_id}/add-normalized-item")
async def add_normalized_item(
    package_id: str,
    item: Dict[str, Any]
):
    """
    Add a new normalized item to a package manually.
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
    
    # Create new item
    import uuid
    from app.models.schemas import NormalizedDataItem, CategoryGroup, DataClassification
    
    new_item = NormalizedDataItem(
        id=str(uuid.uuid4()),
        raw_text=item.get("raw_text", "Manual Entry"),
        normalized_value=item.get("normalized_value", "Uncategorized"),
        field_type=item.get("field_type", "expense_category"),
        category_group=CategoryGroup(item.get("category_group", "Operating Expense")),
        data_classification=DataClassification.SOURCED,
        confidence=1.0,
        user_verified=True,
        source_document=item.get("source_document", "Manual Entry"),
        metadata=item.get("metadata", {})
    )
    
    # Add to package
    package.normalized_data.append(new_item)
    
    # If it's a financial item, also add to financials_data
    if new_item.category_group in ["Operating Expense", "Tax & Insurance", "Revenue"]:
        if not hasattr(package, 'financials_data') or package.financials_data is None:
            package.financials_data = []
        package.financials_data.append(new_item)

    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    return {
        "message": "Item added successfully",
        "item": new_item.model_dump()
    }


@router.delete("/packages/{package_id}/remove-normalized-item/{item_id}")
async def remove_normalized_item(
    package_id: str,
    item_id: str
):
    """
    Remove a normalized item from a package.
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
    
    # Remove from normalized_data
    package.normalized_data = [i for i in package.normalized_data if i.id != item_id]
    
    # Remove from financials_data if present
    if hasattr(package, 'financials_data') and package.financials_data:
        package.financials_data = [i for i in package.financials_data if i.id != item_id]

    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    return {
        "message": "Item removed successfully",
        "item_id": item_id
    }


@router.post("/packages/{package_id}/manual-overrides")
async def update_manual_overrides(
    package_id: str,
    overrides: Dict[str, Any],
):
    """
    Update manual overrides for a deal package.
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
        
    # Update overrides
    package.manual_overrides.update(overrides)
    
    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    return {
        "message": "Manual overrides updated successfully",
        "overrides": package.manual_overrides
    }


@router.get("/packages/{package_id}/documents/{document_id}/content")
async def get_package_document_content(
    package_id: str,
    document_id: str,
    request: Request
):
    """
    Get a signed URL for the document content.
    If using local storage, returns a direct download URL to the backend.
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)

    # Find the document
    found_doc = None
    for category, docs in package.documents.items():
        for doc in docs:
            if doc.document_id == document_id:
                found_doc = doc
                break
        if found_doc:
            break
            
    if not found_doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found in package {package_id}")
        
    # Construct storage path
    extension = Path(found_doc.filename).suffix
    storage_path = f"deal-packages/{package_id}/documents/{document_id}{extension}"
    
    # Try to get signed URL (GCP)
    signed_url = await storage_service.get_signed_url(storage_path)
    
    if not signed_url:
        # Fallback to local download endpoint
        # Construct full URL for the download endpoint
        download_url = request.url_for("download_package_document", package_id=package_id, document_id=document_id)
        signed_url = str(download_url)
        
    return {
        "signed_url": signed_url,
        "filename": found_doc.filename,
        "content_type": storage_service._get_content_type(found_doc.filename)
    }


@router.get("/packages/{package_id}/documents/{document_id}/download")
async def download_package_document(
    package_id: str,
    document_id: str,
):
    """
    Directly download a document file (used for local storage or proxying).
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)

    # Find the document
    found_doc = None
    for category, docs in package.documents.items():
        for doc in docs:
            if doc.document_id == document_id:
                found_doc = doc
                break
        if found_doc:
            break
            
    if not found_doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found in package {package_id}")

    # Construct storage path
    extension = Path(found_doc.filename).suffix
    storage_path = f"deal-packages/{package_id}/documents/{document_id}{extension}"
    
    # Get file content
    content = await storage_service.get_document_file(storage_path)
    if not content:
        raise HTTPException(status_code=404, detail="File content not found")
        
    # Return as stream
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    
    content_type = storage_service._get_content_type(found_doc.filename)
    
    return StreamingResponse(
        BytesIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{found_doc.filename}"'}
    )


@router.delete("/packages/{package_id}/documents/{document_id}")
async def delete_document_from_package(
    package_id: str,
    document_id: str
):
    """
    Delete a document from a deal package.
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)

    # Find the document
    found_doc = None
    
    for category, docs in package.documents.items():
        for i, doc in enumerate(docs):
            if doc.document_id == document_id:
                found_doc = doc
                # Remove from category
                package.documents[category].pop(i)
                break
        if found_doc:
            break
            
    if not found_doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found in package {package_id}")
        
    # Update updated_at
    package.updated_at = datetime.utcnow().isoformat()
    
    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    # Remove from file storage cache if present
    if document_id in file_storage_cache:
        del file_storage_cache[document_id]
        
    return {
        "message": "Document deleted successfully",
        "document_id": document_id
    }


@router.patch("/packages/{package_id}/rename")
async def rename_deal_package(
    package_id: str,
    new_name: str
):
    """
    Rename a deal package.
    """
    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
    
    # Update name
    package.property_name = new_name
    package.updated_at = datetime.utcnow().isoformat()
    
    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    return {
        "message": "Package renamed successfully",
        "package_id": package_id,
        "new_name": new_name
    }


@router.delete("/packages/{package_id}")
async def delete_deal_package(package_id: str):
    """
    Delete an entire deal package and all its associated data.
    This includes:
    - Package metadata from MongoDB
    - Analysis results from MongoDB
    - All document files from GCP/local storage
    """
    # Load from storage to verify it exists
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    
    try:
        # Delete the package (this also deletes analysis results and files)
        success = await storage_service.delete_deal_package(package_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete package completely")
        
        # Remove from file cache if present
        package = DealPackage(**package_data)
        for category, docs in package.documents.items():
            for doc in docs:
                if doc.document_id in file_storage_cache:
                    del file_storage_cache[doc.document_id]
        
        logger.info(f"Successfully deleted package {package_id}")
        
        return {
            "message": "Package deleted successfully",
            "package_id": package_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting package {package_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete package: {str(e)}")


@router.put("/packages/{package_id}/documents/{document_id}/category")
async def update_document_category(
    package_id: str,
    document_id: str,
    new_category: str
):
    """
    Move a document to a different category.
    """
    # Validate new category
    try:
        new_doc_type = DocumentType(new_category)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {new_category}")

    # Load from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)

    # Find the document
    found_doc = None
    old_category = None
    
    for category, docs in package.documents.items():
        for i, doc in enumerate(docs):
            if doc.document_id == document_id:
                found_doc = doc
                old_category = category
                # Remove from old category
                package.documents[category].pop(i)
                break
        if found_doc:
            break
            
    if not found_doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found in package {package_id}")
        
    # Update document type
    found_doc.document_type = new_doc_type
    
    # Add to new category
    if new_doc_type not in package.documents:
        package.documents[new_doc_type] = []
    package.documents[new_doc_type].append(found_doc)
    
    # Update updated_at
    package.updated_at = datetime.utcnow().isoformat()
    
    # Save changes
    await storage_service.save_deal_package(package.model_dump())
    
    return {
        "message": "Document moved successfully",
        "document_id": document_id,
        "old_category": old_category,
        "new_category": new_category
    }


@router.get("/document-types")
async def get_document_types():
    """
    Get list of all supported document types with their folder naming conventions.
    """
    result = []
    for dt in DocumentType:
        folder_examples = [k for k, v in FOLDER_MAPPING.items() if v == dt][:3]
        result.append({
            "type": dt.value,
            "folder_examples": folder_examples
        })
    return result


def _clean_address(address: str) -> str:
    """
    Clean address string by removing document path artifacts.
    E.g., "Rent Roll/2715DwightRentRoll Package..." -> "2715 Dwight Way"
    """
    import re
    
    if not address:
        return "Unknown"
    
    # Remove document type prefixes
    address = re.sub(r'^(Rent Roll|Offering Memorandum|Financials|Tax Bills?|Utilities|Leases|Disclosures|Building Plans & Permits|Images)[/\\]', '', address, flags=re.IGNORECASE)
    
    # Extract street address pattern: number + street name
    match = re.search(r'(\d+)\s+([A-Za-z\s]+?)(?:\s+(?:Way|Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Court|Ct|Circle|Cir|Place|Pl))?(?:[,\s]|$)', address)
    if match:
        street_num = match.group(1)
        street_name = match.group(2).strip()
        
        # Try to find city and state in the remaining text
        city_state_match = re.search(r',\s*([A-Za-z\s]+),\s*([A-Z]{2})', address)
        if city_state_match:
            city = city_state_match.group(1).strip()
            state = city_state_match.group(2)
            return f"{street_num} {street_name}, {city}, {state}"
        else:
            # Just return street address
            return f"{street_num} {street_name}"
    
    # If no pattern match, return cleaned version
    return address.strip()

@router.get("/packages/{package_id}/analysis")
async def get_package_analysis(package_id: str):
    """
    Retrieve the analysis result for a deal package.
    """
    analysis_data = await storage_service.get_analysis_result(package_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail=f"Analysis not found for package {package_id}")
    
    return analysis_data


@router.post("/packages/{package_id}/analyze")
async def analyze_deal_package(
    package_id: str,
    request: Request,
    gemini_service: GeminiService = Depends(get_gemini_service),
    openai_service: Any = Depends(get_openai_service),
    progress_service: ProgressService = Depends(get_progress_service),
    explainability_service: ExplainabilityService = Depends(get_explainability_service),
):
    """
    Perform financial analysis on a multi-document deal package.
    """
    # Initialize locals from request
    progress_base = 0
    completed_files = None
    deal_parameters = {}

    # DEBUG: Handle Request Body Manually to avoid 422
    try:
        body = await request.json()
        logger.info(f"DEBUG: /analyze raw body for package {package_id}: {body}")
        
        # Handle deal_parameters
        if "deal_parameters" in body and isinstance(body["deal_parameters"], dict):
            deal_parameters = body["deal_parameters"]
        else:
            # Assume root is params if not wrapped, but exclude known other keys
            deal_parameters = {k: v for k, v in body.items() if k not in ["progress_base", "completed_files"]}
            
        # Handle other params from body if present
        if "progress_base" in body:
            try:
                progress_base = int(body["progress_base"])
            except: pass
            
        if "completed_files" in body and isinstance(body["completed_files"], list):
             completed_files = body["completed_files"]
                 
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        deal_parameters = {}
    
    # Also check Query Params for progress_base/completed_files just in case
    # (Though internal calls pass them directly, external API calls use body or query)
    if not progress_base and "progress_base" in request.query_params:
         try:
             progress_base = int(request.query_params["progress_base"])
         except: pass

    # Delegate to logic function
    return await _analyze_deal_package_logic(
        package_id=package_id,
        deal_parameters=deal_parameters,
        gemini_service=gemini_service,
        openai_service=openai_service,
        progress_service=progress_service,
        explainability_service=explainability_service,
        progress_base=progress_base,
        completed_files=completed_files
    )

async def _analyze_deal_package_logic(
    package_id: str,
    deal_parameters: Dict[str, Any],
    gemini_service: GeminiService,
    openai_service: Any,
    progress_service: ProgressService,
    explainability_service: ExplainabilityService,
    progress_base: int = 0,
    completed_files: List[str] = None
):
    """
    Internal logic for financial analysis, extracted for reuse.
    """
    # Import schemas locally to avoid circular deps if any
    from app.models.schemas import (
        UnderwritingAnalysis, DealParameters, PropertyMeta,
        RentRollItem, RentRollSummary, StandardizedExpense,
        ExpenseCategory, AuditLog, StudentHousingConfig
    )
    from app.services.financial_service import FinancialService
    from app.services.audit_log_service import AuditLogService
    from app.services.excel_service import ExcelService
    from app.services.memo_service import MemoService
    from app.services.synthesis_service import SynthesisService
    import math

    def sanitize_float(val):
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return 0.0
            return f
        except (ValueError, TypeError):
            return 0.0
    
    logger.info(f"Starting FRESH multi-document analysis (Optimized V2) for package: {package_id}")
    logger.info(f"Received deal parameters: {deal_parameters}")
    
    async def update_progress(pct: int, msg: str):
        # Scale pct from 0-100 to progress_base-100
        # If pct is 0 (error), keep it 0
        details = None
        if completed_files:
            details = {
                "completed_files": completed_files,
                "status": "processing" if pct < 100 else "completed"
            }
            
        if pct == 0:
            await progress_service.update_progress(package_id, 0, msg, details=details)
            return
            
        scaled_pct = progress_base + int((pct / 100) * (100 - progress_base))
        await progress_service.update_progress(package_id, scaled_pct, msg, details=details)

    await update_progress(5, "Initializing analysis...")
    
    # Get the deal package from storage
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    package = DealPackage(**package_data)
    
    # Check if package has been normalized
    if package.normalization_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="Package has not been normalized yet. Please run normalization first."
        )
    
    # Parse deal parameters
    try:
        logger.info(f"Raw deal_parameters received: {deal_parameters}")
        params = DealParameters(**deal_parameters)
        
        # Explicitly force loan_amount from raw dict if present
        if "loan_amount" in deal_parameters and deal_parameters["loan_amount"] is not None:
            try:
                raw_loan = float(deal_parameters["loan_amount"])
                if raw_loan > 0:
                    params.loan_amount = raw_loan
                    logger.info(f"Forced loan_amount from raw dict: {params.loan_amount}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse loan_amount from raw dict: {e}")

        # Sanitize params immediately
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
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid deal parameters: {str(e)}")
    
    # Initialize services
    audit_log_service = AuditLogService()
    financial_service = FinancialService(audit_log_service=audit_log_service)
    excel_service = ExcelService()
    memo_service = MemoService(gemini_service=gemini_service, openai_service=openai_service)
    ingestion_service = IngestionService()
    synthesis_service = SynthesisService()
    
    # ===== STEP 1: LOAD PACKAGE DATA (NEW SEGMENTED FLOW) =====
    
    await update_progress(20, "Aggregating package data...")
    
    # Financials (Expenses)
    # Prefer normalized_data as it is the source of truth for user verifications/corrections
    normalized_items = package.normalized_data if package.normalized_data else package.financials_data
    
    # Sort items to prioritize user-verified ones
    if normalized_items:
        normalized_items = sorted(normalized_items, key=lambda x: x.user_verified, reverse=True)

    # Rent Roll
    rent_roll_items = package.rent_roll_data
    
    logger.info(f"Using {len(normalized_items)} normalized items and {len(rent_roll_items)} rent roll items for analysis")
    
    # ===== STEP 2: SYNTHESIZE DATA FROM ALL DOCUMENTS (OMNISCIENT PATTERN) =====
    
    await update_progress(30, "Synthesizing property metadata from all documents...")
    
    # --- Verification Agents (Non-OM Flow) ---
    verification_audit_logs = []

    # NEW: Contextual Data Verification Agent (Applies to ALL extracted items)
    # This fulfills the request to apply "Contextual Analysis" to all values
    if normalized_items:
        try:
            logger.info(f"Running Contextual Data Verification Agent on {len(normalized_items)} items...")
            await update_progress(35, "Verifying data quality with AI context...")

            # 1. Group items by Document to optimize text fetching
            items_by_doc = {}
            for item in normalized_items:
                doc_id = item.metadata.get("document_id")
                if not doc_id: continue
                if doc_id not in items_by_doc:
                    items_by_doc[doc_id] = []
                items_by_doc[doc_id].append(item)

            verified_items_results = []
            # Semaphore to avoid overwhelming LLM API with too many parallel batches
            audit_sem = asyncio.Semaphore(5)

            async def process_doc_audit(doc_id, items):
                nonlocal verified_items_results
                # Fetch document text once
                full_text = ""
                source_filename = items[0].source_document or "unknown.pdf"

                # 1. Try OCR Backend first (Fastest/Best)
                try:
                    full_text = await ingestion_service.ocr_backend_client.get_document_text(doc_id)
                except Exception as e:
                    logger.warning(f"Backend text fetch failed for {doc_id} in generic audit: {e}")

                # 2. Fallback to Storage Service (GCP/Local) if backend failed
                if not full_text:
                    try:
                        content = None
                        if doc_id in file_storage_cache:
                            content = file_storage_cache[doc_id]["content"]
                        else:
                            ext = Path(source_filename).suffix
                            storage_path = f"deal-packages/{package_id}/documents/{doc_id}{ext}"
                            content = await storage_service.get_document_file(storage_path)

                        if content and source_filename.lower().endswith(".pdf"):
                            import PyPDF2
                            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                            text_pages = []
                            # Extract text from first 25 pages for generic audit (faster than 40)
                            for p_idx, page in enumerate(pdf_reader.pages[:25]):
                                text_pages.append(page.extract_text())
                            full_text = "\n".join(text_pages)
                            logger.info(f"Recovered text from storage for {source_filename} in generic audit ({len(full_text)} chars)")
                    except Exception as ex:
                        logger.warning(f"Storage extraction failed for {doc_id} in generic audit: {ex}")

                if not full_text: return

                # Prepare candidates with context
                candidates_to_verify = []
                for item in items:
                    # NEW: Skip items already verified by user. User is ALWAYS right.
                    if item.user_verified:
                        continue

                    # OPTIMIZATION: Skip very small/zero items that are already "Other"
                    # We want to verify High Stakes values (Price, Units, Large Expenses)
                    amount = item.metadata.get("amount", 0.0)
                    if amount == 0 and item.normalized_value in ["Other Operating Expenses", "Uncategorized"]:
                        continue

                    # Center context window on item.raw_text
                    window_text = full_text[:2000]
                    if item.raw_text and item.raw_text in full_text:
                        idx = full_text.find(item.raw_text)
                        start = max(0, idx - 1000)
                        end = min(len(full_text), idx + 1000)
                        window_text = full_text[start:end]
                    
                    candidates_to_verify.append({
                        "id": item.id,
                        "raw_text": item.raw_text,
                        "current_category": item.normalized_value,
                        "amount": amount,
                        "context": window_text,
                        "source": item.source_document
                    })

                if not candidates_to_verify: return

                # Batch verify items (max 25 per LLM call)
                BATCH_SIZE = 25
                audit_tasks = []

                async def run_audit_batch(batch):
                    async with audit_sem:
                        logger.info(f"Verifying batch of {len(batch)} items from {doc_id}")
                        return await synthesis_service.verify_items_contextual(batch, gemini_service)

                for i in range(0, len(candidates_to_verify), BATCH_SIZE):
                    batch = candidates_to_verify[i:i+BATCH_SIZE]
                    audit_tasks.append(run_audit_batch(batch))
                
                if audit_tasks:
                    batch_results = await asyncio.gather(*audit_tasks)
                    for res_list in batch_results:
                        if res_list:
                            verified_items_results.extend(res_list)

            # Parallelize across documents
            doc_audit_tasks = [process_doc_audit(doc_id, items) for doc_id, items in items_by_doc.items()]
            await asyncio.gather(*doc_audit_tasks)

            # 2. Apply Verification Results
            # Create map for fast lookup
            results_map = {res.get("id"): res for res in verified_items_results if isinstance(res, dict)}

            final_normalized_items = []
            for item in normalized_items:
                res = results_map.get(item.id)
                if res:
                    # Update category if AI suggests "perfect" one
                    if res.get("perfect_category"):
                        item.normalized_value = res["perfect_category"]

                    # Update group
                    if res.get("perfect_group"):
                        try:
                            from app.models.schemas import CategoryGroup
                            item.category_group = CategoryGroup(res["perfect_group"])
                        except: pass

                    # Log reasoning
                    if res.get("reasoning"):
                        item.metadata["verification_reasoning"] = res["reasoning"]

                    # Keep only if beneficial
                    if res.get("beneficial", True):
                        final_normalized_items.append(item)
                    else:
                        logger.info(f"Contextual Agent rejected non-beneficial item: {item.raw_text} ({item.normalized_value})")
                        verification_audit_logs.append({
                            "field_name": f"Excluded: {item.normalized_value}",
                            "extracted_value": item.raw_text,
                            "source": item.source_document,
                            "confidence_score": 1.0,
                            "method": "Contextual Verification Agent",
                            "reasoning": res.get("reasoning", "Item marked as non-beneficial or garbage.")
                        })
                else:
                    # Keep items that weren't verified (e.g. no doc context)
                    final_normalized_items.append(item)

            # Update the list for synthesis
            normalized_items = final_normalized_items
            logger.info(f"Contextual verification complete. Items remaining: {len(normalized_items)}")

        except Exception as e:
            logger.error(f"Error in global contextual verification: {e}")
            # Continue with original items if agent fails

    # Run Metadata Synthesizer
    synthesized_metadata = synthesis_service.synthesize_property_metadata(normalized_items)
    
    if package.underwriting_flow == "MULTI_SOURCE":
        try:
            logger.info("Running Purchase Price Verification Agent (Non-OM Flow)...")
            pp_candidates = []
            
            # Helper to extract numeric value from text if metadata missing
            def extract_price_from_text(text):
                import re
                # Look for $XX,XXX,XXX patterns
                matches = re.findall(r'\$\s?([0-9,]+)', text)
                if matches:
                    try:
                        # Return the largest value found (heuristic)
                        vals = [float(m.replace(",", "")) for m in matches]
                        return max(vals)
                    except: pass
                return 0.0

            # 1. Identify Candidates
            for item in normalized_items:
                # Check for Purchase Price items
                is_pp = False
                if item.normalized_value == "Purchase Price":
                    is_pp = True
                elif item.raw_text and ("purchase price" in item.raw_text.lower() or "sale price" in item.raw_text.lower() or "contract price" in item.raw_text.lower()):
                    is_pp = True

                # Exclude explicit Deposits/Earnest Money
                if item.normalized_value == "Deposit" or (item.raw_text and ("deposit" in item.raw_text.lower() or "earnest money" in item.raw_text.lower())):
                    is_pp = False
                
                if is_pp:
                    doc_id = item.metadata.get("document_id")
                    if not doc_id: continue
                    
                    # Determine value
                    val = 0.0
                    if item.metadata and item.metadata.get("amount"):
                        try: val = float(item.metadata.get("amount"))
                        except: pass
                    
                    if val == 0.0 and item.raw_text:
                        val = extract_price_from_text(item.raw_text)
                    
                    if val > 10000: # Filter out small amounts/noise
                        # Fetch context robustly
                        full_text = ""
                        source_filename = item.source_document or "unknown.pdf"
                        
                        # 1. Try OCR Backend first (Fastest/Best)
                        try:
                            full_text = await ingestion_service.ocr_backend_client.get_document_text(doc_id)
                        except Exception as e:
                            logger.warning(f"Backend text fetch failed for {doc_id} in PP verify: {e}")
                        
                        # 2. Fallback to Storage Service (GCP/Local) if backend failed
                        # This handles cases where server restarted and cache is empty, or backend 404s
                        if not full_text:
                            try:
                                # Try cache first
                                content = None
                                if doc_id in file_storage_cache:
                                    content = file_storage_cache[doc_id]["content"]
                                else:
                                    # Fetch from storage
                                    ext = Path(source_filename).suffix
                                    storage_path = f"deal-packages/{package_id}/documents/{doc_id}{ext}"
                                    content = await storage_service.get_document_file(storage_path)
                                
                                if content and source_filename.lower().endswith(".pdf"):
                                    import PyPDF2
                                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                                    text_pages = []
                                    # Extract text from first 20 pages (PSA/OM usually has price early)
                                    for p_idx, page in enumerate(pdf_reader.pages[:20]):
                                        text_pages.append(page.extract_text())
                                    full_text = "\n".join(text_pages)
                                    logger.info(f"Recovered text from storage for {source_filename} in PP verify ({len(full_text)} chars)")
                            except Exception as ex:
                                logger.warning(f"Storage extraction failed for {doc_id} in PP verify: {ex}")

                        if full_text:
                            # Extract relevant window (centered on raw_text match)
                            # Expanded window to 5000 chars to capture more context
                            window_text = full_text[:5000]
                            
                            # If we found the specific text, center on it
                            if item.raw_text and item.raw_text in full_text:
                                idx = full_text.find(item.raw_text)
                                start = max(0, idx - 2000)
                                end = min(len(full_text), idx + 3000)
                                window_text = full_text[start:end]
                            
                            pp_candidates.append({
                                "value": val,
                                "source": item.source_document,
                                "text_context": window_text,
                                "document_id": doc_id
                            })
                        else:
                            logger.warning(f"Could not retrieve text context for Purchase Price candidate in {item.source_document} (ID: {doc_id})")

            # 2. Run Verification if candidates exist
            if pp_candidates:
                verified_result = await synthesis_service.verify_purchase_price(pp_candidates, gemini_service)
                
                if verified_result and verified_result.get("value", 0) > 0:
                    v_val = verified_result["value"]
                    v_conf = verified_result.get("confidence", 0.0)
                    v_source = verified_result.get("source", "Verification Agent")
                    v_reason = verified_result.get("reasoning", "")
                    
                    logger.info(f"Verified Purchase Price: ${v_val:,.2f} (Conf: {v_conf})")
                    
                    # Update synthesized metadata - Only if user hasn't manually verified a price already
                    if synthesized_metadata.get("purchase_price", {}).get("score", 0) < 2000:
                        synthesized_metadata["purchase_price"] = {
                            "value": v_val,
                            "source": f"Verified: {v_source}",
                            "score": 999 # High priority for AI-verified
                        }

                    verification_audit_logs.append({
                        "field_name": "Purchase Price (Verified)",
                        "extracted_value": f"${v_val:,.2f}",
                        "source": v_source,
                        "confidence_score": v_conf,
                        "method": "Verification Agent (Context Analysis)",
                        "reasoning": v_reason
                    })
                    
            else:
                logger.info("No Purchase Price candidates found for verification.")

            # --- Year Built Verification Agent ---
            logger.info("Running Year Built Verification Agent...")
            yb_candidates = []
            
            for item in normalized_items:
                is_yb = False
                if item.normalized_value == "Year Built":
                    is_yb = True
                elif item.raw_text and ("year built" in item.raw_text.lower() or "date of construction" in item.raw_text.lower()):
                    is_yb = True
                
                if is_yb:
                    doc_id = item.metadata.get("document_id")
                    if not doc_id: continue
                    
                    val = 0
                    if item.metadata and item.metadata.get("amount"):
                        try: val = int(float(item.metadata.get("amount")))
                        except: pass
                    
                    # If val is 0, try regex on raw_text
                    if val == 0 and item.raw_text:
                        import re
                        matches = re.findall(r'\b(18\d{2}|19\d{2}|20\d{2})\b', item.raw_text)
                        if matches:
                            try: val = int(matches[0])
                            except: pass

                    if val > 1800 and val < 2030:
                        # Fetch context (Reuse logic)
                        full_text = ""
                        source_filename = item.source_document or "unknown.pdf"
                        
                        try:
                            full_text = await ingestion_service.ocr_backend_client.get_document_text(doc_id)
                        except: pass
                        
                        if not full_text:
                            try:
                                content = None
                                if doc_id in file_storage_cache:
                                    content = file_storage_cache[doc_id]["content"]
                                else:
                                    ext = Path(source_filename).suffix
                                    storage_path = f"deal-packages/{package_id}/documents/{doc_id}{ext}"
                                    content = await storage_service.get_document_file(storage_path)
                                
                                if content and source_filename.lower().endswith(".pdf"):
                                    import PyPDF2
                                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                                    text_pages = []
                                    for p_idx, page in enumerate(pdf_reader.pages[:20]):
                                        text_pages.append(page.extract_text())
                                    full_text = "\n".join(text_pages)
                            except: pass
                        
                        if full_text:
                            window_text = full_text[:3000]
                            if item.raw_text and item.raw_text in full_text:
                                idx = full_text.find(item.raw_text)
                                start = max(0, idx - 1000)
                                end = min(len(full_text), idx + 1000)
                                window_text = full_text[start:end]
                            
                            yb_candidates.append({
                                "value": val,
                                "source": item.source_document,
                                "text_context": window_text,
                                "document_id": doc_id
                            })

            if yb_candidates:
                verified_yb = await synthesis_service.verify_year_built(yb_candidates, gemini_service)
                if verified_yb and verified_yb.get("value", 0) > 0:
                    v_val = verified_yb["value"]
                    v_conf = verified_yb.get("confidence", 0.0)
                    v_source = verified_yb.get("source", "Verification Agent")
                    v_reason = verified_yb.get("reasoning", "")
                    
                    logger.info(f"Verified Year Built: {v_val} (Conf: {v_conf})")
                    
                    # Update synthesized metadata - Only if user hasn't manually verified a year built already
                    if synthesized_metadata.get("year_built", {}).get("score", 0) < 2000:
                        synthesized_metadata["year_built"] = {
                            "value": v_val,
                            "source": f"Verified: {v_source}",
                            "score": 999
                        }
                    
                    verification_audit_logs.append({
                        "field_name": "Year Built (Verified)",
                        "extracted_value": str(v_val),
                        "source": v_source,
                        "confidence_score": v_conf,
                        "method": "Verification Agent (Conflict Resolution)",
                        "reasoning": v_reason
                    })
            

        except Exception as e:
            logger.error(f"Error in Verification Agents: {e}")
            # Continue without failing the whole analysis

    # Note: If rent roll has more units than found in expenses/OM, update it
    if rent_roll_items:
        rr_units = len(rent_roll_items)
        if rr_units > synthesized_metadata['total_units']['value']:
             synthesized_metadata['total_units'] = {
                 "value": rr_units,
                 "source": "Rent Roll Data",
                 "score": 90
             }
    
    logger.info("=== SYNTHESIZED METADATA ===")
    logger.info(f"Purchase Price: ${synthesized_metadata['purchase_price']['value']:,.2f} (from {synthesized_metadata['purchase_price']['source']})")
    logger.info(f"Total Units: {synthesized_metadata['total_units']['value']} (from {synthesized_metadata['total_units']['source']})")
    logger.info(f"Year Built: {synthesized_metadata['year_built']['value']} (from {synthesized_metadata['year_built']['source']})")
    
    # Initialize Property Meta with synthesized values
    extracted_name = synthesized_metadata.get('property_name', {}).get('value')
    extracted_address = synthesized_metadata.get('address', {}).get('value')
    
    if extracted_address:
        logger.info(f"Using Synthesized Property Address: {extracted_address}")
    
    # Defaults based on Underwriting Flow
    is_flow_a = (package.underwriting_flow == "OM_DRIVEN")
    default_year_built = 0 if is_flow_a else 1980
    default_address = "Missing in OM" if is_flow_a else _clean_address(package.property_name)

    property_meta = PropertyMeta(
        property_name=str(extracted_name) if extracted_name else None,
        address=str(extracted_address) if extracted_address else default_address,
        year_built=synthesized_metadata['year_built']['value'] if synthesized_metadata['year_built']['value'] > 0 else default_year_built,
        purchase_price=synthesized_metadata['purchase_price']['value'],
        total_units=synthesized_metadata['total_units']['value'],
        is_renovated=False,
        current_loan_balance=synthesized_metadata.get('current_loan_balance', {}).get('value', 0.0)
    )
    
    # Extract rent roll items (Use pre-processed Rent Roll data if available)
    await update_progress(40, "Building master rent roll from all documents...")
    
    rent_roll: List[RentRollItem] = []
    
    if rent_roll_items:
        # We already extracted rent rolls during normalization phase
        rent_roll = synthesis_service.build_master_rent_roll(rent_roll_items)
        logger.info(f"Master rent roll built from {len(rent_roll_items)} raw items -> {len(rent_roll)} unique units")
    else:
        # Fallback for legacy packages or if extraction failed
        # Try to extract rent roll from OM first (if available) for backward compatibility
        selected_om = None
        om_docs = package.documents.get(DocumentType.OFFERING_MEMORANDUM, [])
        if om_docs:
            selected_om = om_docs[0]
            if len(om_docs) > 1 and package.property_name:
                prop_parts = package.property_name.lower().split()
                best_score = 0
                for doc in om_docs:
                    score = sum(1 for p in prop_parts if p in doc.filename.lower())
                    if score > best_score:
                        best_score = score
                        selected_om = doc
            
            try:
                doc_id = selected_om.document_id
                file_content = None
                if doc_id in file_storage_cache:
                    file_content = file_storage_cache[doc_id].get("content")
                else:
                    extension = Path(selected_om.filename).suffix
                    storage_path = f"deal-packages/{package_id}/documents/{doc_id}{extension}"
                    file_content = await storage_service.get_document_file(storage_path)
                
                if file_content:
                    target_units = property_meta.total_units if property_meta.total_units > 0 else 0
                    
                    # Check file type and use appropriate extraction method
                    extension = Path(selected_om.filename).suffix.lower()
                    if extension in ['.xlsx', '.xls']:
                        # Use Excel-specific extraction
                        om_rent_roll = await ingestion_service.extract_rent_roll_from_excel(
                            file_content,
                            total_units=target_units
                        )
                    else:
                        # Use PDF extraction
                        om_rent_roll = await ingestion_service.extract_rent_roll_from_pdf(
                            file_content,
                            total_units=target_units
                        )
                    
                    if om_rent_roll:
                        rent_roll.extend(om_rent_roll)
                        logger.info(f"Extracted {len(om_rent_roll)} rent roll items from OM")
            except Exception as e:
                logger.warning(f"Failed to extract rent roll from OM: {e}")
        
        # Run Rent Roll Accumulator (Deduplication by unit number)
        if rent_roll:
            rent_roll = synthesis_service.build_master_rent_roll(rent_roll)
            logger.info(f"Master rent roll built with {len(rent_roll)} unique units")

    # Apply Manual Overrides for Property Meta (Overrides everything)
    if package.manual_overrides:
        if "total_units" in package.manual_overrides:
            property_meta.total_units = int(package.manual_overrides["total_units"])
            logger.info(f"Applied manual override for total_units: {property_meta.total_units}")
        if "purchase_price" in package.manual_overrides:
            property_meta.purchase_price = float(package.manual_overrides["purchase_price"])
            logger.info(f"Applied manual override for purchase_price: {property_meta.purchase_price}")
        if "year_built" in package.manual_overrides:
            property_meta.year_built = int(package.manual_overrides["year_built"])
            logger.info(f"Applied manual override for year_built: {property_meta.year_built}")
        if "current_loan_balance" in package.manual_overrides:
            property_meta.current_loan_balance = float(package.manual_overrides["current_loan_balance"])
            logger.info(f"Applied manual override for current_loan_balance: {property_meta.current_loan_balance}")
            
    historical_expenses: List[StandardizedExpense] = []
    
    # Parse normalized items for expenses only (property metadata already synthesized)
    for item in normalized_items:
        # Check if this is an expense item
        if item.field_type == "expense_category" or (hasattr(item, 'category_group') and item.category_group in ["Operating Expense", "Tax & Insurance"]):
            try:
                # Parse the category
                # Fallback to Other OpEx if unknown
                try:
                    # Priority: User Correction > Normalized Value
                    category_to_use = item.user_correction or item.normalized_value
                    category = ExpenseCategory(category_to_use)
                except ValueError:
                    category = ExpenseCategory.OTHER_OPERATING_EXPENSES
                
                # If the normalized_value is MARKETING or ADVERTISING (legacy), remap it to ADVERTISING_MARKETING
                if (item.user_correction or item.normalized_value) in ["Marketing", "Advertising"]:
                    category = ExpenseCategory.ADVERTISING_MARKETING
                
                # Use amount from metadata if available, otherwise parse from text
                amount = 0.0
                if item.metadata:
                    val = item.metadata.get("amount")
                    if val is not None:
                        amount = sanitize_float(val)
                
                # Parser Fallback (Only if not verified by user)
                if amount == 0.0 and not item.user_verified and "$" in item.raw_text:
                    amount_str = item.raw_text.split("$")[-1].replace(",", "").strip()
                    amount = sanitize_float(amount_str)
                    if amount == 0.0:
                        # For Flow A, do not auto-guess values
                        if is_flow_a:
                            amount = 0.0
                        else:
                            amount = 1000.0  # Default fallback for Flow B
                
                # Get document_id from metadata if available
                doc_id = item.metadata.get("document_id") if item.metadata else None
                page_number = item.metadata.get("page_number") if item.metadata else None
                bbox = item.metadata.get("bbox") if item.metadata else None
                expense_year = item.metadata.get("expense_year") if item.metadata else None

                expense = StandardizedExpense(
                    id=item.id,
                    original_text=item.raw_text,
                    mapped_category=category,
                    amount=amount,
                    amount_t3=sanitize_float(item.metadata.get("amount_t3")) if item.metadata and item.metadata.get("amount_t3") is not None else None,
                    amount_t6=sanitize_float(item.metadata.get("amount_t6")) if item.metadata and item.metadata.get("amount_t6") is not None else None,
                    amount_t9=sanitize_float(item.metadata.get("amount_t9")) if item.metadata and item.metadata.get("amount_t9") is not None else None,
                    confidence=sanitize_float(item.confidence),
                    audit_log=AuditLog(
                        field_name="expense",
                        extracted_value=amount,
                        source=item.source_document,
                        confidence_score=sanitize_float(item.confidence),
                        method=f"Extracted from {item.source_document}",
                        document_id=doc_id,
                        page_number=page_number,
                        bbox=bbox
                    ),
                    user_verified=item.user_verified,
                    user_corrected_category=None,
                    expense_year=expense_year
                )
                
                # Safely attempt to set user_corrected_category if it matches enum
                if item.user_correction:
                    try:
                        expense.user_corrected_category = ExpenseCategory(item.user_correction)
                    except ValueError:
                        logger.warning(f"User correction '{item.user_correction}' is not a valid ExpenseCategory enum value")
                historical_expenses.append(expense)
            except Exception as e:
                logger.warning(f"Could not parse expense item: {item.raw_text}, error: {str(e)}")
    
    # Deduplicate expenses
    if historical_expenses:
        logger.info(f"Expenses before deduplication: {len(historical_expenses)}")
        historical_expenses = synthesis_service.deduplicate_expenses(historical_expenses)
        logger.info(f"Expenses after deduplication: {len(historical_expenses)}")

    # Check for Rent Roll in Manual Overrides
    if package.manual_overrides and "rent_roll" in package.manual_overrides:
        try:
            manual_rr = package.manual_overrides["rent_roll"]
            if isinstance(manual_rr, list) and len(manual_rr) > 0:
                rent_roll = []
                for item in manual_rr:
                    # Handle dictionary or object
                    if isinstance(item, dict):
                        rent_roll.append(RentRollItem(**item))
                    else:
                        rent_roll.append(item)
                logger.info(f"Using manual override for Rent Roll with {len(rent_roll)} units")
        except Exception as e:
            logger.error(f"Failed to apply rent roll override: {e}")

    # Create a basic rent roll if none exists
    if not rent_roll:
        if package.underwriting_flow == "OM_DRIVEN":
            logger.warning("Flow A (OM_DRIVEN): No rent roll found in OM. Flagging as Missing.")
            # Do NOT generate placeholders for Flow A
            # We will rely on flagging it in the analysis or summary
        else:
            # Flow B: Generate placeholder rent roll based on property size (Auto-guess allowed)
            logger.info("Flow B: Generating placeholder rent roll.")
            num_units = property_meta.total_units or 0
            for i in range(num_units):
                rent_roll.append(RentRollItem(
                    unit_number=f"Unit {i+1}",
                    unit_type="1BR",
                    unit_size=750,
                    tenant_name="Occupied",
                    current_rent=2000.0,
                    stabilized_rent=2200.0,
                    market_rent=2100.0,
                    move_in_date="",
                    lease_start="2024-01-01",
                    lease_end="2024-12-31"
                ))
    
    # Calculate rent roll summary
    total_units = len(rent_roll)
    occupied_units = sum(1 for unit in rent_roll if unit.current_rent > 0)
    occupied_sf = sum((unit.unit_size or 0) for unit in rent_roll if unit.current_rent > 0)
    occupancy_rate = occupied_units / total_units if total_units > 0 else 0
    
    total_monthly_rent = sum(unit.current_rent for unit in rent_roll)
    total_annual_rent = total_monthly_rent * 12
    total_stabilized_rent = sum((unit.stabilized_rent or 0.0) for unit in rent_roll)
    total_market_rent = sum((unit.market_rent or 0.0) for unit in rent_roll)
    total_unit_size = sum((unit.unit_size or 0) for unit in rent_roll)

    # Averages
    avg_unit_size = total_unit_size / total_units if total_units > 0 else 0
    
    avg_rent_per_unit = total_monthly_rent / occupied_units if occupied_units > 0 else 0
    avg_rent_per_sf = total_monthly_rent / occupied_sf if occupied_sf > 0 else 0

    avg_stabilized_per_unit = total_stabilized_rent / total_units if total_units > 0 else 0
    avg_stabilized_per_sf = total_stabilized_rent / total_unit_size if total_unit_size > 0 else 0

    avg_market_per_unit = total_market_rent / total_units if total_units > 0 else 0
    avg_market_per_sf = total_market_rent / total_unit_size if total_unit_size > 0 else 0
    
    # Apply Manual Overrides for GPR/Rent
    if package.manual_overrides:
        if "total_units" in package.manual_overrides:
             # If manual override exists, it takes precedence if extraction failed
             manual_units = int(package.manual_overrides["total_units"])
             if total_units == 0 or total_units != manual_units:
                 total_units = manual_units
                 # Adjust occupancy if needed (assume 95% if no data?)
                 if occupied_units == 0:
                     occupied_units = int(total_units * 0.95)
                     occupancy_rate = 0.95
        
        if "gross_potential_rent" in package.manual_overrides:
            manual_gpr = float(package.manual_overrides["gross_potential_rent"])
            if total_annual_rent == 0:
                total_annual_rent = manual_gpr
                total_monthly_rent = manual_gpr / 12
    
    rent_roll_summary = RentRollSummary(
        total_units=total_units,
        occupied_units=occupied_units,
        occupancy_rate=occupancy_rate,
        avg_unit_size=avg_unit_size,
        total_monthly_rent=total_monthly_rent,
        total_annual_rent=total_annual_rent,
        total_stabilized_rent=total_stabilized_rent,
        total_market_rent=total_market_rent,
        avg_rent_per_unit=avg_rent_per_unit,
        avg_rent_per_sf=avg_rent_per_sf,
        avg_stabilized_per_unit=avg_stabilized_per_unit,
        avg_stabilized_per_sf=avg_stabilized_per_sf,
        avg_market_per_unit=avg_market_per_unit,
        avg_market_per_sf=avg_market_per_sf
    )
    
    # Update property meta total units if 0
    if property_meta.total_units == 0 and total_units > 0:
        property_meta.total_units = total_units

    # Apply Transient Overrides from DealParameters (Frontend "Edit" Mode)
    if params.units_override is not None:
        property_meta.total_units = params.units_override
        logger.info(f"Applied transient override for Total Units: {property_meta.total_units}")

    if params.purchase_price_override is not None:
        property_meta.purchase_price = params.purchase_price_override
        logger.info(f"Applied transient override for Purchase Price: {property_meta.purchase_price}")
    
    # Check for existing analysis to preserve persistent configurations (like student housing config)
    existing_analysis_dict = await storage_service.get_analysis_result(package_id)
    existing_student_config = None
    existing_commentary = None
    existing_memo = None
    
    # Priority 1: Check Manual Overrides (from Frontend Save)
    if package.manual_overrides and "student_housing_config" in package.manual_overrides:
        try:
            from app.models.schemas import StudentHousingConfig
            config_data = package.manual_overrides["student_housing_config"]
            if config_data:
                existing_student_config = StudentHousingConfig(**config_data)
                logger.info("Restored student housing config from Manual Overrides")
        except Exception as e:
            logger.warning(f"Failed to restore student housing config from overrides: {e}")

    # Priority 2: Check Existing Analysis (Fallback)
    if existing_analysis_dict:
        # Student Config
        if not existing_student_config and "student_housing_config" in existing_analysis_dict:
            try:
                # Parse it to ensure validity
                from app.models.schemas import StudentHousingConfig
                if existing_analysis_dict["student_housing_config"]:
                    existing_student_config = StudentHousingConfig(**existing_analysis_dict["student_housing_config"])
                    logger.info("Restored student housing config from Previous Analysis")
            except Exception as e:
                logger.warning(f"Failed to restore student housing config from analysis: {e}")
        
        # We want to regenerate commentary and memo to reflect updated values
        existing_commentary = None
        existing_memo = None

    # Create analysis object
    analysis = UnderwritingAnalysis(
        document_id=package_id,
        underwriting_flow=package.underwriting_flow or "MULTI_SOURCE",
        pass_fail_status="PENDING",
        gating_reasons=[],
        property_meta=property_meta,
        primary_fiscal_year=package.primary_fiscal_year,
        is_partial_year=package.is_partial_year,
        rent_roll=rent_roll,
        rent_roll_summary=rent_roll_summary,
        historical_expenses=historical_expenses,
        deal_parameters=params,
        audit_trail=[],
        pro_forma_expenses_detailed=[],
        pro_forma_noi=0.0,
        pro_forma_expenses=0.0,
        cap_rate=0.0,
        exit_cap_rate=params.exit_cap_rate,
        historical_noi=0.0,
        historical_total_expenses=0.0,
        historical_cap_rate=0.0,
        om_proforma=package.om_proforma_data,
        student_housing_config=existing_student_config,
        analyst_commentary=existing_commentary,
        investment_memo=existing_memo
    )
    
    logger.info(f"Built analysis object with {len(rent_roll)} units and {len(historical_expenses)} expenses")

    # Populate Audit Trail with Ingestion Data
    audit_log_service.add_ingestion_logs(analysis, synthesized_metadata=synthesized_metadata)
    
    # Add Verification Logs
    if verification_audit_logs:
        if analysis.audit_trail is None:
            analysis.audit_trail = []
        analysis.audit_trail.extend(verification_audit_logs)

    # ===== STEP 3: CHECK DEAL VIABILITY =====
    await update_progress(50, "Checking deal viability criteria...")
    viability_check = financial_service.check_deal_viability(analysis)
    logger.info(f"Viability check: {viability_check['status']}")
    
    # Log the check to the audit trail
    audit_log_service.add_log(
        analysis,
        "Deal Viability Status",
        viability_check["status"],
        "Gating Logic",
        "Checked: Units, Loan Amount, Vintage vs. Criteria",
        1.0,
        {"reasons": viability_check["reasons"]}
    )

    if viability_check["status"] == "FAIL":
        analysis.pass_fail_status = "FAIL"
        analysis.gating_reasons = viability_check["reasons"]
        logger.warning(f"Deal failed viability check: {viability_check['reasons']}")
    
    # ===== STEP 4: CALCULATE FINANCIALS =====
    try:
        await update_progress(70, "Calculating financial projections...")
        # Calculate historical metrics
        historical_data = financial_service.calculate_historical(analysis)
        logger.info(f"Historical NOI: ${historical_data['historical_noi']:,.2f}")
        analysis.historical_noi = historical_data["historical_noi"]
        analysis.historical_cap_rate = historical_data["historical_cap_rate"]
        
        # Calculate pro forma metrics
        pro_forma_data = financial_service.calculate_pro_forma(analysis)
        logger.info(f"Pro Forma NOI: ${pro_forma_data['pro_forma_noi']:,.2f}")
        
        analysis.pro_forma_noi = pro_forma_data["pro_forma_noi"]
        analysis.pro_forma_expenses = pro_forma_data["pro_forma_expenses"]
        analysis.cap_rate = pro_forma_data["cap_rate"]
        analysis.exit_cap_rate = pro_forma_data.get("exit_cap_rate", params.exit_cap_rate)
        
    except Exception as e:
        logger.error(f"Financial calculation failed: {str(e)}", exc_info=True)
        await update_progress(0, f"Calculations failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Financial calculation failed: {str(e)}")
    
    # ===== STEP 4.5: GENERATE EXPLAINABILITY & CONCLUSION =====
    try:
        await update_progress(80, "Generating insights and explanations...")
        analysis = await explainability_service.generate_explanations(analysis)
        
        logger.info("Explainability metadata and conclusion generated successfully.")
    except Exception as e:
        logger.error(f"Explainability generation failed: {str(e)}")
        # Don't fail the pipeline for this, but log it
        analysis.gating_reasons.append(f"Explainability generation failed: {str(e)}")

    # ===== STEP 5: GENERATE OUTPUTS (Excel, Memo & Commentary) =====
    try:
        await update_progress(90, "Generating output models and AI commentary...")
        
        # 1. Excel (Synchronous/Fast)
        pro_forma_entries = excel_service.generate_side_by_side_view(analysis)
        await excel_service.create_side_by_side_excel(pro_forma_entries, analysis_data=analysis)
        logger.info(f"Excel model generated for package: {package_id}")
        
        # 2. Parallel AI Tasks (Memo & Commentary) - ONLY IF MISSING
        async def task_commentary():
            if analysis.analyst_commentary:
                return
            try:
                await explainability_service.generate_analyst_commentary(analysis)
                logger.info("Analyst commentary generated.")
            except Exception as e:
                logger.error(f"Commentary generation failed: {e}")
                analysis.analyst_commentary = "Commentary unavailable."

        async def task_memo():
            if analysis.investment_memo:
                return
            try:
                logger.info("Generating investment memo...")
                memo_content = await memo_service.generate_investment_memo(analysis)
                analysis.investment_memo = memo_content
                logger.info("Investment memo generated successfully.")
            except Exception as e:
                logger.error(f"Memo generation failed: {e}")

        await asyncio.gather(task_commentary(), task_memo())
        
    except Exception as e:
        logger.warning(f"Output generation had issues (non-critical): {str(e)}")
    
    # ===== STEP 6: UPDATE PACKAGE STATUS AND SAVE ANALYSIS =====
    if analysis.pass_fail_status != "FAIL":
        analysis.pass_fail_status = "PASS"
    
    # Save the analysis result separately so it can be retrieved later
    analysis_dict = analysis.model_dump()
    await storage_service.save_analysis_result(package_id, analysis_dict)
    
    # Only update package status if it wasn't already completed
    # This avoids overwriting user verifications that might have happened during analysis
    # Always set status to completed and update timestamp
    # Use a targeted update to avoid overwriting user verifications (race condition)
    # We implement update_deal_package_status in storage_service to handle this
    await storage_service.update_deal_package_status(package_id, "completed")
    
    logger.info(f"Multi-document analysis complete for package {package_id}")
    logger.info(f"Final status: {analysis.pass_fail_status}")
    
    await update_progress(100, "Analysis complete!")
    return analysis
