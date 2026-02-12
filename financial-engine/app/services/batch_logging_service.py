import csv
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class BatchLoggingService:
    """
    Service to log batch processing events to CSV files for auditing and debugging.
    Tracks classification, normalization, and errors.
    """

    def __init__(self, log_dir: str = "batch_logs"):
        self.log_dir = log_dir
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._ensure_log_dir()
        
        # Define file paths
        self.classification_log_file = os.path.join(self.log_dir, f"classification_{self.session_id}.csv")
        self.normalization_log_file = os.path.join(self.log_dir, f"normalization_{self.session_id}.csv")
        self.error_log_file = os.path.join(self.log_dir, f"errors_{self.session_id}.csv")
        
        # Initialize headers
        self._init_csv(self.classification_log_file, ["timestamp", "filename", "predicted_category", "confidence", "status"])
        self._init_csv(self.normalization_log_file, ["timestamp", "document_id", "filename", "raw_text", "amount", "normalized_value", "category_group", "confidence", "source_document"])
        self._init_csv(self.error_log_file, ["timestamp", "filename", "operation", "error_message", "details"])

    def _ensure_log_dir(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def _init_csv(self, filepath: str, headers: List[str]):
        if not os.path.exists(filepath):
            try:
                with open(filepath, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
            except Exception as e:
                logger.error(f"Failed to initialize log file {filepath}: {e}")

    def log_classification(self, filename: str, category: str, confidence: float = 1.0, status: str = "success"):
        """Log a file classification result."""
        try:
            with open(self.classification_log_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    filename,
                    category,
                    confidence,
                    status
                ])
        except Exception as e:
            logger.error(f"Failed to log classification: {e}")

    def log_normalization(self, document_id: str, filename: str, raw_text: str, amount: float, normalized_value: str, category_group: str, confidence: float, source_document: str):
        """Log a normalization result."""
        try:
            with open(self.normalization_log_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    document_id,
                    filename,
                    raw_text,
                    amount,
                    normalized_value,
                    category_group,
                    confidence,
                    source_document
                ])
        except Exception as e:
            logger.error(f"Failed to log normalization: {e}")

    def log_error(self, filename: str, operation: str, error_message: str, details: str = ""):
        """Log an error during batch processing."""
        try:
            with open(self.error_log_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    filename,
                    operation,
                    error_message,
                    details
                ])
        except Exception as e:
            logger.error(f"Failed to log error: {e}")