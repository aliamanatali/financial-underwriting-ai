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

from app.models.schemas import (
    DocumentType,
    DocumentMetadata,
    DealPackage,
    DocumentNormalizationResult,
    NormalizedDataItem
)
from app.services.ingestion_service import IngestionService
from app.services.normalization_service import NormalizationService
from app.services.gemini_service import GeminiService
from app.services.multi_document_extraction_service import MultiDocumentExtractionService
from app.services.storage_service import storage_service
from app.services.explainability_service import ExplainabilityService
from app.services.progress_service import ProgressService
from app.dependencies import get_gemini_service, get_progress_service, get_explainability_service

router = APIRouter(prefix="/api/v1/multi-document", tags=["Multi-Document Ingestion"])
logger = logging.getLogger(__name__)

# In-memory cache for quick access (backed by GCP storage)
deal_packages_cache = {}
# In-memory file storage (backed by GCP storage)
file_storage_cache = {}

# Folder name to DocumentType mapping
FOLDER_MAPPING = {
    "01 - Offering Memorandum": DocumentType.OFFERING_MEMORANDUM,
    "01-Offering Memorandum": DocumentType.OFFERING_MEMORANDUM,
    "Offering Memorandum": DocumentType.OFFERING_MEMORANDUM,
    
    "02 - Rent Roll": DocumentType.RENT_ROLL,
    "02-Rent Roll": DocumentType.RENT_ROLL,
    "Rent Roll": DocumentType.RENT_ROLL,
    
    "03 - Leases": DocumentType.LEASES,
    "03-Leases": DocumentType.LEASES,
    "Leases": DocumentType.LEASES,
    
    "04 - Financials": DocumentType.FINANCIALS,
    "04-Financials": DocumentType.FINANCIALS,
    "Financials": DocumentType.FINANCIALS,
    
    "05 - Building Plans & Permits": DocumentType.BUILDING_PLANS_PERMITS,
    "05-Building Plans & Permits": DocumentType.BUILDING_PLANS_PERMITS,
    "Building Plans & Permits": DocumentType.BUILDING_PLANS_PERMITS,
    
    "06 - Disclosures": DocumentType.DISCLOSURES,
    "06-Disclosures": DocumentType.DISCLOSURES,
    "Disclosures": DocumentType.DISCLOSURES,
    
    "07 - Tax Bills": DocumentType.TAX_BILLS,
    "07-Tax Bills": DocumentType.TAX_BILLS,
    "Tax Bills": DocumentType.TAX_BILLS,
    
    "08 - Utilities": DocumentType.UTILITIES,
    "08-Utilities": DocumentType.UTILITIES,
    "Utilities": DocumentType.UTILITIES,
}


def get_document_type_from_folder(folder_path: str) -> Optional[DocumentType]:
    """
    Determine document type based on folder name.
    Supports various naming conventions (with/without numbers, with/without dashes).
    """
    folder_name = os.path.basename(folder_path)
    
    # Direct match
    if folder_name in FOLDER_MAPPING:
        return FOLDER_MAPPING[folder_name]
    
    # Fuzzy match - check if any key is in the folder name
    for key, doc_type in FOLDER_MAPPING.items():
        if key.lower() in folder_name.lower():
            return doc_type
    
    return None


@router.post("/packages/upload-zip", response_model=DealPackage)
async def upload_zip_package(
    file: UploadFile = File(...),
    property_name: Optional[str] = Form(None),
):
    """
    Upload a ZIP file containing the 8-folder structure.
    
    Expected structure:
    Property_Name_Inputs.zip
    ├── 01 - Offering Memorandum/
    │   └── OM.pdf
    ├── 02 - Rent Roll/
    │   └── Current_Rent_Roll.xlsx
    ├── 03 - Leases/
    │   ├── Lease_Unit_101.pdf
    │   └── Lease_Unit_102.pdf
    ├── 04 - Financials/
    │   ├── T12_Income_Statement.xlsx
    │   └── T12_P&L.pdf
    ├── 05 - Building Plans & Permits/
    │   └── Floor_Plans.pdf
    ├── 06 - Disclosures/
    │   └── Property_Condition_Report.pdf
    ├── 07 - Tax Bills/
    │   └── 2024_Property_Tax_Bill.pdf
    └── 08 - Utilities/
        ├── PGE_Bill_Nov.pdf
        └── Water_Bill.pdf
    """
    
    # Validate file type
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    
    # Extract property name from filename if not provided
    if not property_name:
        property_name = file.filename.replace('.zip', '').replace('_Inputs', '')
    
    # Create deal package
    package_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    package = DealPackage(
        package_id=package_id,
        property_name=property_name,
        created_at=now,
        updated_at=now,
        documents={doc_type: [] for doc_type in DocumentType},
        normalization_status="pending",
        verification_progress=0.0
    )
    
    # Read ZIP file
    content = await file.read()
    
    files_processed = 0
    files_skipped = 0
    empty_folders = []
    
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zip_ref:
            # Get list of all files in the ZIP
            file_list = zip_ref.namelist()
            logger.info(f"ZIP contains {len(file_list)} entries")
            logger.info(f"File list: {file_list[:10]}")  # Log first 10 entries for debugging
            
            # Process each file
            for file_path in file_list:
                # Skip directories and hidden files
                if file_path.endswith('/') or os.path.basename(file_path).startswith('.'):
                    logger.debug(f"Skipping directory or hidden file: {file_path}")
                    continue
                
                # Get the folder name (first level directory)
                path_parts = Path(file_path).parts
                logger.info(f"Processing file: {file_path}, parts: {path_parts}")
                
                if len(path_parts) < 2:
                    logger.warning(f"Skipping file at root level: {file_path}")
                    files_skipped += 1
                    continue
                
                # Handle nested folder structure (e.g., "Keystone Apartments 2/Financials/file.pdf")
                # Find the actual document type folder
                folder_name = None
                for part in path_parts[:-1]:  # Exclude the filename
                    doc_type = get_document_type_from_folder(part)
                    if doc_type:
                        folder_name = part
                        break
                
                if not folder_name:
                    # Try the immediate parent folder
                    folder_name = path_parts[-2] if len(path_parts) >= 2 else path_parts[0]
                
                filename = os.path.basename(file_path)
                logger.info(f"Determined folder: {folder_name}, filename: {filename}")
                
                # Determine document type from folder
                doc_type = get_document_type_from_folder(folder_name)
                if not doc_type:
                    logger.warning(f"Could not determine document type for folder: {folder_name}")
                    files_skipped += 1
                    continue
                
                # Read file content
                file_content = zip_ref.read(file_path)
                file_size = len(file_content)
                
                # Skip empty files
                if file_size == 0:
                    logger.warning(f"Skipping empty file: {file_path}")
                    files_skipped += 1
                    continue
                
                # Create document metadata
                document_id = str(uuid.uuid4())
                doc_metadata = DocumentMetadata(
                    document_id=document_id,
                    filename=filename,
                    document_type=doc_type,
                    upload_timestamp=now,
                    file_size=file_size,
                    extraction_status="pending"
                )
                
                # Add to package
                package.documents[doc_type].append(doc_metadata)
                
                # Store file content in cache
                file_storage_cache[document_id] = {
                    "content": file_content,
                    "filename": filename,
                    "document_type": doc_type,
                    "package_id": package_id
                }
                
                # Persist file to GCP storage
                await storage_service.save_document_file(
                    package_id=package_id,
                    document_id=document_id,
                    filename=filename,
                    file_content=file_content
                )
                
                files_processed += 1
                logger.info(f"Processed: {filename} -> {doc_type.value}")
            
            # Check for empty or missing document categories
            for doc_type in DocumentType:
                if doc_type not in package.documents or len(package.documents[doc_type]) == 0:
                    empty_folders.append(doc_type.value)
            
            # Log summary
            logger.info(f"Processing complete: {files_processed} files processed, {files_skipped} skipped")
            if empty_folders:
                logger.warning(f"Empty or missing categories: {', '.join(empty_folders)}")
    
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except Exception as e:
        logger.error(f"Error processing ZIP file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing ZIP file: {str(e)}")
    
    # Store package in cache
    deal_packages_cache[package_id] = package
    
    # Persist to GCP storage
    package_dict = package.model_dump()
    await storage_service.save_deal_package(package_dict)
    
    logger.info(f"Created deal package {package_id} with {sum(len(docs) for docs in package.documents.values())} documents")
    
    return package


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
    explainability_service: ExplainabilityService = Depends(get_explainability_service)
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
    extraction_service = MultiDocumentExtractionService(gemini_service=gemini_service)
    
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
    
    for doc_type in target_types:
        if doc_type not in package.documents:
            continue
        
        for doc_metadata in package.documents[doc_type]:
            doc_id = doc_metadata.document_id
            
            # Retrieve file content from cache or GCP storage
            if doc_id in file_storage_cache:
                file_data = file_storage_cache[doc_id]
            else:
                # Try to load from GCP storage using the correct path
                # The storage service's _get_document_path already includes the extension
                filename = doc_metadata.filename
                extension = Path(filename).suffix
                storage_path = f"deal-packages/{package_id}/documents/{doc_id}{extension}"
                
                try:
                    file_content = await storage_service.get_document_file(storage_path)
                    if file_content:
                        file_data = {
                            "content": file_content,
                            "filename": filename,
                            "document_type": doc_metadata.document_type,
                            "package_id": package_id
                        }
                        # Update cache
                        file_storage_cache[doc_id] = file_data
                    else:
                        logger.warning(f"File content not found for document {doc_id} at {storage_path}")
                        continue
                except Exception as e:
                    logger.error(f"Error retrieving document {doc_id}: {str(e)}")
                    continue
            
            # Determine file type
            filename = file_data["filename"]
            if filename.endswith((".xlsx", ".xls")):
                file_type = "excel"
            elif filename.endswith(".pdf"):
                file_type = "pdf"
            else:
                logger.warning(f"Unsupported file type: {filename}")
                continue
            
            documents_to_process.append({
                "content": file_data["content"],
                "filename": filename,
                "type": file_type
            })
    
    if not documents_to_process:
        logger.warning(f"No processable documents found for package {package_id}")
        # Return empty result instead of error for best possible outcome
        return DocumentNormalizationResult(
            document_id="multiple",
            document_type=document_type or DocumentType.FINANCIALS,
            normalized_items=[],
            total_items=0,
            verified_items=0,
            confidence_average=0.0
        )
    
    logger.info(f"Processing {len(documents_to_process)} documents for package {package_id}")
    for idx, doc in enumerate(documents_to_process):
        logger.info(f"  Document {idx+1}: {doc['filename']} ({doc['type']}, {len(doc['content'])} bytes)")
    
    await progress_service.update_progress(package_id, 20, f"Extracting data from {len(documents_to_process)} documents (this may take a minute)...")
    
    # Process documents and extract normalized data
    try:
        normalized_items = await extraction_service.process_financial_documents(
            documents_to_process,
            progress_service=progress_service,
            task_id=package_id
        )
        logger.info(f"Extraction service returned {len(normalized_items) if normalized_items else 0} normalized items")
    except Exception as e:
        logger.error(f"Error processing documents: {str(e)}", exc_info=True)
        await progress_service.update_progress(package_id, 0, f"Normalization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing documents: {str(e)}")
    
    if not normalized_items:
        logger.warning("No expense items extracted from documents. Continuing with empty result.")
        normalized_items = []
    
    # Assign unique IDs
    for idx, item in enumerate(normalized_items):
        item.id = str(uuid.uuid4())
    
    # Save normalized data to package
    package.normalization_status = "in_progress"
    package.normalized_data = normalized_items  # Save extracted items to package
    
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
    
    # ===== STEP 1: BUILD ANALYSIS OBJECT FROM PACKAGE DATA =====
    # We use the normalized data that was stored in the package (and verified by user)
    # If not present (legacy packages), we might need to re-extract, but we'll assume
    # the new flow enforces normalization first.
    
    await progress_service.update_progress(package_id, 20, "Aggregating package data...")
    
    normalized_items = package.normalized_data
    
    # If no items found but we have documents, try to extract (fallback/legacy support)
    if not normalized_items and any(package.documents.values()):
        logger.info("No normalized data found in package. Attempting on-the-fly extraction (legacy mode)...")
        try:
             # Re-extract normalized data from documents
            extraction_service = MultiDocumentExtractionService(gemini_service=gemini_service)
            
            # Collect documents to process
            documents_to_process = []
            for doc_type, doc_list in package.documents.items():
                for doc_metadata in doc_list:
                    doc_id = doc_metadata.document_id
                    
                    # Retrieve file content
                    if doc_id in file_storage_cache:
                        file_data = file_storage_cache[doc_id]
                    else:
                        filename = doc_metadata.filename
                        extension = Path(filename).suffix
                        storage_path = f"deal-packages/{package_id}/documents/{doc_id}{extension}"
                        
                        try:
                            file_content = await storage_service.get_document_file(storage_path)
                            if file_content:
                                file_data = {
                                    "content": file_content,
                                    "filename": filename,
                                    "document_type": doc_metadata.document_type,
                                    "package_id": package_id
                                }
                                file_storage_cache[doc_id] = file_data
                            else:
                                continue
                        except Exception as e:
                            logger.error(f"Error retrieving document {doc_id}: {str(e)}")
                            continue
                    
                    # Determine file type
                    filename = file_data["filename"]
                    if filename.endswith((".xlsx", ".xls")):
                        file_type = "excel"
                    elif filename.endswith(".pdf"):
                        file_type = "pdf"
                    else:
                        continue
                    
                    documents_to_process.append({
                        "content": file_data["content"],
                        "filename": filename,
                        "type": file_type
                    })
            
            normalized_items = await extraction_service.process_financial_documents(
                documents_to_process,
                progress_service=progress_service,
                task_id=package_id,
                progress_start=25,
                progress_end=45
            )
            # Don't save back to package in this fallback mode to avoid overwriting future proper usage
        except Exception as e:
            logger.warning(f"Fallback extraction failed: {str(e)}")
            normalized_items = []

    logger.info(f"Using {len(normalized_items)} normalized items for analysis")
    
    # ===== STEP 2: CONVERT NORMALIZED DATA TO ANALYSIS STRUCTURE =====
    # Build property metadata, rent roll, and expenses from normalized items
    
    # Handle missing loan_amount gracefully by using LTV calculation or default
    # Note: current_loan_balance represents EXISTING debt, not the NEW loan being analyzed
    # The NEW loan amount will be calculated in financial_service based on deal_parameters
    current_loan_balance = 0.0
    # Only set if there's an existing loan on the property (from extraction)
    # The new loan_amount from params will be used in financial calculations, not here
    
    property_meta = PropertyMeta(
        address=package.property_name,
        year_built=1980,  # Default - should be extracted from OM
        purchase_price=0.0,  # Default to 0, will be updated from extraction
        total_units=0,  # Default - should be calculated from rent roll
        is_renovated=False,
        current_loan_balance=current_loan_balance  # Existing debt, not new loan
    )
    
    # Apply Manual Overrides for Property Meta
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
    
    rent_roll: List[RentRollItem] = []
    historical_expenses: List[StandardizedExpense] = []
    
    # Parse normalized items
    for item in normalized_items:
        # GLOBAL CHECK: Unit Count from Metadata (e.g. from Excel Rent Roll)
        # We check this on ALL items regardless of category, as Rent Rolls might be miscategorized
        if item.metadata and item.metadata.get("row_count") and "rent roll" in item.raw_text.lower():
            row_count = item.metadata.get("row_count")
            if row_count and row_count > 0:
                # Only update if we don't have a value or if this one seems more reliable (e.g. from actual file rows)
                if property_meta.total_units == 0:
                    property_meta.total_units = int(row_count)
                    logger.info(f"Updated Total Units from Rent Roll row count: {row_count}")
        
        # Check if this is a Property Meta item or Property Info group
        if item.field_type == "property_meta" or (hasattr(item, 'category_group') and item.category_group == "Property Info"):
            try:
                # Update Property Meta based on content
                lower_text = item.raw_text.lower()
                # Safely get amount from metadata
                amount = 0.0
                if item.metadata:
                    metadata_amount = item.metadata.get("amount", 0.0)
                    # Handle None or 0.0 explicitly
                    if metadata_amount:
                        amount = sanitize_float(metadata_amount)
                
                # Check normalized value first, then raw text
                mapped_val = item.normalized_value.lower()
                
                if "purchase price" in mapped_val or "purchase price" in lower_text or "asking price" in lower_text:
                    if amount and amount > 0:
                        property_meta.purchase_price = amount
                        # Also update loan amount if using LTV
                        if hasattr(params, 'ltv') and params.ltv > 0:
                             property_meta.current_loan_balance = sanitize_float(amount * params.ltv)
                        logger.info(f"Updated Purchase Price from extraction: ${amount:,.2f}")
                
                elif "year built" in mapped_val or "year built" in lower_text:
                    # Try to extract year (might need regex if amount is not clean)
                    if amount and amount > 1800 and amount < 2030:
                        property_meta.year_built = int(amount)
                
                elif "total units" in mapped_val or "total units" in lower_text or "number of units" in lower_text:
                    if amount and amount > 0:
                        property_meta.total_units = int(amount)
                
                elif "loan" in mapped_val or "existing loan" in lower_text:
                     if amount and amount > 0:
                        property_meta.current_loan_balance = amount
                        logger.info(f"Updated Existing Loan from extraction: ${amount:,.2f}")

            except Exception as e:
                logger.warning(f"Could not parse property meta item: {item.raw_text}, error: {str(e)}")

        # Check if this is a Revenue item
        elif item.field_type == "revenue_item" or (hasattr(item, 'category_group') and item.category_group == "Revenue"):
             # We can potentially use this to refine GPR if Rent Roll is missing
             # For now, we'll log it but rely on Rent Roll logic for main GPR
             pass
             
        # Check if this is an expense item
        elif item.field_type == "expense_category" or (hasattr(item, 'category_group') and item.category_group == "Operating Expense"):
            try:
                # Parse the category
                # Fallback to Other OpEx if unknown
                try:
                    category = ExpenseCategory(item.normalized_value)
                except ValueError:
                    category = ExpenseCategory.OTHER_OPERATING_EXPENSES
                
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
                        method=f"Extracted from {item.source_document}"
                    ),
                    user_verified=item.user_verified,
                    user_corrected_category=ExpenseCategory(item.user_correction) if item.user_correction else None
                )
                historical_expenses.append(expense)
            except Exception as e:
                logger.warning(f"Could not parse expense item: {item.raw_text}, error: {str(e)}")
    
    # Create a basic rent roll if none exists
    if not rent_roll:
        # Generate placeholder rent roll based on property size
        num_units = property_meta.total_units or 0
        for i in range(num_units):
            rent_roll.append(RentRollItem(
                unit_number=f"Unit {i+1}",
                unit_type="1BR",
                tenant_name="Occupied",
                current_rent=2000.0,
                market_rent=2100.0,
                lease_start="2024-01-01",
                lease_end="2024-12-31"
            ))
    
    # Calculate rent roll summary
    total_units = len(rent_roll)
    occupied_units = sum(1 for unit in rent_roll if unit.current_rent > 0)
    occupancy_rate = occupied_units / total_units if total_units > 0 else 0
    total_monthly_rent = sum(unit.current_rent for unit in rent_roll)
    total_annual_rent = total_monthly_rent * 12
    
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
        total_monthly_rent=total_monthly_rent,
        total_annual_rent=total_annual_rent
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
        historical_cap_rate=0.0
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
        logger.info("Explainability metadata and conclusion generated successfully.")
    except Exception as e:
        logger.error(f"Explainability generation failed: {str(e)}")
        # Don't fail the pipeline for this, but log it
        analysis.gating_reasons.append(f"Explainability generation failed: {str(e)}")

    # ===== STEP 5: GENERATE OUTPUTS (Excel & Memo) =====
    try:
        await progress_service.update_progress(package_id, 90, "Generating output models...")
        
        # Excel
        pro_forma_entries = excel_service.generate_side_by_side_view(analysis)
        await excel_service.create_side_by_side_excel(pro_forma_entries)
        logger.info(f"Excel model generated for package: {package_id}")
        
        # Memo
        logger.info("Generating investment memo...")
        memo_content = memo_service.generate_investment_memo(analysis)
        analysis.investment_memo = memo_content
        logger.info("Investment memo generated successfully.")
        
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
    
    return {"message": f"Deal package {package_id} deleted successfully"}
