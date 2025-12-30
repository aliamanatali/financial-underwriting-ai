from fastapi import Depends
from app.services.gemini_client import GeminiClient
from app.services.normalization_service import NormalizationService
from app.services.financial_service import FinancialService
from app.services.excel_service import ExcelService

def get_gemini_service():
    return GeminiClient()

def get_normalization_service(llm_service: GeminiClient = Depends(get_gemini_service)):
    return NormalizationService(llm_service=llm_service)

def get_financial_service():
    return FinancialService()

def get_excel_service():
    return ExcelService()