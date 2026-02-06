"""
Multi-Document Upload and Normalization API Routes.
Handles the ingestion of ZIP files containing 8 folders of documents for a deal package.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging
import zipfile
import io
import os
from pathlib import Path
import shutil

from app.models.schemas import (
    DocumentType,
    DocumentMetadata,
    DealPackage,
    DocumentNormalizationResult,
    NormalizedDataItem,
    OMProformaTable
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
from app.dependencies import get_gemini_service, get_progress_service, get_explainability_service, get_classification_service, get_batch_logging_service
from app.services.zip_processing_service import ZipProcessingService, FOLDER_MAPPING

router = APIRouter(prefix="/api/v1/multi-document", tags=["Multi-Document Ingestion"])
logger = logging.getLogger(__name__)

# In-memory cache for quick access (backed by GCP storage)
deal_packages_cache = {}
# In-memory file storage (backed by GCP storage)
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
        
        # Update caches
        deal_packages_cache[package.package_id] = package
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
    classification_service: ClassificationService = Depends(get_classification_service)
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
        # If it's smart upload with multiple files, this logic might need adjustment if we uploaded multiple files separately
        # But assuming we zip them on frontend or upload 1 big zip for now?
        # WAIT: The prompt says "User can upload Zip/pngs/pdf/csv/exels/docs".
        # If the user uploads multiple individual files, the frontend typically sends them one by one or as a formData list.
        # But our chunk endpoint is designed for one large file stream.
        # Strategy: The frontend should ZIP the selected files if there are multiple loose files,
        # OR we need a new endpoint for multi-file upload.
        # Given "upload-chunk" flow, it assumes one binary blob.
        # Let's assume the frontend Zips selected files on the client side before chunking, OR sends a single Zip file.
        # If "is_smart_upload" is true, we treat the content as a ZIP that might contain loose files needing classification.

        combined_path = os.path.join(upload_dir, "combined_upload.tmp")
        
        with open(combined_path, "wb") as outfile:
            for chunk_file in chunk_files:
                chunk_path = os.path.join(upload_dir, chunk_file)
                with open(chunk_path, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)
        
        # Determine property name
        if not property_name:
             property_name = original_filename.replace('.zip', '').replace('_Inputs', '')

        if is_smart_upload:
            # For smart upload, we extract the zip (created by client or user) and process loose files
            # Check if it is a zip
            if not zipfile.is_zipfile(combined_path):
                 # It might be a single file uploaded directly?
                 # If so, we can wrap it in a list and process it.
                 # But our chunk flow is generic. Let's see if we can just pass it to zip_service
                 # If it's NOT a zip, we can't use zip_service.process_zip_file directly without modification or wrapper
                 
                 # Let's assume for now the frontend packages multiple files into a ZIP if needed.
                 # If single file (e.g. PDF), we should probably support that too.
                 
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
                # It is a zip, so we use the internal zip processor BUT we need to tell it to use classification
                # We need to use process_smart_upload by unzipping first
                files = []
                with zipfile.ZipFile(combined_path, 'r') as zip_ref:
                    for name in zip_ref.namelist():
                        if not name.endswith('/') and not os.path.basename(name).startswith('.'):
                            # Use full path for better classification context
                            files.append((name, zip_ref.read(name)))
                
                package, file_data_map = await zip_service.process_smart_upload(
                    files=files,
                    property_name=property_name,
                    classification_service=classification_service,
                    progress_service=progress_service,
                    task_id=upload_id
                )
        else:
            # Standard "Structured Zip" processing
            package, file_data_map = await zip_service.process_zip_file(
                combined_path,
                property_name,
                progress_service=progress_service,
                task_id=upload_id
            )
        
        # Update caches
        deal_packages_cache[package.package_id] = package
        file_storage_cache.update(file_data_map)
        
        # Cleanup
        try:
            shutil.rmtree(upload_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {upload_dir}: {str(e)}")
        
        # Check for missing info and attach validation warning to response if needed
        # We can calculate missing docs here
        required_types = {
            DocumentType.OFFERING_MEMORANDUM,
            DocumentType.RENT_ROLL,
            DocumentType.FINANCIALS
        }
        present_types = set()
        for dt, docs in package.documents.items():
            if docs:
                present_types.add(dt)
        
        missing = [dt.value for dt in required_types if dt not in present_types]
        
        # We can't easily change the return type schema dynamically to add "missing_info",
        # but we can add a transient field or frontend can check "documents" map.
        # Let's rely on frontend checking the returned package.documents
        
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
    classification_map = await classification_service.classify_files_batch(filenames)
    
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
        # For larger files, we might need a streaming approach or chunked upload similar to the main upload
        file_data = []
        for file in files:
            content = await file.read()
            file_data.append((file.filename, content))
            
        package, file_map = await zip_service.add_files_to_package(
            package_id=package_id,
            files=file_data,
            classification_service=classification_service
        )
        
        # Update caches
        deal_packages_cache[package.package_id] = package
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
    # Check cache first
    if package_id in deal_packages_cache:
        return deal_packages_cache[package_id]
    
    # Try to load from GCP storage
    package_data = await storage_service.get_deal_package(package_id)
    if package_data:
        package = DealPackage(**package_data)
        # Update cache
        deal_packages_cache[package_id] = package
        return package
    
    raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")


@router.get("/packages")
async def list_deal_packages(
    limit: int = 5,
    offset: int = 0
):
    """
    List deal packages with pagination.
    
    Args:
        limit: Maximum number of packages to return (default: 5)
        offset: Number of packages to skip (default: 0)
    
    Returns:
        Paginated response with packages and metadata
    """
    # Get paginated packages from GCP storage (optimized - only downloads what we need)
    packages_data, total = await storage_service.list_deal_packages(limit=limit, offset=offset)
    
    # Convert to DealPackage objects
    packages = []
    for pkg_data in packages_data:
        try:
            package = DealPackage(**pkg_data)
            packages.append(package)
            # Update cache
            deal_packages_cache[package.package_id] = package
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
    progress_service: ProgressService = Depends(get_progress_service),
    explainability_service: ExplainabilityService = Depends(get_explainability_service),
    batch_logging_service: BatchLoggingService = Depends(get_batch_logging_service)
):
    """
    Normalize documents in a package and automatically generate financial report.
    If document_type is provided, normalize only documents of that type.
    Otherwise, normalize all documents in the package.
    
    This endpoint extracts data, maps it to standardized categories,
    and automatically generates the financial analysis report.
    The user can then verify/modify categories and regenerate if needed.
    """
    await progress_service.update_progress(package_id, 5, "Initializing normalization...")
    
    # Check cache first
    if package_id in deal_packages_cache:
        package = deal_packages_cache[package_id]
    else:
        # Try to load from GCP storage
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
        package = DealPackage(**package_data)
        deal_packages_cache[package_id] = package
    
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
                # OMs also contain financials, so add to financial_docs too?
                # Actually, standard flow extracts proforma from OM.
                # Let's add to financial_docs as well so expenses are extracted.
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
    
    # --- 1. Process Rent Rolls (Segmented) ---
    extracted_rent_roll = []
    if rent_roll_docs:
        try:
            logger.info("Normalizing Rent Roll folder...")
            extracted_rent_roll = await extraction_service.process_rent_roll_documents(
                rent_roll_docs,
                progress_service=progress_service,
                task_id=package_id
            )
            package.rent_roll_data = extracted_rent_roll
            logger.info(f"Saved {len(extracted_rent_roll)} rent roll items to package")
        except Exception as e:
            logger.error(f"Error processing Rent Rolls: {e}")
            # Continue to other folders
            
    # --- 2. Process Financials / OM (Segmented) ---
    extracted_financials = []
    extracted_om_proforma = []
    
    if financial_docs:
        try:
            logger.info("Normalizing Financials/OM folders...")
            extracted_financials, extracted_om_proforma = await extraction_service.process_financial_documents(
                financial_docs,
                progress_service=progress_service,
                task_id=package_id
            )
            
            # Assign unique IDs to financials
            for idx, item in enumerate(extracted_financials):
                item.id = str(uuid.uuid4())
                
            package.financials_data = extracted_financials
            if extracted_om_proforma:
                package.om_proforma_data = extracted_om_proforma
                
            logger.info(f"Saved {len(extracted_financials)} financial items and {len(extracted_om_proforma)} OM tables to package")
            
        except Exception as e:
             logger.error(f"Error processing Financials: {e}")
             await progress_service.update_progress(package_id, 0, f"Normalization failed: {str(e)}")
             raise HTTPException(status_code=500, detail=f"Error processing documents: {str(e)}")

    # Consolidate normalized_data for backward compatibility / Verification UI
    # The UI likely consumes package.normalized_data
    # We should populate it with everything that needs verification (Financials)
    # Rent Roll items usually have their own widget, but if we want them in the "Data Verification" table?
    # Usually Rent Roll is separate. The "normalized_data" field in schema is List[NormalizedDataItem].
    # RentRollItem is NOT NormalizedDataItem.
    # So normalized_data should contain the financials_data.
    package.normalized_data = package.financials_data
    
    package.normalization_status = "in_progress"
    
    # Update cache and persist to GCP
    deal_packages_cache[package_id] = package
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
        max_unit_count=80,
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
        # Call the analyze endpoint internally
        analysis_result = await analyze_deal_package(
            package_id=package_id,
            deal_parameters=default_params.model_dump(),
            gemini_service=gemini_service,
            progress_service=progress_service,
            explainability_service=explainability_service
        )
        
        logger.info(f"Financial report generated successfully for package {package_id}")
        
        # Return the analysis result instead of normalization result
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error generating financial report: {str(e)}", exc_info=True)
        # If analysis fails, still return normalization result
        await progress_service.update_progress(package_id, 100, "Normalization complete. Analysis generation failed.")
        
        result = DocumentNormalizationResult(
            document_id="multiple",
            document_type=document_type or DocumentType.FINANCIALS,
            normalized_items=normalized_items,
            total_items=len(normalized_items),
            verified_items=0,
            confidence_average=sum(item.confidence for item in normalized_items) / len(normalized_items) if normalized_items else 0
        )
        return result


@router.put("/packages/{package_id}/verify-item/{item_id}")
async def verify_normalized_item(
    package_id: str,
    item_id: str,
    user_correction: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
):
    """
    Mark a normalized item as verified by the user.
    If user_correction is provided, it means the user changed the mapping.
    """
    # Check cache first
    if package_id in deal_packages_cache:
        package = deal_packages_cache[package_id]
    else:
        # Try to load from GCP storage
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
        package = DealPackage(**package_data)
        deal_packages_cache[package_id] = package
    
    # Find and update the item in normalized_data
    item_found = False
    for item in package.normalized_data:
        if item.id == item_id:
            item.user_verified = True
            if user_correction is not None:
                item.user_correction = user_correction
            item_found = True
            break
            
    if not item_found:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in package")
        
    # Recalculate progress
    total_items = len(package.normalized_data)
    verified_items = sum(1 for item in package.normalized_data if item.user_verified)
    package.verification_progress = (verified_items / total_items) * 100 if total_items > 0 else 0
    
    # Save changes
    deal_packages_cache[package_id] = package
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
    
    Args:
        package_id: The deal package ID
        items: List of items to verify, each with:
            - item_id: str (required)
            - user_correction: str (optional)
    
    Returns:
        Summary of verification results
    
    Example payload:
    [
        {"item_id": "abc-123"},
        {"item_id": "def-456", "user_correction": "Real Estate Taxes"}
    ]
    """
    # Check cache first
    if package_id in deal_packages_cache:
        package = deal_packages_cache[package_id]
    else:
        # Try to load from GCP storage
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
        package = DealPackage(**package_data)
        deal_packages_cache[package_id] = package
    
    # Track results
    verified_count = 0
    not_found_ids = []
    
    # Create a map of item_id to verification data for quick lookup
    verification_map = {item.get("item_id"): item.get("user_correction") for item in items if item.get("item_id")}
    
    # Update all items in a single pass
    for item in package.normalized_data:
        if item.id in verification_map:
            item.user_verified = True
            user_correction = verification_map[item.id]
            if user_correction is not None:
                item.user_correction = user_correction
            verified_count += 1
    
    # Check for items that weren't found
    found_ids = {item.id for item in package.normalized_data if item.user_verified}
    requested_ids = set(verification_map.keys())
    not_found_ids = list(requested_ids - found_ids)
    
    # Recalculate progress
    total_items = len(package.normalized_data)
    total_verified = sum(1 for item in package.normalized_data if item.user_verified)
    package.verification_progress = (total_verified / total_items) * 100 if total_items > 0 else 0
    
    # Save changes once
    deal_packages_cache[package_id] = package
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


@router.post("/packages/{package_id}/manual-overrides")
async def update_manual_overrides(
    package_id: str,
    overrides: Dict[str, Any],
):
    """
    Update manual overrides for a deal package.
    Useful when documents are missing or extraction fails.
    
    Expected keys in overrides:
    - total_units: int
    - gross_potential_rent: float
    - etc.
    """
    # Check cache first
    if package_id in deal_packages_cache:
        package = deal_packages_cache[package_id]
    else:
        # Try to load from GCP storage
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
        package = DealPackage(**package_data)
        deal_packages_cache[package_id] = package
        
    # Update overrides
    package.manual_overrides.update(overrides)
    
    # Save changes
    deal_packages_cache[package_id] = package
    await storage_service.save_deal_package(package.model_dump())
    
    return {
        "message": "Manual overrides updated successfully",
        "overrides": package.manual_overrides
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
    # Match patterns like "2715 Dwight" or "2715 Dwight Way"
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


@router.post("/packages/{package_id}/analyze")
async def analyze_deal_package(
    package_id: str,
    deal_parameters: Dict[str, Any],
    gemini_service: GeminiService = Depends(get_gemini_service),
    progress_service: ProgressService = Depends(get_progress_service),
    explainability_service: ExplainabilityService = Depends(get_explainability_service)
):
    """
    Perform financial analysis on a multi-document deal package.
    
    This endpoint is designed for the multi-document workflow and does NOT
    require documents to be in the OCR backend. It uses the normalized data
    from the package to perform analysis.
    
    This endpoint ALWAYS performs a fresh analysis from scratch, ensuring all
    calculations use the latest deal parameters provided.
    
    Args:
        package_id: The deal package ID
        deal_parameters: Deal parameters (growth_rate, exit_cap_rate, etc.)
    
    Returns:
        UnderwritingAnalysis object with complete financial analysis
    """
    from app.models.schemas import (
        UnderwritingAnalysis, DealParameters, PropertyMeta,
        RentRollItem, RentRollSummary, StandardizedExpense,
        ExpenseCategory, AuditLog
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
    
    logger.info(f"Starting FRESH multi-document analysis for package: {package_id}")
    logger.info(f"Received deal parameters: {deal_parameters}")
    
    await progress_service.update_progress(package_id, 5, "Initializing analysis...")
    
    # Get the deal package
    if package_id in deal_packages_cache:
        package = deal_packages_cache[package_id]
    else:
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
        package = DealPackage(**package_data)
        deal_packages_cache[package_id] = package
    
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
        
        # Explicitly force loan_amount from raw dict if present (safety net)
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
    memo_service = MemoService(gemini_service=gemini_service)
    ingestion_service = IngestionService()
    synthesis_service = SynthesisService()
    
    # ===== STEP 1: LOAD PACKAGE DATA (NEW SEGMENTED FLOW) =====
    # We load from the segmented data stores in the package.
    
    await progress_service.update_progress(package_id, 20, "Aggregating package data...")
    
    # Financials (Expenses)
    normalized_items = package.financials_data if package.financials_data else package.normalized_data
    
    # Rent Roll
    rent_roll_items = package.rent_roll_data
    
    logger.info(f"Using {len(normalized_items)} normalized items and {len(rent_roll_items)} rent roll items for analysis")
    
    # ===== STEP 2: SYNTHESIZE DATA FROM ALL DOCUMENTS (OMNISCIENT PATTERN) =====
    
    await progress_service.update_progress(package_id, 30, "Synthesizing property metadata from all documents...")
    
    # Run Metadata Synthesizer (Priority-based selection)
    synthesized_metadata = synthesis_service.synthesize_property_metadata(normalized_items)
    
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
    property_meta = PropertyMeta(
        address=_clean_address(package.property_name),
        year_built=synthesized_metadata['year_built']['value'] if synthesized_metadata['year_built']['value'] > 0 else 1980,
        purchase_price=synthesized_metadata['purchase_price']['value'],
        total_units=synthesized_metadata['total_units']['value'],
        is_renovated=False,
        current_loan_balance=synthesized_metadata.get('current_loan_balance', {}).get('value', 0.0)
    )
    
    # Extract rent roll items (Use pre-processed Rent Roll data if available)
    await progress_service.update_progress(package_id, 40, "Building master rent roll from all documents...")
    
    rent_roll: List[RentRollItem] = []
    
    if rent_roll_items:
        # We already extracted rent rolls during normalization phase
        # Just need to synthesize/deduplicate them
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
        if item.field_type == "expense_category" or (hasattr(item, 'category_group') and item.category_group == "Operating Expense"):
            try:
                # Parse the category
                # Fallback to Other OpEx if unknown
                try:
                    category = ExpenseCategory(item.normalized_value)
                except ValueError:
                    category = ExpenseCategory.OTHER_OPERATING_EXPENSES
                
                # Fix for attribute error: type object 'ExpenseCategory' has no attribute 'MARKETING'
                # If the normalized_value is MARKETING or ADVERTISING (legacy), remap it to ADVERTISING_MARKETING
                if item.normalized_value in ["Marketing", "Advertising"]:
                    category = ExpenseCategory.ADVERTISING_MARKETING
                
                # Use amount from metadata if available, otherwise parse from text
                amount = 0.0
                if item.metadata:
                    val = item.metadata.get("amount")
                    if val is not None:
                        amount = sanitize_float(val)
                
                if amount == 0.0 and "$" in item.raw_text:
                    amount_str = item.raw_text.split("$")[-1].replace(",", "").strip()
                    amount = sanitize_float(amount_str)
                    if amount == 0.0:
                        amount = 1000.0  # Default fallback
                
                # Get document_id from metadata if available (it should be there now)
                doc_id = item.metadata.get("document_id") if item.metadata else None
                page_number = item.metadata.get("page_number") if item.metadata else None
                bbox = item.metadata.get("bbox") if item.metadata else None

                expense = StandardizedExpense(
                    original_text=item.raw_text,
                    mapped_category=category,
                    amount=amount,
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
                    user_corrected_category=ExpenseCategory(item.user_correction) if item.user_correction else None
                )
                historical_expenses.append(expense)
            except Exception as e:
                logger.warning(f"Could not parse expense item: {item.raw_text}, error: {str(e)}")
    
    # (Rent Roll extraction logic moved to start of function)

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
        # Generate placeholder rent roll based on property size
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
    
    # Modified to use occupied units/sf for Current Rent averages (ignore 0$ rent)
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
    # These override extraction and package-level manual overrides
    if params.units_override is not None:
        property_meta.total_units = params.units_override
        logger.info(f"Applied transient override for Total Units: {property_meta.total_units}")

    if params.purchase_price_override is not None:
        property_meta.purchase_price = params.purchase_price_override
        logger.info(f"Applied transient override for Purchase Price: {property_meta.purchase_price}")
    
    # Check for existing analysis to preserve persistent configurations (like student housing config)
    existing_analysis_dict = await storage_service.get_analysis_result(package_id)
    existing_student_config = None
    
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
    if not existing_student_config and existing_analysis_dict and "student_housing_config" in existing_analysis_dict:
        try:
            # Parse it to ensure validity
            from app.models.schemas import StudentHousingConfig
            if existing_analysis_dict["student_housing_config"]:
                existing_student_config = StudentHousingConfig(**existing_analysis_dict["student_housing_config"])
                logger.info("Restored student housing config from Previous Analysis")
        except Exception as e:
            logger.warning(f"Failed to restore student housing config from analysis: {e}")

    # Create analysis object
    analysis = UnderwritingAnalysis(
        document_id=package_id,
        pass_fail_status="PENDING",
        gating_reasons=[],
        property_meta=property_meta,
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
        student_housing_config=existing_student_config
    )
    
    logger.info(f"Built analysis object with {len(rent_roll)} units and {len(historical_expenses)} expenses")

    # Populate Audit Trail with Ingestion Data
    audit_log_service.add_ingestion_logs(analysis)
    
    # ===== STEP 3: CHECK DEAL VIABILITY =====
    await progress_service.update_progress(package_id, 50, "Checking deal viability criteria...")
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
        # Proceed to calculation anyway
    
    # ===== STEP 4: CALCULATE FINANCIALS =====
    try:
        await progress_service.update_progress(package_id, 70, "Calculating financial projections...")
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
        await progress_service.update_progress(package_id, 0, f"Calculations failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Financial calculation failed: {str(e)}")
    
    # ===== STEP 4.5: GENERATE EXPLAINABILITY & CONCLUSION =====
    try:
        await progress_service.update_progress(package_id, 80, "Generating insights and explanations...")
        analysis = await explainability_service.generate_explanations(analysis)
        
        # Generate Analyst Commentary
        logger.info("Generating analyst commentary...")
        await explainability_service.generate_analyst_commentary(analysis)
        
        logger.info("Explainability metadata, conclusion, and commentary generated successfully.")
    except Exception as e:
        logger.error(f"Explainability generation failed: {str(e)}")
        # Don't fail the pipeline for this, but log it
        analysis.gating_reasons.append(f"Explainability generation failed: {str(e)}")

    # ===== STEP 5: GENERATE OUTPUTS (Excel, Memo & Commentary) =====
    try:
        import asyncio
        await progress_service.update_progress(package_id, 90, "Generating output models and AI commentary...")
        
        # 1. Excel (Synchronous/Fast)
        pro_forma_entries = excel_service.generate_side_by_side_view(analysis)
        await excel_service.create_side_by_side_excel(pro_forma_entries)
        logger.info(f"Excel model generated for package: {package_id}")
        
        # 2. Parallel AI Tasks (Memo & Commentary)
        async def task_commentary():
            try:
                await explainability_service.generate_analyst_commentary(analysis)
                logger.info("Analyst commentary generated.")
            except Exception as e:
                logger.error(f"Commentary generation failed: {e}")
                analysis.analyst_commentary = "Commentary unavailable."

        async def task_memo():
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
    
    package.normalization_status = "completed"
    package.updated_at = datetime.utcnow().isoformat()
    
    # Save the analysis result separately so it can be retrieved later
    analysis_dict = analysis.model_dump()
    await storage_service.save_analysis_result(package_id, analysis_dict)
    
    # Update cache and persist package
    deal_packages_cache[package_id] = package
    package_dict = package.model_dump()
    await storage_service.save_deal_package(package_dict)
    
    logger.info(f"Multi-document analysis complete for package {package_id}")
    logger.info(f"Final status: {analysis.pass_fail_status}")
    
    await progress_service.update_progress(package_id, 100, "Analysis complete!")
    return analysis


@router.get("/packages/{package_id}/analysis")
async def get_deal_analysis(package_id: str):
    """
    Retrieve the stored financial analysis for a deal package.
    Returns 404 with a specific message if analysis hasn't been run yet.
    This allows the frontend to distinguish between "package not found" and "analysis not run yet".
    """
    from app.services.storage_service import storage_service
    
    # First, verify the package exists
    package_data = await storage_service.get_deal_package(package_id)
    if not package_data:
        raise HTTPException(
            status_code=404,
            detail=f"Package {package_id} not found. It may have been deleted or never existed."
        )
    
    # Check cache/storage for analysis result
    analysis_data = await storage_service.get_analysis_result(package_id)
    
    if not analysis_data:
        # Package exists but analysis hasn't been run yet
        # Return 404 with a clear message that frontend can handle
        raise HTTPException(
            status_code=404,
            detail=f"NO_ANALYSIS_YET"
        )
    
    return analysis_data


@router.patch("/packages/{package_id}/rename")
async def rename_deal_package(package_id: str, new_name: str):
    """
    Rename a deal package.
    
    Args:
        package_id: Package identifier
        new_name: New property name
    
    Returns:
        Updated package information
    """
    # Get the package
    if package_id in deal_packages_cache:
        package = deal_packages_cache[package_id]
    else:
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
        package = DealPackage(**package_data)
    
    # Update the property name
    package.property_name = new_name
    package.updated_at = datetime.utcnow().isoformat()
    
    # Save changes
    deal_packages_cache[package_id] = package
    package_dict = package.model_dump()
    await storage_service.save_deal_package(package_dict)
    
    logger.info(f"Renamed package {package_id} to '{new_name}'")
    
    return {
        "message": "Package renamed successfully",
        "package_id": package_id,
        "property_name": new_name
    }


@router.delete("/packages/{package_id}")
async def delete_deal_package(package_id: str):
    """
    Delete a deal package and all its documents.
    """
    # Delete from GCP storage
    deleted = await storage_service.delete_deal_package(package_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
    
    # Remove from cache
    if package_id in deal_packages_cache:
        del deal_packages_cache[package_id]
    
    # Remove associated files from cache
    file_ids_to_remove = [
        doc_id for doc_id, file_data in file_storage_cache.items()
        if file_data.get("package_id") == package_id
    ]
    for doc_id in file_ids_to_remove:
        del file_storage_cache[doc_id]
    
@router.get("/packages/{package_id}/documents/{document_id}/content")
async def get_package_document_content(package_id: str, document_id: str):
    """
    Get the raw content of a document within a package.
    Returns a signed URL if GCP is configured, otherwise returns base64-encoded content.
    """
    # Check cache first
    if package_id in deal_packages_cache:
        package = deal_packages_cache[package_id]
    else:
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise HTTPException(status_code=404, detail=f"Deal package {package_id} not found")
        package = DealPackage(**package_data)
        deal_packages_cache[package_id] = package

    # Find document metadata
    target_doc = None
    for doc_list in package.documents.values():
        for doc in doc_list:
            if doc.document_id == document_id:
                target_doc = doc
                break
        if target_doc:
            break
            
    if not target_doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found in package {package_id}")

    extension = Path(target_doc.filename).suffix
    storage_path = f"deal-packages/{package_id}/documents/{document_id}{extension}"
    
    # Try to generate a signed URL first (preferred method)
    try:
        if storage_service.use_gcp:
            signed_url = await storage_service.get_signed_url(storage_path)
            if signed_url:
                logger.info(f"Generated signed URL for document {document_id}")
                return {"signed_url": signed_url}
            else:
                logger.warning(f"Signed URL generation returned None for {storage_path}")
        else:
            logger.warning("GCP not configured, cannot generate signed URL")
    except Exception as e:
        logger.error(f"Error generating signed URL for {storage_path}: {e}", exc_info=True)
    
    # Fallback: Try to get document from cache
    if document_id in file_storage_cache:
        try:
            import base64
            file_data = file_storage_cache[document_id]
            content = file_data.get("content")
            if content:
                # Return base64-encoded content for frontend to decode
                encoded_content = base64.b64encode(content).decode('utf-8')
                logger.info(f"Returning cached content for document {document_id} (base64)")
                return {
                    "content": encoded_content,
                    "filename": target_doc.filename,
                    "content_type": storage_service._get_content_type(target_doc.filename),
                    "encoding": "base64"
                }
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}", exc_info=True)
    
    # Fallback: Try to download from GCP storage directly
    if storage_service.use_gcp:
        try:
            import base64
            file_content = await storage_service.get_document_file(storage_path)
            if file_content:
                # Return base64-encoded content
                encoded_content = base64.b64encode(file_content).decode('utf-8')
                logger.info(f"Downloaded and returning content for document {document_id} (base64)")
                return {
                    "content": encoded_content,
                    "filename": target_doc.filename,
                    "content_type": storage_service._get_content_type(target_doc.filename),
                    "encoding": "base64"
                }
            else:
                logger.error(f"Document file not found in storage: {storage_path}")
        except Exception as e:
            logger.error(f"Error downloading from GCP: {e}", exc_info=True)
    
    # All methods failed
    raise HTTPException(
        status_code=404,
        detail=f"Document file not accessible. Path: {storage_path}. Check GCP configuration and file existence."
    )
