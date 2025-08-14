"""
Configuration management with environment variable support and validation.
Uses Pydantic Settings for type safety and validation.
"""

import os
from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseSettings, Field, validator
from pydantic.networks import AnyHttpUrl


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    
    # PostgreSQL Configuration
    postgres_host: str = Field("localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(5433, env="POSTGRES_PORT")
    postgres_db: str = Field("wms_chatbot", env="POSTGRES_DB")
    postgres_user: str = Field("wms_user", env="POSTGRES_USER")
    postgres_password: str = Field(..., env="POSTGRES_PASSWORD")
    
    # Vector Database Configuration
    weaviate_url: AnyHttpUrl = Field("http://localhost:5002", env="WEAVIATE_URL")
    weaviate_api_key: Optional[str] = Field(None, env="WEAVIATE_API_KEY")
    
    @property
    def postgres_url(self) -> str:
        """Generate PostgreSQL connection URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def postgres_sync_url(self) -> str:
        """Generate synchronous PostgreSQL connection URL for migrations"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration settings"""
    
    endpoint: AnyHttpUrl = Field(..., env="AZURE_OPENAI_ENDPOINT")
    api_key: str = Field(..., env="AZURE_OPENAI_API_KEY")
    api_version: str = Field("2024-02-15-preview", env="AZURE_OPENAI_API_VERSION")
    deployment_chat: str = Field("azure-gpt-4o", env="AZURE_OPENAI_DEPLOYMENT_CHAT")
    deployment_embeddings: str = Field("text-embedding-ada-002", env="AZURE_OPENAI_DEPLOYMENT_EMBEDDINGS")
    model_name: str = Field("gpt-4o", env="AZURE_OPENAI_MODEL_NAME")
    
    @validator("api_key")
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Azure OpenAI API key is required and must be valid")
        return v


class SecuritySettings(BaseSettings):
    """Security and authentication settings"""
    
    secret_key: str = Field(..., env="APP_SECRET_KEY")
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(24, env="JWT_EXPIRATION_HOURS")
    
    @validator("secret_key", "jwt_secret_key")
    def validate_secrets(cls, v):
        if not v or len(v) < 32:
            raise ValueError("Secret keys must be at least 32 characters long")
        return v


class ProcessingSettings(BaseSettings):
    """File and data processing settings"""
    
    max_file_size_mb: int = Field(50, env="MAX_FILE_SIZE_MB")
    supported_file_formats: str = Field(
        "txt,doc,docx,pdf,md,xlsx,xls,csv,png,jpg,jpeg,gif,bmp,tiff,html,htm,mp3,wav,mp4,avi,mov",
        env="SUPPORTED_FILE_FORMATS"
    )
    temp_directory: Path = Field(Path("temp"), env="TEMP_DIRECTORY")
    output_directory: Path = Field(Path("output"), env="OUTPUT_DIRECTORY")
    
    # OCR Configuration
    tesseract_path: Optional[str] = Field(None, env="TESSERACT_PATH")
    ocr_confidence_threshold: int = Field(30, env="OCR_CONFIDENCE_THRESHOLD")
    
    @property
    def supported_formats_list(self) -> List[str]:
        """Get supported file formats as a list"""
        return [fmt.strip() for fmt in self.supported_file_formats.split(",")]
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes"""
        return self.max_file_size_mb * 1024 * 1024
    
    @validator("temp_directory", "output_directory")
    def create_directories(cls, v):
        """Ensure directories exist"""
        v.mkdir(parents=True, exist_ok=True)
        return v


class AgentSettings(BaseSettings):
    """Agent and LLM configuration settings"""
    
    llm_temperature: float = Field(0.0, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(4000, env="LLM_MAX_TOKENS")
    categorization_confidence_threshold: float = Field(0.7, env="CATEGORIZATION_CONFIDENCE_THRESHOLD")
    manual_review_threshold: float = Field(0.8, env="MANUAL_REVIEW_THRESHOLD")
    
    @validator("llm_temperature")
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError("LLM temperature must be between 0.0 and 2.0")
        return v
    
    @validator("categorization_confidence_threshold", "manual_review_threshold")
    def validate_thresholds(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence thresholds must be between 0.0 and 1.0")
        return v


class APISettings(BaseSettings):
    """API server configuration settings"""
    
    host: str = Field("0.0.0.0", env="API_HOST")
    port: int = Field(5000, env="API_PORT")
    workers: int = Field(4, env="API_WORKERS")
    timeout: int = Field(300, env="API_TIMEOUT")
    cors_origins: List[str] = Field(["*"], env="CORS_ORIGINS")
    
    @validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class LoggingSettings(BaseSettings):
    """Logging and monitoring configuration"""
    
    log_level: str = Field("INFO", env="APP_LOG_LEVEL")
    log_file_path: Path = Field(Path("logs/wms_chatbot.log"), env="LOG_FILE_PATH")
    log_max_size_mb: int = Field(10, env="LOG_MAX_SIZE_MB")
    log_backup_count: int = Field(5, env="LOG_BACKUP_COUNT")
    enable_metrics: bool = Field(True, env="ENABLE_METRICS")
    metrics_port: int = Field(9090, env="METRICS_PORT")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @validator("log_file_path")
    def create_log_directory(cls, v):
        """Ensure log directory exists"""
        v.parent.mkdir(parents=True, exist_ok=True)
        return v


class AppSettings(BaseSettings):
    """Main application settings that combines all configuration sections"""
    
    # Application metadata
    name: str = Field("WMS Chatbot System", env="APP_NAME")
    version: str = Field("1.0.0", env="APP_VERSION")
    debug: bool = Field(False, env="APP_DEBUG")
    
    # Configuration sections
    database: DatabaseSettings = DatabaseSettings()
    azure_openai: AzureOpenAISettings = AzureOpenAISettings()
    security: SecuritySettings = SecuritySettings()
    processing: ProcessingSettings = ProcessingSettings()
    agents: AgentSettings = AgentSettings()
    api: APISettings = APISettings()
    logging: LoggingSettings = LoggingSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("debug")
    def validate_debug_mode(cls, v, values):
        """Warn about debug mode in production"""
        if v and not values.get("name", "").endswith("Development"):
            import warnings
            warnings.warn(
                "Debug mode is enabled! This should not be used in production.",
                UserWarning
            )
        return v


# Global settings instance
def get_settings() -> AppSettings:
    """Get application settings with caching"""
    if not hasattr(get_settings, "_settings"):
        get_settings._settings = AppSettings()
    return get_settings._settings


# Convenience function for accessing specific setting sections
def get_database_settings() -> DatabaseSettings:
    """Get database settings"""
    return get_settings().database


def get_azure_openai_settings() -> AzureOpenAISettings:
    """Get Azure OpenAI settings"""
    return get_settings().azure_openai


def get_security_settings() -> SecuritySettings:
    """Get security settings"""
    return get_settings().security


def get_processing_settings() -> ProcessingSettings:
    """Get processing settings"""
    return get_settings().processing


def get_agent_settings() -> AgentSettings:
    """Get agent settings"""
    return get_settings().agents


def get_api_settings() -> APISettings:
    """Get API settings"""
    return get_settings().api


def get_logging_settings() -> LoggingSettings:
    """Get logging settings"""
    return get_settings().logging