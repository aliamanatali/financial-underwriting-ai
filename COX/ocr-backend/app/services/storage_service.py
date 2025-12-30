"""Storage service for file management (local and MinIO)."""

import os
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from minio import Minio
from minio.error import S3Error

from app.config import settings
from app.utils.logger import logger


class StorageService:
    """Service for managing file storage (local or MinIO)."""
    
    def __init__(self):
        """Initialize storage service."""
        self.use_minio = settings.use_minio
        
        if self.use_minio:
            self._init_minio()
        else:
            self._init_local_storage()
    
    def _init_minio(self):
        """Initialize MinIO client."""
        try:
            self.minio_client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_use_ssl
            )
            
            # Create bucket if it doesn't exist
            if not self.minio_client.bucket_exists(settings.minio_bucket):
                self.minio_client.make_bucket(settings.minio_bucket)
                logger.info(f"Created MinIO bucket: {settings.minio_bucket}")
            
            logger.info("MinIO storage initialized successfully")
            
        except S3Error as e:
            logger.error(f"Failed to initialize MinIO: {str(e)}")
            raise
    
    def _init_local_storage(self):
        """Initialize local file storage."""
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at: {self.upload_dir}")
    
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
        storage_path = f"{file_id}{extension}"
        
        return file_id, storage_path
    
    async def save_file(
        self,
        file_data: bytes,
        filename: str
    ) -> tuple[str, str]:
        """
        Save file to storage.
        
        Args:
            file_data: File content as bytes
            filename: Original filename
            
        Returns:
            Tuple of (file_id, storage_path)
        """
        file_id, storage_path = self.generate_file_id(filename)
        
        if self.use_minio:
            await self._save_to_minio(file_data, storage_path)
        else:
            await self._save_to_local(file_data, storage_path)
        
        logger.info(f"Saved file: {filename} -> {storage_path}")
        return file_id, storage_path
    
    async def _save_to_minio(self, file_data: bytes, storage_path: str):
        """Save file to MinIO."""
        try:
            from io import BytesIO
            
            self.minio_client.put_object(
                bucket_name=settings.minio_bucket,
                object_name=storage_path,
                data=BytesIO(file_data),
                length=len(file_data),
                content_type="application/pdf"
            )
            
        except S3Error as e:
            logger.error(f"Failed to save file to MinIO: {str(e)}")
            raise
    
    async def _save_to_local(self, file_data: bytes, storage_path: str):
        """Save file to local storage."""
        file_path = self.upload_dir / storage_path
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)
    
    async def get_file(self, storage_path: str) -> bytes:
        """
        Retrieve file from storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            File content as bytes
        """
        if self.use_minio:
            return await self._get_from_minio(storage_path)
        else:
            return await self._get_from_local(storage_path)
    
    async def _get_from_minio(self, storage_path: str) -> bytes:
        """Retrieve file from MinIO."""
        try:
            response = self.minio_client.get_object(
                bucket_name=settings.minio_bucket,
                object_name=storage_path
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data
            
        except S3Error as e:
            logger.error(f"Failed to retrieve file from MinIO: {str(e)}")
            raise
    
    async def _get_from_local(self, storage_path: str) -> bytes:
        """Retrieve file from local storage."""
        file_path = self.upload_dir / storage_path
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")
        
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if deleted successfully
        """
        try:
            if self.use_minio:
                await self._delete_from_minio(storage_path)
            else:
                await self._delete_from_local(storage_path)
            
            logger.info(f"Deleted file: {storage_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return False
    
    async def _delete_from_minio(self, storage_path: str):
        """Delete file from MinIO."""
        self.minio_client.remove_object(
            bucket_name=settings.minio_bucket,
            object_name=storage_path
        )
    
    async def _delete_from_local(self, storage_path: str):
        """Delete file from local storage."""
        file_path = self.upload_dir / storage_path
        
        if file_path.exists():
            os.remove(file_path)
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if file exists in storage.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if file exists
        """
        if self.use_minio:
            try:
                self.minio_client.stat_object(
                    bucket_name=settings.minio_bucket,
                    object_name=storage_path
                )
                return True
            except S3Error:
                return False
        else:
            file_path = self.upload_dir / storage_path
            return file_path.exists()
