import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    OCR_BACKEND_URL: str = os.getenv("OCR_BACKEND_URL", "http://localhost:8001")
    OCR_BACKEND_URL: str = os.getenv("OCR_BACKEND_URL", "http://localhost:8001")

settings = Settings()