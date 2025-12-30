from fastapi import Depends
from app.services.gemini_client import GeminiClient
from app.services.normalization_service import NormalizationService
from app.services.financial_service import FinancialService
from app.services.excel_service import ExcelService
from app.services.memo_service import MemoService
from app.services.audit_log_service import AuditLogService
from app.services.ingestion_service import IngestionService

def get_gemini_service():
    return GeminiClient()

def get_normalization_service(llm_service: GeminiClient = Depends(get_gemini_service)):
    return NormalizationService(llm_service=llm_service)

def get_financial_service():
    return FinancialService()

def get_excel_service():
    return ExcelService()

def get_memo_service(gemini_service: GeminiClient = Depends(get_gemini_service)):
    return MemoService(gemini_service=gemini_service)

def get_audit_log_service():
    return AuditLogService()

def get_ingestion_service():
    return IngestionService()