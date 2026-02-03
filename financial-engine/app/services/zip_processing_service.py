import logging
import zipfile
import io
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from app.models.schemas import DealPackage, DocumentMetadata, DocumentType
from app.services.storage_service import storage_service
from app.services.classification_service import ClassificationService
# Avoid circular import if ProgressService is needed only for typing
# But we need it for execution. We'll import inside the method if needed or use Any
from app.services.progress_service import ProgressService

logger = logging.getLogger(__name__)

# Folder name to DocumentType mapping
FOLDER_MAPPING = {
    # Offering Memorandum
    "offering memorandum": DocumentType.OFFERING_MEMORANDUM,
    "om": DocumentType.OFFERING_MEMORANDUM,
    "marketing": DocumentType.OFFERING_MEMORANDUM,
    "flyer": DocumentType.OFFERING_MEMORANDUM,
    "appraisal": DocumentType.OFFERING_MEMORANDUM,
    "setup": DocumentType.OFFERING_MEMORANDUM,
    "executive summary": DocumentType.OFFERING_MEMORANDUM,

    # Rent Roll
    "rent roll": DocumentType.RENT_ROLL,
    "rentroll": DocumentType.RENT_ROLL,
    "rr": DocumentType.RENT_ROLL,

    # Leases
    "leases": DocumentType.LEASES,
    "lease": DocumentType.LEASES,
    "tenancy agreements": DocumentType.LEASES,

    # Financials
    "financials": DocumentType.FINANCIALS,
    "financial": DocumentType.FINANCIALS,
    "t12": DocumentType.FINANCIALS,
    "trailing 12": DocumentType.FINANCIALS,
    "p&l": DocumentType.FINANCIALS,
    "profit & loss": DocumentType.FINANCIALS,
    "profit and loss": DocumentType.FINANCIALS,
    "income statement": DocumentType.FINANCIALS,
    "operating statement": DocumentType.FINANCIALS,
    "balance sheet": DocumentType.FINANCIALS,
    "historical": DocumentType.FINANCIALS,
    "expenses": DocumentType.FINANCIALS,
    "insurance": DocumentType.FINANCIALS,

    # Building Plans & Permits
    "building plans": DocumentType.BUILDING_PLANS_PERMITS,
    "plans": DocumentType.BUILDING_PLANS_PERMITS,
    "permits": DocumentType.BUILDING_PLANS_PERMITS,
    "survey": DocumentType.BUILDING_PLANS_PERMITS,
    "zoning": DocumentType.BUILDING_PLANS_PERMITS,
    "floor plans": DocumentType.BUILDING_PLANS_PERMITS,
    "site plan": DocumentType.BUILDING_PLANS_PERMITS,

    # Disclosures
    "disclosures": DocumentType.DISCLOSURES,
    "reports": DocumentType.DISCLOSURES,
    "environmental": DocumentType.DISCLOSURES,
    "phase i": DocumentType.DISCLOSURES,
    "phase 1": DocumentType.DISCLOSURES,
    "pca": DocumentType.DISCLOSURES,

    # Tax Bills
    "tax bills": DocumentType.TAX_BILLS,
    "tax bill": DocumentType.TAX_BILLS,
    "property tax": DocumentType.TAX_BILLS,
    "taxes": DocumentType.TAX_BILLS,
    "tax returns": DocumentType.TAX_BILLS,
    "assessor": DocumentType.TAX_BILLS,

    # Utilities
    "utilities": DocumentType.UTILITIES,
    "utility": DocumentType.UTILITIES,
    "bills": DocumentType.UTILITIES,
    "water": DocumentType.UTILITIES,
    "electric": DocumentType.UTILITIES,
    "gas": DocumentType.UTILITIES,
    "sewer": DocumentType.UTILITIES,
    "trash": DocumentType.UTILITIES,
}


def get_document_type_from_folder(folder_path: str) -> Optional[DocumentType]:
    """
    Determine document type based on folder name.
    Supports various naming conventions (with/without numbers, with/without dashes).
    """
    folder_name = os.path.basename(folder_path).lower().strip()
    
    # 1. Direct match (normalized)
    if folder_name in FOLDER_MAPPING:
        return FOLDER_MAPPING[folder_name]

    # 2. Heuristic: Remove common numbering prefixes (e.g., "01 - ", "1. ", "01-")
    # This helps matching "01 - Offering Memorandum" to "offering memorandum"
    cleaned_name = folder_name
    for i in range(10):
        cleaned_name = cleaned_name.replace(f"{i}", "").strip()
    cleaned_name = cleaned_name.replace("-", "").replace(".", "").strip()
    
    if cleaned_name in FOLDER_MAPPING:
        return FOLDER_MAPPING[cleaned_name]

    # 3. Fuzzy match: Check if any key is contained in the folder name
    # We prioritize longer keys to avoid false positives (e.g., "tax" in "taxi")
    sorted_keys = sorted(FOLDER_MAPPING.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in folder_name:
            return FOLDER_MAPPING[key]
            
    return None


class ZipProcessingService:
    """Service for processing ZIP uploads containing financial documents."""

    async def process_zip_file(
        self,
        zip_path: str,
        property_name: str,
        progress_service: Optional[ProgressService] = None,
        task_id: Optional[str] = None
    ) -> Tuple[DealPackage, Dict[str, Any]]:
        """
        Process a ZIP file from disk, extract documents, creating a DealPackage,
        and saving files to storage.
        """
        # This legacy method can now delegate to a more generic file processor if needed,
        # but for now we keep it as is for strict backward compatibility with existing structured ZIPs,
        # or we could enhance it to use the classifier fallback.
        # For this update, we will simply leave it as is to ensure stability,
        # and implement the new smart upload logic in process_smart_upload.
        return await self._process_zip_internal(zip_path, property_name, progress_service, task_id)

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped (hidden files, MACOSX artifacts, etc)."""
        if file_path.endswith('/'):
            return True
            
        basename = os.path.basename(file_path)
        if basename.startswith('.'):
            return True
            
        # Skip macOS resource forks
        if "__MACOSX" in file_path:
            return True
            
        return False

    async def _process_zip_internal(
        self,
        zip_path: str,
        property_name: str,
        progress_service: Optional[ProgressService] = None,
        task_id: Optional[str] = None,
        classification_service: Optional[ClassificationService] = None
    ) -> Tuple[DealPackage, Dict[str, Any]]:
        if progress_service and task_id:
            await progress_service.update_progress(task_id, 0, "Initializing ZIP processing...")

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
        
        # List to hold files that need classification
        files_to_classify: List[Dict[str, Any]] = []

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                logger.info(f"ZIP contains {len(file_list)} entries")
                
                total_files = len(file_list)
                
                for idx, file_path in enumerate(file_list):
                    if self._should_skip_file(file_path):
                        continue
                    
                    filename = os.path.basename(file_path)
                    
                    # Try to determine type from folder structure first
                    path_parts = Path(file_path).parts
                    folder_name = None
                    doc_type = None
                    
                    # Check path parts for folder mapping
                    if len(path_parts) > 1:
                        for part in path_parts[:-1]:
                            dt = get_document_type_from_folder(part)
                            if dt:
                                doc_type = dt
                                folder_name = part
                                break
                    
                    # If not found in folder, and we have a classification service,
                    # we will queue it for classification
                    if not doc_type and classification_service:
                         # Read content for classification
                        file_content = zip_ref.read(file_path)
                        if len(file_content) == 0: continue
                        
                        files_to_classify.append({
                            "filename": filename,
                            "content": file_content,
                            "file_path": file_path
                        })
                        continue
                    elif not doc_type:
                        # Legacy behavior: check parent folder or skip
                        if len(path_parts) >= 2:
                             folder_name = path_parts[-2]
                             doc_type = get_document_type_from_folder(folder_name)
                        
                        if not doc_type:
                            logger.warning(f"Could not determine document type for file: {file_path}")
                            files_skipped += 1
                            continue

                    # If we got here, we have a doc_type from folder structure
                    file_content = zip_ref.read(file_path)
                    if len(file_content) == 0: continue

                    await self._add_file_to_package(
                        package, package_id, filename, doc_type, file_content, now, file_cache_data
                    )
                    files_processed += 1
                    
                    if progress_service and task_id:
                        percent = 10 + int((idx + 1) / total_files * 60)
                        await progress_service.update_progress(task_id, percent, f"Processing: {filename}")

                # Batch classify remaining files if any
                if files_to_classify and classification_service:
                    if progress_service and task_id:
                        await progress_service.update_progress(task_id, 70, f"Classifying {len(files_to_classify)} files based on content...")
                    
                    # Prepare files with content for content-based classification
                    files_with_content = [(f["filename"], f["content"]) for f in files_to_classify]
                    classification_results = await classification_service.classify_files_batch(files=files_with_content)
                    
                    for f_item in files_to_classify:
                        fname = f_item["filename"]
                        doc_type = classification_results.get(fname)
                        
                        if doc_type:
                            await self._add_file_to_package(
                                package, package_id, fname, doc_type, f_item["content"], now, file_cache_data
                            )
                            files_processed += 1
                        else:
                            logger.warning(f"Could not classify file based on content: {fname}")
                            files_skipped += 1

                # Check for empty folders
                for doc_type in DocumentType:
                    if doc_type not in package.documents or len(package.documents[doc_type]) == 0:
                        empty_folders.append(doc_type.value)
                
                logger.info(f"Processing complete: {files_processed} files processed, {files_skipped} skipped")

        except zipfile.BadZipFile:
            raise ValueError("Invalid ZIP file")
        except Exception as e:
            logger.error(f"Error processing ZIP file: {str(e)}")
            raise Exception(f"Error processing ZIP file: {str(e)}")
        
        # Persist package
        package_dict = package.model_dump()
        await storage_service.save_deal_package(package_dict)
        
        if progress_service and task_id:
            await progress_service.update_progress(task_id, 100, "Processing complete!")

        return package, file_cache_data

    async def _add_file_to_package(self, package, package_id, filename, doc_type, content, now, file_cache_data):
        """Helper to add file to package and storage"""
        document_id = str(uuid.uuid4())
        doc_metadata = DocumentMetadata(
            document_id=document_id,
            filename=filename,
            document_type=doc_type,
            upload_timestamp=now,
            file_size=len(content),
            extraction_status="pending"
        )
        
        package.documents[doc_type].append(doc_metadata)
        
        file_cache_data[document_id] = {
            "content": content,
            "filename": filename,
            "document_type": doc_type,
            "package_id": package_id
        }
        
        await storage_service.save_document_file(
            package_id=package_id,
            document_id=document_id,
            filename=filename,
            file_content=content
        )

    async def process_smart_upload(
        self,
        files: List[Tuple[str, bytes]], # List of (filename, content)
        property_name: str,
        classification_service: ClassificationService,
        progress_service: Optional[ProgressService] = None,
        task_id: Optional[str] = None
    ) -> Tuple[DealPackage, Dict[str, Any]]:
        """
        Process a list of loose files (or mixed content) using AI classification.
        """
        if progress_service and task_id:
            await progress_service.update_progress(task_id, 0, "Initializing Smart Upload...")

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
        
        file_cache_data = {}
        files_processed = 0
        
        # 1. separate files into known (by folder/path) and unknown (need classification)
        files_to_classify = []
        known_files = [] # list of (filename, content, doc_type)
        
        for filename, content in files:
            # Check for skip first (in case not filtered upstream)
            if self._should_skip_file(filename):
                continue

            # Try to determine type from folder structure first
            path_parts = Path(filename).parts
            found_type = None
            
            # Check path parts for folder mapping
            if len(path_parts) > 1:
                for part in path_parts[:-1]:
                    dt = get_document_type_from_folder(part)
                    if dt:
                        found_type = dt
                        break
            
            if found_type:
                known_files.append((filename, content, found_type))
            else:
                files_to_classify.append((filename, content))

        # 2. Classify unknown files using content-based classification
        if files_to_classify:
            if progress_service and task_id:
                await progress_service.update_progress(task_id, 20, f"Classifying {len(files_to_classify)} files based on content...")
                
            # Pass files with content for content-based classification
            classifications = await classification_service.classify_files_batch(files=files_to_classify)
        else:
            classifications = {}

        # 3. Add all files to package
        all_files = known_files + files_to_classify
        total_files = len(all_files)
        
        for idx, item in enumerate(all_files):
            if len(item) == 3:
                filename, content, doc_type = item
            else:
                filename, content = item
                doc_type = classifications.get(filename)
            
            if doc_type:
                # Use basename for storage/metadata to keep it clean
                safe_filename = os.path.basename(filename)
                await self._add_file_to_package(
                    package, package_id, safe_filename, doc_type, content, now, file_cache_data
                )
                files_processed += 1
            else:
                # Handle unknown files -> maybe map to 'Other' or 'Uncategorized' if we had one?
                # For now, we'll skip or map to DISCLOSURES as a fallback bucket? No, better to skip or warn.
                # Actually, let's map to DISCLOSURES if unknown? No.
                # Let's map to OFFERING_MEMORANDUM if it's a PDF and large? No.
                # Just skip for now and log.
                logger.warning(f"Could not classify file {filename}. Skipping.")
            
            if progress_service and task_id:
                percent = 30 + int((idx + 1) / len(files) * 60)
                await progress_service.update_progress(task_id, percent, f"Processed {filename}")
        
        # 3. Save Package
        package_dict = package.model_dump()
        await storage_service.save_deal_package(package_dict)
        
        if progress_service and task_id:
            await progress_service.update_progress(task_id, 100, "Upload complete!")
            
        return package, file_cache_data

    async def add_files_to_package(
        self,
        package_id: str,
        files: List[Tuple[str, bytes]],
        classification_service: Optional[ClassificationService] = None
    ) -> Tuple[DealPackage, Dict[str, Any]]:
        """
        Add additional files to an existing package using classification.
        """
        # Load existing package
        package_data = await storage_service.get_deal_package(package_id)
        if not package_data:
            raise ValueError(f"Package {package_id} not found")
        
        package = DealPackage(**package_data)
        now = datetime.utcnow().isoformat()
        file_cache_data = {}
        
        # 1. separate files into known (by folder/path) and unknown (need classification)
        files_to_classify = []
        known_files = [] # list of (filename, content, doc_type)
        
        for filename, content in files:
            # Check for skip first
            if self._should_skip_file(filename):
                continue

            # Try to determine type from folder structure first
            path_parts = Path(filename).parts
            found_type = None
            
            # Check path parts for folder mapping
            if len(path_parts) > 1:
                for part in path_parts[:-1]:
                    dt = get_document_type_from_folder(part)
                    if dt:
                        found_type = dt
                        break
            
            if found_type:
                known_files.append((filename, content, found_type))
            else:
                files_to_classify.append((filename, content))

        # 2. Classify unknown files using content-based classification
        if files_to_classify and classification_service:
            # Pass files with content for content-based classification
            classifications = await classification_service.classify_files_batch(files=files_to_classify)
        else:
            classifications = {}

        # 3. Add all files to package
        all_files = known_files + files_to_classify
        files_added = 0
        
        for idx, item in enumerate(all_files):
            if len(item) == 3:
                filename, content, doc_type = item
            else:
                filename, content = item
                doc_type = classifications.get(filename)
            
            if doc_type:
                safe_filename = os.path.basename(filename)
                await self._add_file_to_package(
                    package, package_id, safe_filename, doc_type, content, now, file_cache_data
                )
                files_added += 1
            else:
                logger.warning(f"Could not classify additional file {filename}. Skipping.")

        if files_added > 0:
            package.updated_at = now
            # Reset normalization status if new files are added, so we re-process
            package.normalization_status = "pending"
            await storage_service.save_deal_package(package.model_dump())
        
        return package, file_cache_data