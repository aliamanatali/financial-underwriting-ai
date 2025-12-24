"""Configuration management using pydantic-settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Gemini API Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-3-pro-preview"
    gemini_embedding_model: str = "text-embedding-004"
    gemini_temperature: float = 0.0
    gemini_max_output_tokens: int = 65536
    gemini_timeout_seconds: int = 120
    gemini_max_retries: int = 3
    
    # PDF Chunking Configuration
    chunk_size_pages: int = 1
    large_file_threshold_mb: float = 5.0
    large_file_page_threshold: int = 1
    
    # MongoDB Configuration (Optional)
    mongodb_uri: Optional[str] = None
    mongodb_database: str = "ocr_db"
    
    # MinIO Configuration (Optional)
    minio_endpoint: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_bucket: str = "documents"
    minio_use_ssl: bool = False
    
    # Local Storage Configuration
    upload_dir: str = "./uploads"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_worker_concurrency: int = 4
    celery_task_time_limit: int = 3600  # 1 hour
    celery_task_soft_time_limit: int = 3300  # 55 minutes
    celery_worker_prefetch_multiplier: int = 4
    celery_worker_max_tasks_per_child: int = 1000
    
    # Server Configuration
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False
    
    # CORS Configuration
    cors_origins: list[str] = ["*"]
    
    # Logging
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def use_mongodb(self) -> bool:
        """Check if MongoDB is configured."""
        return self.mongodb_uri is not None
    
    @property
    def use_minio(self) -> bool:
        """Check if MinIO is configured."""
        return all([
            self.minio_endpoint,
            self.minio_access_key,
            self.minio_secret_key
        ])


# Global settings instance
settings = Settings()
