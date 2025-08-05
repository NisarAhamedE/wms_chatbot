import logging
import logging.handlers
from pathlib import Path
from typing import Optional

def setup_logger(
    name: str = "wms_screenshot_app",
    log_file: str = "logs/app.log",
    level: str = "INFO",
    max_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup application logger with file and console handlers
    
    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level
        max_size: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
    
    Returns:
        Configured logger instance
    """
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create file handler with rotation
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_logger(name: str = "wms_screenshot_app") -> logging.Logger:
    """
    Get existing logger instance
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

class LoggerMixin:
    """
    Mixin class to add logging capabilities to other classes
    """
    
    def __init__(self, logger_name: Optional[str] = None):
        if logger_name:
            self.logger = get_logger(logger_name)
        else:
            self.logger = get_logger(self.__class__.__name__)
    
    def log_info(self, message: str) -> None:
        """Log info message"""
        self.logger.info(message)
    
    def log_error(self, message: str, exc_info: bool = True) -> None:
        """Log error message"""
        self.logger.error(message, exc_info=exc_info)
    
    def log_warning(self, message: str) -> None:
        """Log warning message"""
        self.logger.warning(message)
    
    def log_debug(self, message: str) -> None:
        """Log debug message"""
        self.logger.debug(message)
    
    def log_critical(self, message: str, exc_info: bool = True) -> None:
        """Log critical message"""
        self.logger.critical(message, exc_info=exc_info) 