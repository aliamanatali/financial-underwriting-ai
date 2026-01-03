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

logger = logging.getLogger(__name__)


# In-memory storage for when GCP is not configured
_memory_storage: Dict[str, dict] = {}
import logging

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing file storage and deal package persistence with GCP Cloud Storage."""
    
    def __init__(self):
        """Initialize GCP Cloud Storage service."""
        self.use_gcp = settings.use_gcp
        
        if self.use_gcp:
            self._init_gcp_storage()
        else:
            logger.warning("GCP Cloud Storage not configured. Using in-memory storage only.")
            self.storage_client = None
            self.bucket = None
    
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
    
    def _get_package_metadata_path(self, package_id: str) -> str:
        """Get storage path for package metadata."""
        return f"deal-packages/{package_id}/metadata.json"

    def _get_analysis_result_path(self, package_id: str) -> str:
        """Get storage path for analysis result."""
        return f"deal-packages/{package_id}/analysis_result.json"
    
    def _get_document_path(self, package_id: str, document_id: str, filename: str) -> str:
        """Get storage path for document file."""
        extension = Path(filename).suffix
        return f"deal-packages/{package_id}/documents/{document_id}{extension}"
    
    async def save_deal_package(self, package_data: dict) -> bool:
        """
        Save deal package metadata to GCP Cloud Storage.
        
        Args:
            package_data: Dictionary containing package metadata
            
        Returns:
            True if saved successfully
        """
        package_id = package_data.get("package_id")
        if not package_id:
            logger.error("package_id is required")
            return False

        if not self.use_gcp:
            logger.warning("GCP not configured. Using in-memory storage.")
            _memory_storage[package_id] = package_data
            return True
        
        try:
            # Convert to JSON
            json_data = json.dumps(package_data, indent=2, default=str)
            
            # Save to GCP
            blob_path = self._get_package_metadata_path(package_id)
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(json_data, content_type="application/json")
            
            logger.info(f"Saved deal package metadata: {package_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save deal package: {str(e)}")
            return False

    async def save_analysis_result(self, package_id: str, analysis_data: dict) -> bool:
        """
        Save underwriting analysis result to GCP Cloud Storage.
        
        Args:
            package_id: Package identifier
            analysis_data: Dictionary containing analysis result
            
        Returns:
            True if saved successfully
        """
        if not self.use_gcp:
            logger.warning("GCP not configured. Using in-memory storage for analysis result.")
            _memory_storage[f"{package_id}_analysis"] = analysis_data
            return True
        
        try:
            # Convert to JSON
            json_data = json.dumps(analysis_data, indent=2, default=str)
            
            # Save to GCP
            blob_path = self._get_analysis_result_path(package_id)
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(json_data, content_type="application/json")
            
            logger.info(f"Saved analysis result: {package_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save analysis result: {str(e)}")
            return False

    async def get_analysis_result(self, package_id: str) -> Optional[dict]:
        """
        Retrieve underwriting analysis result from GCP Cloud Storage.
        
        Args:
            package_id: Package identifier
            
        Returns:
            Analysis result dictionary or None if not found
        """
        if not self.use_gcp:
            return _memory_storage.get(f"{package_id}_analysis")
        
        try:
            blob_path = self._get_analysis_result_path(package_id)
            blob = self.bucket.blob(blob_path)
            
            if not blob.exists():
                logger.warning(f"Analysis result not found in GCP: {package_id}")
                return None
            
            # Download and parse JSON
            json_data = blob.download_as_text()
            analysis_data = json.loads(json_data)
            
            logger.info(f"Retrieved analysis result: {package_id}")
            return analysis_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve analysis result: {str(e)}")
            return None
    
    async def get_deal_package(self, package_id: str) -> Optional[dict]:
        """
        Retrieve deal package metadata from GCP Cloud Storage.
        
        Args:
            package_id: Package identifier
            
        Returns:
            Package metadata dictionary or None if not found
        """
        if not self.use_gcp:
            return _memory_storage.get(package_id)
        
        try:
            blob_path = self._get_package_metadata_path(package_id)
            blob = self.bucket.blob(blob_path)
            
            if not blob.exists():
                logger.warning(f"Package not found in GCP: {package_id}")
                return None
            
            # Download and parse JSON
            json_data = blob.download_as_text()
            package_data = json.loads(json_data)
            
            logger.info(f"Retrieved deal package: {package_id}")
            return package_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve deal package: {str(e)}")
            return None
    
    async def list_deal_packages(self) -> List[dict]:
        """
        List all deal packages from GCP Cloud Storage.
        
        Returns:
            List of package metadata dictionaries
        """
        if not self.use_gcp:
            return list(_memory_storage.values())
        
        try:
            # List all metadata files
            blobs = self.bucket.list_blobs(prefix="deal-packages/")
            packages = []
            
            for blob in blobs:
                if blob.name.endswith("/metadata.json"):
                    try:
                        json_data = blob.download_as_text()
                        package_data = json.loads(json_data)
                        packages.append(package_data)
                    except Exception as e:
                        logger.error(f"Error loading package from {blob.name}: {str(e)}")
                        continue
            
            logger.info(f"Listed {len(packages)} deal packages")
            return packages
            
        except Exception as e:
            logger.error(f"Failed to list deal packages: {str(e)}")
            return []
    
    async def delete_deal_package(self, package_id: str) -> bool:
        """
        Delete deal package and all its documents from GCP Cloud Storage.
        
        Args:
            package_id: Package identifier
            
        Returns:
            True if deleted successfully
        """
        if not self.use_gcp:
            return False
        
        try:
            # Delete all files in the package directory
            prefix = f"deal-packages/{package_id}/"
            blobs = self.bucket.list_blobs(prefix=prefix)
            
            deleted_count = 0
            for blob in blobs:
                blob.delete()
                deleted_count += 1
            
            logger.info(f"Deleted deal package {package_id} ({deleted_count} files)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete deal package: {str(e)}")
            return False
    
    async def save_document_file(
        self,
        package_id: str,
        document_id: str,
        filename: str,
        file_content: bytes
    ) -> Optional[str]:
        """
        Save document file to GCP Cloud Storage.
        
        Args:
            package_id: Package identifier
            document_id: Document identifier
            filename: Original filename
            file_content: File content as bytes
            
        Returns:
            Storage path if saved successfully, None otherwise
        """
        if not self.use_gcp:
            logger.warning("GCP not configured. Document file not persisted.")
            return None
        
        try:
            blob_path = self._get_document_path(package_id, document_id, filename)
            blob = self.bucket.blob(blob_path)
            
            # Determine content type
            content_type = self._get_content_type(filename)
            
            # Upload file
            blob.upload_from_file(
                BytesIO(file_content),
                content_type=content_type
            )
            
            logger.info(f"Saved document file: {filename} -> {blob_path}")
            return blob_path
            
        except Exception as e:
            logger.error(f"Failed to save document file: {str(e)}")
            return None
    
    async def get_document_file(self, storage_path: str) -> Optional[bytes]:
        """
        Retrieve document file from GCP Cloud Storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            File content as bytes or None if not found
        """
        if not self.use_gcp:
            return None
        
        try:
            blob = self.bucket.blob(storage_path)
            
            if not blob.exists():
                logger.warning(f"Document file not found: {storage_path}")
                return None
            
            # Download file content
            data = blob.download_as_bytes()
            
            logger.info(f"Retrieved document file: {storage_path}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to retrieve document file: {str(e)}")
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
