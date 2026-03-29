"""
Logging configuration and utilities.
"""

import logging
import sys
from typing import Optional

from .config import Config


def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (defaults to Config.LOG_LEVEL)
    
    Returns:
        Configured logger instance
    """
    if level is None:
        level = Config.LOG_LEVEL
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level))
    
    # Formatter
    formatter = logging.Formatter(Config.LOG_FORMAT)
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger
