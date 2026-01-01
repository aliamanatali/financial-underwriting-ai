from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# 👇 ABSOLUTE path to project root .env
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str
    gemini_embedding_model: str
    gemini_temperature: float = 0.0
    gemini_max_output_tokens: int = 8192
    gemini_timeout_seconds: int = 1800
    gemini_max_retries: int = 5

    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    celery_task_time_limit: int = 3600
    celery_task_soft_time_limit: int = 3300
    celery_worker_prefetch_multiplier: int = 4
    celery_worker_max_tasks_per_child: int = 1000

    log_level: str = "INFO"

    # Server settings
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # PDF processing settings
    chunk_size_pages: int = 15
    large_file_page_threshold: int = 100
    large_file_threshold_mb: int = 10

    # Storage settings
    upload_dir: str = "./uploads"
    minio_endpoint: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_bucket: str = "documents"
    minio_use_ssl: bool = False

    # Database settings
    mongodb_uri: Optional[str] = None
    mongodb_database: Optional[str] = None

    @property
    def use_minio(self) -> bool:
        return all([self.minio_endpoint, self.minio_access_key, self.minio_secret_key])

    @property
    def use_mongodb(self) -> bool:
        return self.mongodb_uri is not None

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()
