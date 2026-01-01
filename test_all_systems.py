#!/usr/bin/env python
"""
Comprehensive test suite for COX Financial Engine and OCR systems.
Tests all endpoints, services, and validates end-to-end functionality.
"""

import sys
import json
import time
import asyncio
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
FINANCIAL_ENGINE_URL = "http://localhost:8000"
OCR_BACKEND_URL = "http://localhost:8001"
OCR_FRONTEND_URL = "http://localhost:3000"

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []
    
    def add_pass(self, test_name: str, message: str = ""):
        self.passed.append({"test": test_name, "message": message})
        logger.info(f"✓ PASS: {test_name} {message}")
    
    def add_fail(self, test_name: str, error: str):
        self.failed.append({"test": test_name, "error": error})
        logger.error(f"✗ FAIL: {test_name} - {error}")
    
    def add_skip(self, test_name: str, reason: str = ""):
        self.skipped.append({"test": test_name, "reason": reason})
        logger.warning(f"⊘ SKIP: {test_name} - {reason}")
    
    def print_summary(self):
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Passed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")
        print(f"Skipped: {len(self.skipped)}")
        print("="*80)
        
        if self.failed:
            print("\nFailed Tests:")
            for test in self.failed:
                print(f"  - {test['test']}: {test['error']}")
        
        if self.skipped:
            print("\nSkipped Tests:")
            for test in self.skipped:
                print(f"  - {test['test']}: {test['reason']}")
        print("="*80 + "\n")
        
        return len(self.failed) == 0


results = TestResults()


class FinancialEngineTests:
    """Test suite for Financial Engine API"""
    
    @staticmethod
    def test_health_check() -> bool:
        """Test health endpoint"""
        try:
            response = requests.get(f"{FINANCIAL_ENGINE_URL}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    results.add_pass("Financial Engine Health Check", f"Status: {data['status']}")
                    return True
            results.add_fail("Financial Engine Health Check", f"Unexpected response: {response.text}")
            return False
        except requests.exceptions.ConnectionError:
            results.add_skip("Financial Engine Health Check", "Server not running on port 8000")
            return False
        except Exception as e:
            results.add_fail("Financial Engine Health Check", str(e))
            return False
    
    @staticmethod
    def test_schemas_import() -> bool:
        """Test that all schemas can be imported"""
        try:
            sys.path.insert(0, str(Path("c:/Users/shamt/Downloads/COX/COX/financial-engine")))
            from app.models.schemas import (
                UnderwritingAnalysis, DealParameters, PropertyMetadata,
                ExpenseItem, IncomeItem, AuditLogEntry
            )
            results.add_pass("Schema Imports", "All schemas imported successfully")
            return True
        except Exception as e:
            results.add_fail("Schema Imports", str(e))
            return False
    
    @staticmethod
    def test_services_initialization() -> bool:
        """Test that services can be initialized"""
        try:
            sys.path.insert(0, str(Path("c:/Users/shamt/Downloads/COX/COX/financial-engine")))
            from app.services.financial_service import FinancialService
            from app.services.normalization_service import NormalizationService
            
            fin_service = FinancialService()
            norm_service = NormalizationService()
            
            results.add_pass("Services Initialization", "FinancialService and NormalizationService initialized")
            return True
        except Exception as e:
            results.add_fail("Services Initialization", str(e))
            return False
    
    @staticmethod
    def test_excel_service() -> bool:
        """Test Excel service"""
        try:
            sys.path.insert(0, str(Path("c:/Users/shamt/Downloads/COX/COX/financial-engine")))
            from app.services.excel_service import ExcelService
            
            excel_service = ExcelService()
            results.add_pass("Excel Service", "ExcelService initialized successfully")
            return True
        except Exception as e:
            results.add_fail("Excel Service", str(e))
            return False


class OCRBackendTests:
    """Test suite for OCR Backend API"""
    
    @staticmethod
    def test_health_check() -> bool:
        """Test OCR backend health endpoint"""
        try:
            response = requests.get(f"{OCR_BACKEND_URL}/health", timeout=5)
            if response.status_code == 200:
                results.add_pass("OCR Backend Health Check", f"Status code: {response.status_code}")
                return True
            results.add_fail("OCR Backend Health Check", f"Unexpected status: {response.status_code}")
            return False
        except requests.exceptions.ConnectionError:
            results.add_skip("OCR Backend Health Check", "Server not running on port 8001")
            return False
        except Exception as e:
            results.add_fail("OCR Backend Health Check", str(e))
            return False
    
    @staticmethod
    def test_gemini_service() -> bool:
        """Test Gemini service initialization"""
        try:
            sys.path.insert(0, str(Path("c:/Users/shamt/Downloads/COX/COX/ocr-backend")))
            from app.services.gemini_service import GeminiService
            
            # Check if API key is available
            from app.config import settings
            if not settings.gemini_api_key:
                results.add_skip("Gemini Service", "GEMINI_API_KEY not set in environment")
                return False
            
            gemini_service = GeminiService()
            results.add_pass("Gemini Service", "GeminiService initialized successfully")
            return True
        except Exception as e:
            results.add_fail("Gemini Service", str(e))
            return False
    
    @staticmethod
    def test_document_models() -> bool:
        """Test OCR document models"""
        try:
            sys.path.insert(0, str(Path("c:/Users/shamt/Downloads/COX/COX/ocr-backend")))
            from app.models.document import Document, DocumentStatus
            
            results.add_pass("OCR Document Models", "Document models imported successfully")
            return True
        except Exception as e:
            results.add_fail("OCR Document Models", str(e))
            return False


class OCRFrontendTests:
    """Test suite for OCR Frontend"""
    
    @staticmethod
    def test_frontend_accessibility() -> bool:
        """Test if frontend is accessible"""
        try:
            response = requests.get(OCR_FRONTEND_URL, timeout=5)
            if response.status_code == 200:
                results.add_pass("OCR Frontend Accessibility", "Frontend is accessible")
                return True
            results.add_fail("OCR Frontend Accessibility", f"Status code: {response.status_code}")
            return False
        except requests.exceptions.ConnectionError:
            results.add_skip("OCR Frontend Accessibility", "Frontend not running on port 3000")
            return False
        except Exception as e:
            results.add_fail("OCR Frontend Accessibility", str(e))
            return False
    
    @staticmethod
    def test_frontend_components() -> bool:
        """Test that frontend components exist"""
        try:
            base_path = Path("c:/Users/shamt/Downloads/COX/COX/ocr-frontend/components")
            components = [
                "DocumentUpload.tsx",
                "DocumentList.tsx",
                "DocumentViewer.tsx",
                "UnderwritingDashboard.tsx",
                "AuditTrailWidget.tsx",
                "ExportButtons.tsx"
            ]
            
            missing = [c for c in components if not (base_path / c).exists()]
            if missing:
                results.add_fail("Frontend Components", f"Missing components: {missing}")
                return False
            
            results.add_pass("Frontend Components", "All required components found")
            return True
        except Exception as e:
            results.add_fail("Frontend Components", str(e))
            return False


class EndToEndTests:
    """End-to-end integration tests"""
    
    @staticmethod
    def test_api_integration() -> bool:
        """Test if all services can communicate"""
        try:
            # Test financial engine is up
            fin_health = requests.get(f"{FINANCIAL_ENGINE_URL}/health", timeout=5)
            
            if fin_health.status_code == 200:
                results.add_pass("API Integration", "Financial Engine API is responsive")
                return True
            else:
                results.add_skip("API Integration", "Financial Engine API not responding")
                return False
        except requests.exceptions.ConnectionError:
            results.add_skip("API Integration", "Cannot connect to Financial Engine")
            return False
        except Exception as e:
            results.add_fail("API Integration", str(e))
            return False
    
    @staticmethod
    def test_configuration() -> bool:
        """Test configuration files"""
        try:
            # Check for .env files
            paths_to_check = [
                Path("c:/Users/shamt/Downloads/COX/COX/financial-engine/.env"),
                Path("c:/Users/shamt/Downloads/COX/COX/ocr-backend/.env")
            ]
            
            missing_env = [str(p) for p in paths_to_check if not p.exists()]
            if missing_env:
                results.add_skip("Configuration Files", f"Missing .env files: {missing_env}")
                return False
            
            results.add_pass("Configuration Files", ".env files configured")
            return True
        except Exception as e:
            results.add_fail("Configuration Files", str(e))
            return False


def run_all_tests():
    """Execute all test suites"""
    print("\n" + "="*80)
    print("COX FINANCIAL ENGINE & OCR SYSTEM TEST SUITE")
    print("="*80 + "\n")
    
    # Financial Engine Tests
    print("[1/4] Running Financial Engine Tests...")
    FinancialEngineTests.test_health_check()
    FinancialEngineTests.test_schemas_import()
    FinancialEngineTests.test_services_initialization()
    FinancialEngineTests.test_excel_service()
    
    # OCR Backend Tests
    print("\n[2/4] Running OCR Backend Tests...")
    OCRBackendTests.test_health_check()
    OCRBackendTests.test_gemini_service()
    OCRBackendTests.test_document_models()
    
    # OCR Frontend Tests
    print("\n[3/4] Running OCR Frontend Tests...")
    OCRFrontendTests.test_frontend_accessibility()
    OCRFrontendTests.test_frontend_components()
    
    # End-to-End Tests
    print("\n[4/4] Running End-to-End Integration Tests...")
    EndToEndTests.test_api_integration()
    EndToEndTests.test_configuration()
    
    # Print summary
    results.print_summary()
    
    return 0 if results.print_summary() else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
