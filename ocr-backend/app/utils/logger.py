"""Logging configuration for the application."""

import logging
import sys
from typing import Optional

from app.config import settings


def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a logger instance.
    
    Args:
        name: Logger name (defaults to root logger)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper()))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, settings.log_level.upper()))
        
        # Formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger


# Global logger instance
logger = setup_logger("ocr-backend")
