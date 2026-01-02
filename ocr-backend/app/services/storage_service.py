"""Storage service for GCP Cloud Storage file management."""

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from io import BytesIO

from google.cloud import storage
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError

from app.config import settings
from app.utils.logger import logger


class StorageService:
    """Service for managing file storage with GCP Cloud Storage."""
    
    def __init__(self):
        """Initialize GCP Cloud Storage service."""
        self._init_gcp_storage()
    
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
            
            # Get bucket reference (don't check existence - requires additional permissions)
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
    
    def _generate_storage_path(self, file_id: str, extension: str) -> str:
        """
        Generate date-based storage path for file organization.
        
        Format: uploads/documents/{year}/{month:02d}/{file_id}{extension}
        
        Args:
            file_id: Unique file identifier
            extension: File extension (including dot)
            
        Returns:
            Storage path string
        """
        now = datetime.utcnow()
        year = now.year
        month = now.month
        
        return f"uploads/documents/{year}/{month:02d}/{file_id}{extension}"
    
    def generate_file_id(self, original_filename: str) -> tuple[str, str]:
        """
        Generate unique file ID and storage path.
        
        Args:
            original_filename: Original name of the file
            
        Returns:
            Tuple of (file_id, storage_path)
        """
        file_id = str(uuid.uuid4())
        extension = Path(original_filename).suffix
        storage_path = self._generate_storage_path(file_id, extension)
        
        return file_id, storage_path
    
    async def save_file(
        self,
        file_data: bytes,
        filename: str
    ) -> tuple[str, str]:
        """
        Save file to GCP Cloud Storage.
        
        Args:
            file_data: File content as bytes
            filename: Original filename
            
        Returns:
            Tuple of (file_id, storage_path)
        """
        file_id, storage_path = self.generate_file_id(filename)
        
        try:
            # Create blob reference
            blob = self.bucket.blob(storage_path)
            
            # Set content type based on file extension
            content_type = self._get_content_type(filename)
            
            # Upload file
            blob.upload_from_file(
                BytesIO(file_data),
                content_type=content_type
            )
            
            logger.info(f"Saved file to GCP: {filename} -> {storage_path}")
            return file_id, storage_path
            
        except Exception as e:
            logger.error(f"Failed to save file to GCP: {str(e)}")
            raise
    
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
    
    async def get_file(self, storage_path: str) -> bytes:
        """
        Retrieve file from GCP Cloud Storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            File content as bytes
        """
        try:
            blob = self.bucket.blob(storage_path)
            
            if not blob.exists():
                raise FileNotFoundError(f"File not found in GCP storage: {storage_path}")
            
            # Download file content
            data = blob.download_as_bytes()
            
            logger.info(f"Retrieved file from GCP: {storage_path}")
            return data
            
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve file from GCP: {str(e)}")
            raise
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from GCP Cloud Storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if deleted successfully
        """
        try:
            blob = self.bucket.blob(storage_path)
            
            if blob.exists():
                blob.delete()
                logger.info(f"Deleted file from GCP: {storage_path}")
                return True
            else:
                logger.warning(f"File not found for deletion: {storage_path}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to delete file from GCP: {str(e)}")
            return False
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if file exists in GCP Cloud Storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if file exists
        """
        try:
            blob = self.bucket.blob(storage_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking file existence: {str(e)}")
            return False
    
    def generate_signed_url(
        self,
        storage_path: str,
        expiration_minutes: int = 60
    ) -> str:
        """
        Generate a signed URL for temporary file access.
        
        Args:
            storage_path: Path to the file in storage
            expiration_minutes: URL expiration time in minutes (default: 60)
            
        Returns:
            Signed URL string
        """
        try:
            blob = self.bucket.blob(storage_path)
            
            # Generate signed URL
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            
            logger.info(f"Generated signed URL for: {storage_path} (expires in {expiration_minutes} min)")
            return url
            
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {str(e)}")
            raise
    
    def list_files(self, prefix: Optional[str] = None) -> list[str]:
        """
        List files in GCP Cloud Storage with optional prefix filter.
        
        Args:
            prefix: Optional prefix to filter files (e.g., "uploads/documents/2026/01/")
            
        Returns:
            List of file paths
        """
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            file_paths = [blob.name for blob in blobs]
            
            logger.info(f"Listed {len(file_paths)} files with prefix: {prefix or 'all'}")
            return file_paths
            
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []


# Create singleton instance
storage_service = StorageService()
