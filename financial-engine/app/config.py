from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)


class Settings(BaseSettings):
    # Gemini API settings
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-pro"
    gemini_fast_model: str = "gemini-3-flash-preview"
    gemini_temperature: float = 0.0
    gemini_max_output_tokens: int = 8192
    
    # OpenAI API settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    # Server settings
    port: int = 8001
    host: str = "0.0.0.0"
    debug: bool = False
    cors_origins: list[str] = ["*"]
    
    # OCR Backend URL
    ocr_backend_url: str = "http://localhost:8000"
    
    # GCP Cloud Storage settings
    gcp_project_id: Optional[str] = None
    gcp_storage_bucket: Optional[str] = None
    gcp_credentials_path: Optional[str] = None
    
    # GCP Service Account Credentials (environment variables method)
    gcp_type: Optional[str] = None
    gcp_private_key_id: Optional[str] = None
    gcp_private_key: Optional[str] = None
    gcp_client_email: Optional[str] = None
    gcp_client_id: Optional[str] = None
    gcp_auth_uri: Optional[str] = None
    gcp_token_uri: Optional[str] = None
    gcp_auth_provider_x509_cert_url: Optional[str] = None
    gcp_client_x509_cert_url: Optional[str] = None
    # Database settings
    mongodb_uri: Optional[str] = None
    mongodb_database: Optional[str] = None
    
    # Redis settings
    redis_url: str = "redis://localhost:6379/0"

    @property
    def use_mongodb(self) -> bool:
        return self.mongodb_uri is not None
    gcp_universe_domain: Optional[str] = None
    
    @property
    def use_gcp(self) -> bool:
        """Check if GCP Cloud Storage is configured."""
        # Method 1: Environment variables (recommended for production)
        has_env_credentials = all([
            self.gcp_project_id,
            self.gcp_storage_bucket,
            self.gcp_type,
            self.gcp_private_key,
            self.gcp_client_email
        ])
        
        # Method 2: Credentials file (legacy support)
        has_file_credentials = all([
            self.gcp_project_id,
            self.gcp_storage_bucket,
            self.gcp_credentials_path
        ])
        
        return has_env_credentials or has_file_credentials
    
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()
