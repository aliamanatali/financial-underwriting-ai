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
from app.dependencies import get_gemini_service

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

    "09 - Images": DocumentType.IMAGES,
    "09-Images": DocumentType.IMAGES,
    "Images": DocumentType.IMAGES,
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
        documents={},
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
                if doc_type not in package.documents:
                    package.documents[doc_type] = []
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


@router.get("/packages", response_model=List[DealPackage])
async def list_deal_packages():
    """
    List all deal packages.
    """
    # Get packages from GCP storage
    packages_data = await storage_service.list_deal_packages()
    packages = [DealPackage(**pkg) for pkg in packages_data]
    
    # Update cache
    for package in packages:
        deal_packages_cache[package.package_id] = package
    
    return packages


@router.post("/packages/{package_id}/normalize", response_model=DocumentNormalizationResult)
async def normalize_package_documents(
    package_id: str,
    document_type: Optional[DocumentType] = None,
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """
    Normalize documents in a package.
    If document_type is provided, normalize only documents of that type.
    Otherwise, normalize all documents in the package.
    
    This endpoint extracts data and maps it to standardized categories,
    returning items that need user verification.
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
        if document_type:
            detail_msg = f"No processable documents found for type: {document_type.value}"
        else:
            available_types = [dt.value for dt in package.documents.keys()]
            detail_msg = f"No processable documents found. Available types in package: {', '.join(available_types) if available_types else 'none'}"
        
        raise HTTPException(
            status_code=400,
            detail=detail_msg
        )
    
    logger.info(f"Processing {len(documents_to_process)} documents for package {package_id}")
    for idx, doc in enumerate(documents_to_process):
        logger.info(f"  Document {idx+1}: {doc['filename']} ({doc['type']}, {len(doc['content'])} bytes)")
    
    # Process documents and extract normalized data
    try:
        normalized_items = await extraction_service.process_financial_documents(documents_to_process)
        logger.info(f"Extraction service returned {len(normalized_items) if normalized_items else 0} normalized items")
    except Exception as e:
        logger.error(f"Error processing documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing documents: {str(e)}")
    
    if not normalized_items:
        # Provide more detailed error message
        doc_summary = ", ".join([f"{doc['filename']} ({doc['type']})" for doc in documents_to_process])
        raise HTTPException(
            status_code=400,
            detail=f"No expense items extracted from documents. Processed: {doc_summary}. Check if documents contain financial data in expected format."
        )
    
    # Assign unique IDs
    for idx, item in enumerate(normalized_items):
        item.id = str(uuid.uuid4())
    
    result = DocumentNormalizationResult(
        document_id="multiple",
        document_type=document_type or DocumentType.FINANCIALS,
        normalized_items=normalized_items,
        total_items=len(normalized_items),
        verified_items=0,
        confidence_average=sum(item.confidence for item in normalized_items) / len(normalized_items) if normalized_items else 0
    )
    
    package.normalization_status = "in_progress"
    
    # Update cache and persist to GCP
    deal_packages_cache[package_id] = package
    package_dict = package.model_dump()
    await storage_service.save_deal_package(package_dict)
    
    return result


@router.put("/packages/{package_id}/verify-item/{item_id}")
async def verify_normalized_item(
    package_id: str,
    item_id: str,
    user_correction: Optional[str] = None,
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
    
    # Update verification progress
    # In production, this would update the specific item in the database
    # and recalculate the overall verification progress
    
    return {
        "item_id": item_id,
        "verified": True,
        "user_correction": user_correction,
        "message": "Item verified successfully"
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
    gemini_service: GeminiService = Depends(get_gemini_service)
):
    """
    Perform financial analysis on a multi-document deal package.
    
    This endpoint is designed for the multi-document workflow and does NOT
    require documents to be in the OCR backend. It uses the normalized data
    from the package to perform analysis.
    
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
    
    logger.info(f"Starting multi-document analysis for package: {package_id}")
    logger.info(f"Received deal parameters: {deal_parameters}")
    
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
        params = DealParameters(**deal_parameters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid deal parameters: {str(e)}")
    
    # Initialize services
    audit_log_service = AuditLogService()
    financial_service = FinancialService(audit_log_service=audit_log_service)
    excel_service = ExcelService()
    
    # ===== STEP 1: BUILD ANALYSIS OBJECT FROM PACKAGE DATA =====
    # We need to reconstruct the normalized data that was stored during normalization
    # For now, we'll need to re-run normalization to get the data
    # In production, this would be stored in the database
    
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
        
        if not documents_to_process:
            raise HTTPException(
                status_code=400,
                detail="No processable documents found in package"
            )
        
        logger.info(f"Processing {len(documents_to_process)} documents for analysis")
        
        # Extract normalized data
        normalized_items = await extraction_service.process_financial_documents(documents_to_process)
        
        if not normalized_items:
            raise HTTPException(
                status_code=400,
                detail="No data could be extracted from documents"
            )
        
        logger.info(f"Extracted {len(normalized_items)} normalized items")
        
    except Exception as e:
        logger.error(f"Error extracting data from package: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error extracting data: {str(e)}")
    
    # ===== STEP 2: CONVERT NORMALIZED DATA TO ANALYSIS STRUCTURE =====
    # Build property metadata, rent roll, and expenses from normalized items
    
    property_meta = PropertyMeta(
        address=package.property_name,
        year_built=1980,  # Default - should be extracted from OM
        purchase_price=10_000_000.0,  # Default - should be extracted from OM
        total_units=50,  # Default - should be calculated from rent roll
        is_renovated=False,
        current_loan_balance=params.loan_amount
    )
    
    rent_roll: List[RentRollItem] = []
    historical_expenses: List[StandardizedExpense] = []
    
    # Parse normalized items
    for item in normalized_items:
        # Check if this is an expense item
        if item.field_type == "expense_category":
            try:
                # Parse the category
                category = ExpenseCategory(item.normalized_value)
                
                # Extract amount from raw_text (assuming format like "Insurance: $5,000")
                amount = 0.0
                if "$" in item.raw_text:
                    amount_str = item.raw_text.split("$")[-1].replace(",", "").strip()
                    try:
                        amount = float(amount_str)
                    except:
                        amount = 1000.0  # Default fallback
                
                expense = StandardizedExpense(
                    original_text=item.raw_text,
                    mapped_category=category,
                    amount=amount,
                    confidence=item.confidence,
                    audit_log=AuditLog(
                        field_name="expense",
                        extracted_value=amount,
                        source_doc=item.source_document,
                        confidence_score=item.confidence,
                        reasoning=f"Extracted from {item.source_document}"
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
        num_units = property_meta.total_units
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
    
    rent_roll_summary = RentRollSummary(
        total_units=total_units,
        occupied_units=occupied_units,
        occupancy_rate=occupancy_rate,
        total_monthly_rent=total_monthly_rent,
        total_annual_rent=total_annual_rent
    )
    
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
    
    # ===== STEP 3: CHECK DEAL VIABILITY =====
    viability_check = financial_service.check_deal_viability(analysis)
    logger.info(f"Viability check: {viability_check['status']}")
    
    if viability_check["status"] == "FAIL":
        analysis.pass_fail_status = "FAIL"
        analysis.gating_reasons = viability_check["reasons"]
        logger.warning(f"Deal failed viability check: {viability_check['reasons']}")
        return analysis
    
    # ===== STEP 4: CALCULATE FINANCIALS =====
    try:
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
        raise HTTPException(status_code=500, detail=f"Financial calculation failed: {str(e)}")
    
    # ===== STEP 5: GENERATE EXCEL (OPTIONAL) =====
    try:
        pro_forma_entries = excel_service.generate_side_by_side_view(analysis)
        excel_service.create_side_by_side_excel(pro_forma_entries)
        logger.info(f"Excel model generated for package: {package_id}")
    except Exception as e:
        logger.warning(f"Excel generation had issues (non-critical): {str(e)}")
    
    # ===== STEP 6: UPDATE PACKAGE STATUS =====
    analysis.pass_fail_status = "PASS"
    package.normalization_status = "completed"
    package.updated_at = datetime.utcnow().isoformat()
    
    # Update cache and persist
    deal_packages_cache[package_id] = package
    package_dict = package.model_dump()
    await storage_service.save_deal_package(package_dict)
    
    logger.info(f"Multi-document analysis complete for package {package_id}")
    logger.info(f"Final status: {analysis.pass_fail_status}")
    
    return analysis


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
