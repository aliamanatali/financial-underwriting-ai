"""Storage service for GCP Cloud Storage and deal package persistence."""

import os
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from io import BytesIO

from google.cloud import storage  # type: ignore
from google.oauth2 import service_account  # type: ignore
from google.auth.exceptions import DefaultCredentialsError  # type: ignore

from app.config import settings
import logging
from app.db.mongodb import get_database
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


# In-memory storage for when GCP/Mongo is not configured
_memory_storage: Dict[str, dict] = {}

# Cache for package list to avoid repeated GCP calls
_package_list_cache: Optional[tuple[List[dict], datetime]] = None
_CACHE_TTL_SECONDS = 60  # Cache for 60 seconds

logger = logging.getLogger(__name__)


class StorageService:
    """
    Service for managing file storage (GCP) and deal package persistence (MongoDB).
    Metadata is stored in MongoDB if configured, otherwise falls back to GCP -> Memory.
    Files are always stored in GCP or skipped if not configured.
    """
    
    def __init__(self):
        """Initialize GCP Cloud Storage service."""
        self.use_gcp = settings.use_gcp
        self.use_mongodb = settings.use_mongodb
        
        if self.use_gcp:
            self._init_gcp_storage()
        else:
            logger.warning("GCP Cloud Storage not configured. Using local file storage.")
            self.storage_client = None
            self.bucket = None
            
        # Initialize local storage directory
        self.local_storage_dir = Path("data/storage")
        self.local_storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_gcp_storage(self):
        """Initialize GCP Cloud Storage client."""
        try:
            credentials = None
            
            # Method 1: Environment variables (recommended for production)
            if all([
                settings.gcp_type,
                settings.gcp_private_key,
                settings.gcp_client_email
            ]):
                logger.info("Initializing GCP with environment variable credentials")
                
                # Validate private key format
                if not settings.gcp_private_key.startswith("-----BEGIN PRIVATE KEY-----"):
                    raise ValueError("GCP_PRIVATE_KEY is not in correct format")
                
                # Construct credentials dictionary from environment variables
                credentials_dict = {
                    "type": settings.gcp_type,
                    "project_id": settings.gcp_project_id,
                    "private_key_id": settings.gcp_private_key_id,
                    "private_key": settings.gcp_private_key,
                    "client_email": settings.gcp_client_email,
                    "client_id": settings.gcp_client_id,
                    "auth_uri": settings.gcp_auth_uri or "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": settings.gcp_token_uri or "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": settings.gcp_auth_provider_x509_cert_url or "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": settings.gcp_client_x509_cert_url,
                    "universe_domain": settings.gcp_universe_domain or "googleapis.com"
                }
                
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict
                )
                
            # Method 2: Credentials file (legacy support)
            elif settings.gcp_credentials_path and os.path.exists(settings.gcp_credentials_path):
                logger.info(f"Initializing GCP with credentials file: {settings.gcp_credentials_path}")
                credentials = service_account.Credentials.from_service_account_file(
                    settings.gcp_credentials_path
                )
            
            # Method 3: Default credentials (development)
            else:
                logger.info("Attempting to use default GCP credentials")
                credentials = None  # Will use default credentials
            
            # Initialize storage client
            self.storage_client = storage.Client(
                project=settings.gcp_project_id,
                credentials=credentials
            )
            
            # Get bucket reference
            self.bucket = self.storage_client.bucket(settings.gcp_storage_bucket)
            
            logger.info(f"GCP Cloud Storage initialized successfully - Bucket: {settings.gcp_storage_bucket}")
            
        except DefaultCredentialsError as e:
            logger.error(f"GCP credentials not found: {str(e)}")
            raise ValueError(
                "GCP Cloud Storage credentials not configured. "
                "Please set GCP environment variables or provide credentials file."
            )
        except Exception as e:
            logger.error(f"Failed to initialize GCP Cloud Storage: {str(e)}")
            raise
    
    def _get_document_path(self, package_id: str, document_id: str, filename: str) -> str:
        """Get storage path for document file."""
        extension = Path(filename).suffix
        return f"deal-packages/{package_id}/documents/{document_id}{extension}"
    
    async def save_deal_package(self, package_data: dict) -> bool:
        """
        Save deal package metadata to MongoDB (or fallback).
        
        Args:
            package_data: Dictionary containing package metadata
            
        Returns:
            True if saved successfully
        """
        package_id = package_data.get("package_id")
        if not package_id:
            logger.error("package_id is required")
            return False

        # 1. MongoDB Strategy (Preferred)
        if self.use_mongodb:
            try:
                db = get_database()
                # Upsert based on package_id
                await db.deal_packages.update_one(
                    {"package_id": package_id},
                    {"$set": package_data},
                    upsert=True
                )
                logger.info(f"Saved deal package metadata to MongoDB: {package_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to save deal package to MongoDB: {str(e)}")
                return False

        # 2. Fallback Strategy (In-Memory)
        logger.warning("MongoDB not configured. Using in-memory storage for metadata.")
        _memory_storage[package_id] = package_data
        return True

    async def save_analysis_result(self, package_id: str, analysis_data: dict) -> bool:
        """
        Save underwriting analysis result to MongoDB (or fallback).
        
        Args:
            package_id: Package identifier
            analysis_data: Dictionary containing analysis result
            
        Returns:
            True if saved successfully
        """
        # 1. MongoDB Strategy (Preferred)
        if self.use_mongodb:
            try:
                db = get_database()
                # Upsert based on document_id (which acts as package_id for single-doc analysis)
                # Note: analysis_data usually contains 'document_id' which maps to package_id here
                doc_id = analysis_data.get("document_id", package_id)
                
                await db.analysis_results.update_one(
                    {"document_id": doc_id},
                    {"$set": analysis_data},
                    upsert=True
                )
                logger.info(f"Saved analysis result to MongoDB: {package_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to save analysis result to MongoDB: {str(e)}")
                return False

        # 2. Fallback Strategy
        logger.warning("MongoDB not configured. Using in-memory storage for analysis result.")
        _memory_storage[f"{package_id}_analysis"] = analysis_data
        return True

    async def get_analysis_result(self, package_id: str) -> Optional[dict]:
        """
        Retrieve underwriting analysis result from MongoDB (or fallback).
        
        Args:
            package_id: Package identifier
            
        Returns:
            Analysis result dictionary or None if not found
        """
        # 1. MongoDB Strategy
        if self.use_mongodb:
            try:
                db = get_database()
                # In single-doc mode, package_id == document_id
                result = await db.analysis_results.find_one({"document_id": package_id})
                if result:
                    # Remove Mongo _id
                    if "_id" in result:
                        del result["_id"]
                    logger.info(f"Retrieved analysis result from MongoDB: {package_id}")
                    return result
                else:
                    logger.warning(f"Analysis result not found in MongoDB: {package_id}")
                    return None
            except Exception as e:
                logger.error(f"Failed to retrieve analysis result from MongoDB: {str(e)}")
                return None

        # 2. Fallback Strategy
        return _memory_storage.get(f"{package_id}_analysis")
    
    async def get_deal_package(self, package_id: str) -> Optional[dict]:
        """
        Retrieve deal package metadata from MongoDB (or fallback).
        
        Args:
            package_id: Package identifier
            
        Returns:
            Package metadata dictionary or None if not found
        """
        # 1. MongoDB Strategy
        if self.use_mongodb:
            try:
                db = get_database()
                result = await db.deal_packages.find_one({"package_id": package_id})
                if result:
                    if "_id" in result:
                        del result["_id"]
                    logger.info(f"Retrieved deal package from MongoDB: {package_id}")
                    return result
                else:
                    logger.warning(f"Package not found in MongoDB: {package_id}")
                    return None
            except Exception as e:
                logger.error(f"Failed to retrieve deal package from MongoDB: {str(e)}")
                return None

        # 2. Fallback Strategy
        return _memory_storage.get(package_id)
    
    async def update_deal_package_timestamp(self, package_id: str) -> bool:
        """
        Update the updated_at timestamp for a deal package.
        """
        now = datetime.utcnow().isoformat()
        
        # 1. MongoDB Strategy
        if self.use_mongodb:
            try:
                db = get_database()
                await db.deal_packages.update_one(
                    {"package_id": package_id},
                    {"$set": {"updated_at": now}}
                )
                logger.info(f"Updated timestamp for deal package in MongoDB: {package_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to update deal package timestamp in MongoDB: {str(e)}")
                return False

        # 2. Fallback Strategy
        if package_id in _memory_storage:
            _memory_storage[package_id]["updated_at"] = now
            return True
        return False
    
    async def update_deal_package_status(self, package_id: str, status: str) -> bool:
        """
        Update the status and updated_at timestamp for a deal package.
        """
        now = datetime.utcnow().isoformat()
        
        # 1. MongoDB Strategy
        if self.use_mongodb:
            try:
                db = get_database()
                await db.deal_packages.update_one(
                    {"package_id": package_id},
                    {"$set": {
                        "normalization_status": status,
                        "updated_at": now
                    }}
                )
                logger.info(f"Updated status to {status} for deal package in MongoDB: {package_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to update deal package status in MongoDB: {str(e)}")
                return False

        # 2. Fallback Strategy
        if package_id in _memory_storage:
            _memory_storage[package_id]["normalization_status"] = status
            _memory_storage[package_id]["updated_at"] = now
            return True
        return False
    
    async def list_deal_packages(self, limit: Optional[int] = None, offset: int = 0, force_refresh: bool = False) -> tuple[List[dict], int]:
        """
        List deal packages from MongoDB with pagination support.
        
        Args:
            limit: Maximum number of packages to return (None = all)
            offset: Number of packages to skip
            force_refresh: Ignored for MongoDB
            
        Returns:
            Tuple of (packages list, total count)
        """
        # 1. MongoDB Strategy
        if self.use_mongodb:
            try:
                db = get_database()
                total = await db.deal_packages.count_documents({})
                
                cursor = db.deal_packages.find({}).sort("created_at", -1).skip(offset)
                if limit is not None:
                    cursor = cursor.limit(limit)
                
                packages = []
                async for pkg in cursor:
                    if "_id" in pkg:
                        del pkg["_id"]
                    packages.append(pkg)
                
                logger.info(f"Listed {len(packages)} deal packages from MongoDB (total={total})")
                return packages, total
            except Exception as e:
                logger.error(f"Failed to list deal packages from MongoDB: {str(e)}")
                return [], 0

        # 2. Fallback Strategy
        # Filter out analysis results (keys ending with _analysis)
        packages = [
            pkg for key, pkg in _memory_storage.items()
            if not key.endswith('_analysis') and isinstance(pkg, dict) and 'package_id' in pkg
        ]
        # Sort by created_at (newest first)
        packages.sort(key=lambda p: p.get('created_at', ''), reverse=True)
        total = len(packages)
        
        # Apply pagination
        if limit is not None:
            packages = packages[offset:offset + limit]
        
        return packages, total
    
    async def delete_deal_package(self, package_id: str) -> bool:
        """
        Delete deal package from MongoDB and associated files from GCP or local storage.
        
        Args:
            package_id: Package identifier
            
        Returns:
            True if deleted successfully
        """
        success = True

        # 1. Delete Metadata from MongoDB
        if self.use_mongodb:
            try:
                db = get_database()
                await db.deal_packages.delete_one({"package_id": package_id})
                await db.analysis_results.delete_one({"document_id": package_id})
                logger.info(f"Deleted deal package metadata from MongoDB: {package_id}")
            except Exception as e:
                logger.error(f"Failed to delete deal package from MongoDB: {str(e)}")
                success = False

        # 2. Delete Files from GCP (if configured)
        if self.use_gcp:
            try:
                # Delete all files in the package directory
                prefix = f"deal-packages/{package_id}/"
                
                def _delete_blobs():
                    blobs = self.bucket.list_blobs(prefix=prefix)
                    count = 0
                    for blob in blobs:
                        blob.delete()
                        count += 1
                    return count

                deleted_count = await run_in_threadpool(_delete_blobs)
                
                logger.info(f"Deleted deal package files from GCP: {package_id} ({deleted_count} files)")
            except Exception as e:
                logger.error(f"Failed to delete deal package files from GCP: {str(e)}")
                success = False
        else:
            # Delete files from local storage
            try:
                import shutil
                package_dir = self.local_storage_dir / "deal-packages" / package_id
                if package_dir.exists():
                    shutil.rmtree(package_dir)
                    logger.info(f"Deleted local deal package files: {package_dir}")
            except Exception as e:
                logger.error(f"Failed to delete local deal package files: {str(e)}")
                success = False
        
        # 3. Memory cleanup
        if package_id in _memory_storage:
            del _memory_storage[package_id]
        if f"{package_id}_analysis" in _memory_storage:
            del _memory_storage[f"{package_id}_analysis"]
            
        return success
    
    async def save_document_file(
        self,
        package_id: str,
        document_id: str,
        filename: str,
        file_content: bytes
    ) -> Optional[str]:
        """
        Save document file to GCP Cloud Storage or local storage.
        
        Args:
            package_id: Package identifier
            document_id: Document identifier
            filename: Original filename
            file_content: File content as bytes
            
        Returns:
            Storage path if saved successfully, None otherwise
        """
        blob_path = self._get_document_path(package_id, document_id, filename)
        
        if self.use_gcp:
            try:
                blob = self.bucket.blob(blob_path)
                
                # Determine content type
                content_type = self._get_content_type(filename)
                
                # Upload file
                await run_in_threadpool(
                    blob.upload_from_file,
                    BytesIO(file_content),
                    content_type=content_type
                )
                
                logger.info(f"Saved document file to GCP: {filename} -> {blob_path}")
                return blob_path
                
            except Exception as e:
                logger.error(f"Failed to save document file to GCP: {str(e)}")
                return None
        else:
            # Local Storage
            try:
                full_path = self.local_storage_dir / blob_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(full_path, "wb") as f:
                    f.write(file_content)
                    
                logger.info(f"Saved document file locally: {filename} -> {full_path}")
                return str(full_path)
            except Exception as e:
                logger.error(f"Failed to save document file locally: {str(e)}")
                return None
    
    async def get_document_file(self, storage_path: str) -> Optional[bytes]:
        """
        Retrieve document file from GCP Cloud Storage or local storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            File content as bytes or None if not found
        """
        if self.use_gcp:
            try:
                blob = self.bucket.blob(storage_path)
                
                if not blob.exists():
                    logger.warning(f"Document file not found in GCP: {storage_path}")
                    return None
                
                # Download file content
                data = await run_in_threadpool(blob.download_as_bytes)
                
                logger.info(f"Retrieved document file from GCP: {storage_path}")
                return data
                
            except Exception as e:
                logger.error(f"Failed to retrieve document file from GCP: {str(e)}")
                return None
        else:
            # Local Storage
            try:
                # storage_path is like "deal-packages/..."
                full_path = self.local_storage_dir / storage_path
                
                if not full_path.exists():
                    logger.warning(f"Document file not found locally: {full_path}")
                    return None
                    
                with open(full_path, "rb") as f:
                    data = f.read()
                    
                logger.info(f"Retrieved document file locally: {storage_path}")
                return data
            except Exception as e:
                logger.error(f"Failed to retrieve document file locally: {str(e)}")
                return None
    
    async def get_signed_url(self, storage_path: str, expiration_minutes: int = 15) -> Optional[str]:
        """
        Generate a signed URL for a document in GCP Cloud Storage.
        
        Args:
            storage_path: Path to the file in storage
            expiration_minutes: URL validity in minutes
            
        Returns:
            Signed URL string or None if failed
        """
        if not self.use_gcp:
            # For local storage, we can't generate a real signed URL that works externally.
            # The API endpoint get_package_document_content serves content directly anyway.
            # Returning None makes the frontend use the proxy endpoint.
            return None
        
        try:
            blob = self.bucket.blob(storage_path)
            
            # Check if blob exists
            if not blob.exists():
                logger.warning(f"Cannot generate signed URL, blob not found: {storage_path}")
                return None
            
            # Generate signed URL
            # Note: This requires the service account to have signing permissions
            # The service account needs 'Service Account Token Creator' role or similar
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            
            logger.info(f"Generated signed URL for: {storage_path}")
            return signed_url
            
        except AttributeError as e:
            logger.error(f"Credentials error - service account may lack signing permissions: {str(e)}")
            logger.error("Ensure the service account has 'Service Account Token Creator' role")
            return None
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {storage_path}: {str(e)}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}")
            return None

    def _get_content_type(self, filename: str) -> str:
        """
        Determine content type based on file extension.
        
        Args:
            filename: Name of the file
            
        Returns:
            Content type string
        """
        extension = Path(filename).suffix.lower()
        
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.csv': 'text/csv',
        }
        
        return content_types.get(extension, 'application/octet-stream')


# Create singleton instance
storage_service = StorageService()
