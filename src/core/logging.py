"""
Structured logging configuration with JSON output, correlation IDs, and metrics.
Production-ready logging with proper formatting and rotation.
"""

import json
import logging
import logging.handlers
import sys
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import filter_by_level

from .config import get_logging_settings

# Context variable for correlation ID tracking
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIDProcessor:
    """Add correlation ID to log records"""
    
    def __call__(self, logger, method_name, event_dict):
        correlation = correlation_id.get("")
        if correlation:
            event_dict["correlation_id"] = correlation
        return event_dict


class TimestampProcessor:
    """Add ISO timestamp to log records"""
    
    def __call__(self, logger, method_name, event_dict):
        event_dict["timestamp"] = time.time()
        event_dict["iso_timestamp"] = structlog.dev.isoformat(time.time())
        return event_dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": record.created,
            "iso_timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add correlation ID if available
        correlation = correlation_id.get("")
        if correlation:
            log_data["correlation_id"] = correlation
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "message", "exc_info", "exc_text",
                "stack_info"
            }:
                log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """Configure structured logging with JSON output and file rotation"""
    
    settings = get_logging_settings()
    
    # Configure structlog
    structlog.configure(
        processors=[
            filter_by_level,
            CorrelationIDProcessor(),
            TimestampProcessor(),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )
    
    # Setup file handler with rotation
    if settings.log_file_path:
        # Ensure log directory exists
        settings.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            filename=settings.log_file_path,
            maxBytes=settings.log_max_size_mb * 1024 * 1024,
            backupCount=settings.log_backup_count,
            encoding="utf-8"
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(getattr(logging, settings.log_level))
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set correlation ID for request tracking"""
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> str:
    """Get current correlation ID"""
    return correlation_id.get("")


class LoggerMixin:
    """Mixin class to add structured logging to any class"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = get_logger(self.__class__.__name__)
    
    def log_debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        self._logger.debug(message, **kwargs)
    
    def log_info(self, message: str, **kwargs) -> None:
        """Log info message"""
        self._logger.info(message, **kwargs)
    
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        self._logger.warning(message, **kwargs)
    
    def log_error(self, message: str, **kwargs) -> None:
        """Log error message"""
        self._logger.error(message, **kwargs)
    
    def log_critical(self, message: str, **kwargs) -> None:
        """Log critical message"""
        self._logger.critical(message, **kwargs)
    
    def log_exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback"""
        self._logger.exception(message, **kwargs)


def log_function_call(func):
    """Decorator to log function calls with parameters and execution time"""
    
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        func_name = f"{func.__module__}.{func.__name__}"
        
        # Log function entry
        logger.debug(
            "Function called",
            function=func_name,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys())
        )
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Log successful completion
            logger.debug(
                "Function completed",
                function=func_name,
                execution_time=execution_time,
                success=True
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Log exception
            logger.error(
                "Function failed",
                function=func_name,
                execution_time=execution_time,
                error=str(e),
                error_type=type(e).__name__,
                success=False
            )
            raise
    
    return wrapper


class RequestLogger:
    """Middleware-compatible request logger"""
    
    def __init__(self):
        self.logger = get_logger("request")
    
    async def log_request(self, request, call_next):
        """Log HTTP request and response"""
        correlation = set_correlation_id()
        start_time = time.time()
        
        # Log request
        self.logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation
        )
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Log response
            self.logger.info(
                "Request completed",
                status_code=response.status_code,
                duration=duration,
                correlation_id=correlation
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            self.logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                duration=duration,
                correlation_id=correlation
            )
            raise


# Application metrics for monitoring
class MetricsCollector:
    """Collect application metrics for monitoring"""
    
    def __init__(self):
        self.logger = get_logger("metrics")
        self._metrics = {}
    
    def increment(self, metric_name: str, value: int = 1, **labels) -> None:
        """Increment a counter metric"""
        self.logger.info(
            "Metric incremented",
            metric=metric_name,
            value=value,
            labels=labels,
            metric_type="counter"
        )
    
    def gauge(self, metric_name: str, value: float, **labels) -> None:
        """Set a gauge metric"""
        self.logger.info(
            "Metric set",
            metric=metric_name,
            value=value,
            labels=labels,
            metric_type="gauge"
        )
    
    def histogram(self, metric_name: str, value: float, **labels) -> None:
        """Record a histogram metric"""
        self.logger.info(
            "Metric recorded",
            metric=metric_name,
            value=value,
            labels=labels,
            metric_type="histogram"
        )


# Global metrics collector
metrics = MetricsCollector()