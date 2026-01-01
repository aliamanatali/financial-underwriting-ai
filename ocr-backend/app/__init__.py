# Load environment variables from .env file before anything else
import os
from dotenv import load_dotenv

# Construct the path to the .env file relative to this file
# This makes the .env file loading more robust
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

"""OCR Backend - FastAPI application for document extraction using Google Gemini."""

__version__ = "1.0.0"
