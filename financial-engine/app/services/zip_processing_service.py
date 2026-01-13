import logging
import zipfile
import io
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from app.models.schemas import DealPackage, DocumentMetadata, DocumentType
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

# Folder name to DocumentType mapping
FOLDER_MAPPING = {
    "01 - Offering Memorandum": DocumentType.OFFERING_MEMORANDUM,
    "01-Offering Memorandum": DocumentType.OFFERING_MEMORANDUM,
    "1. Offering Memorandum": DocumentType.OFFERING_MEMORANDUM,
    "Offering Memorandum": DocumentType.OFFERING_MEMORANDUM,
    
    "02 - Rent Roll": DocumentType.RENT_ROLL,
    "02-Rent Roll": DocumentType.RENT_ROLL,
    "2. Rent Roll": DocumentType.RENT_ROLL,
    "Rent Roll": DocumentType.RENT_ROLL,
    
    "03 - Leases": DocumentType.LEASES,
    "03-Leases": DocumentType.LEASES,
    "3. Leases": DocumentType.LEASES,
    "Leases": DocumentType.LEASES,
    
    "04 - Financials": DocumentType.FINANCIALS,
    "04-Financials": DocumentType.FINANCIALS,
    "4. Financials": DocumentType.FINANCIALS,
    "Financials": DocumentType.FINANCIALS,
    
    "05 - Building Plans & Permits": DocumentType.BUILDING_PLANS_PERMITS,
    "05-Building Plans & Permits": DocumentType.BUILDING_PLANS_PERMITS,
    "5. Building Plans & Permits": DocumentType.BUILDING_PLANS_PERMITS,
    "5. Building plans and permits": DocumentType.BUILDING_PLANS_PERMITS,
    "Building Plans & Permits": DocumentType.BUILDING_PLANS_PERMITS,
    "Building Plans and Permits": DocumentType.BUILDING_PLANS_PERMITS,
    "Building Plans": DocumentType.BUILDING_PLANS_PERMITS,
    
    "06 - Disclosures": DocumentType.DISCLOSURES,
    "06-Disclosures": DocumentType.DISCLOSURES,
    "6. Disclosures": DocumentType.DISCLOSURES,
    "Disclosures": DocumentType.DISCLOSURES,
    
    "07 - Tax Bills": DocumentType.TAX_BILLS,
    "07-Tax Bills": DocumentType.TAX_BILLS,
    "7. Tax Bills": DocumentType.TAX_BILLS,
    "Tax Bills": DocumentType.TAX_BILLS,
    
    "08 - Utilities": DocumentType.UTILITIES,
    "08-Utilities": DocumentType.UTILITIES,
    "8. Utilities": DocumentType.UTILITIES,
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


class ZipProcessingService:
    """Service for processing ZIP uploads containing financial documents."""

    async def process_zip_content(self, zip_content: bytes, property_name: str) -> Tuple[DealPackage, Dict[str, Any]]:
        """
        Process the content of a ZIP file, extract documents, creating a DealPackage,
        and saving files to storage.

        Returns:
            Tuple containing the created DealPackage and a dictionary of file cache data.
        """
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
        
        files_processed = 0
        files_skipped = 0
        empty_folders = []
        file_cache_data = {}
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_ref:
                # Get list of all files in the ZIP
                file_list = zip_ref.namelist()
                logger.info(f"ZIP contains {len(file_list)} entries")
                
                # Process each file
                for file_path in file_list:
                    # Skip directories and hidden files
                    if file_path.endswith('/') or os.path.basename(file_path).startswith('.'):
                        continue
                    
                    # Get the folder name (first level directory)
                    path_parts = Path(file_path).parts
                    
                    if len(path_parts) < 2:
                        logger.warning(f"Skipping file at root level: {file_path}")
                        files_skipped += 1
                        continue
                    
                    # Handle nested folder structure
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
                    
                    # Store file content for cache return
                    file_cache_data[document_id] = {
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
                
                # Check for empty or missing document categories
                for doc_type in DocumentType:
                    if doc_type not in package.documents or len(package.documents[doc_type]) == 0:
                        empty_folders.append(doc_type.value)
                
                # Log summary
                logger.info(f"Processing complete: {files_processed} files processed, {files_skipped} skipped")
                if empty_folders:
                    logger.warning(f"Empty or missing categories: {', '.join(empty_folders)}")
        
        except zipfile.BadZipFile:
            raise ValueError("Invalid ZIP file")
        except Exception as e:
            logger.error(f"Error processing ZIP file: {str(e)}")
            raise Exception(f"Error processing ZIP file: {str(e)}")
        
        # Persist package to GCP storage
        package_dict = package.model_dump()
        await storage_service.save_deal_package(package_dict)
        
        logger.info(f"Created deal package {package_id} with {sum(len(docs) for docs in package.documents.values())} documents")
        
        return package, file_cache_data