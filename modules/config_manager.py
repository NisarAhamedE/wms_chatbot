import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class ConfigManager:
    """
    Manages application configuration and settings
    """
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.env_file = Path(".env")
        
        # Load environment variables
        if self.env_file.exists():
            load_dotenv(self.env_file)
        
        # Default configuration
        self.default_config = {
            "database": {
                "sqlite_path": "data/wms_screenshots.db",
                "chroma_path": "data/chroma_db",
                "backup_enabled": True,
                "backup_interval": 24  # hours
            },
            "azure_openai": {
                "api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
                "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", ""),
                "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            },
            "file_processing": {
                "max_file_size": 50 * 1024 * 1024,  # 50MB
                "supported_formats": [
                    ".txt", ".doc", ".docx", ".pdf", ".md", ".rtf",
                    ".xlsx", ".xls", ".csv",
                    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff",
                    ".ppt", ".pptx",
                    ".html", ".htm"
                ],
                "temp_dir": "temp",
                "output_dir": "output"
            },
            "ui": {
                "theme": "clam",
                "window_size": "1200x800",
                "min_window_size": "1000x600",
                "auto_save_interval": 30  # seconds
            },
            "chatbot": {
                "model_name": "gpt-4-vision-preview",
                "max_tokens": 4000,
                "temperature": 0.7,
                "context_window": 10,
                "enable_voice": True,
                "enable_image_input": True
            },
            "logging": {
                "level": "INFO",
                "file": "logs/app.log",
                "max_size": 10 * 1024 * 1024,  # 10MB
                "backup_count": 5
            }
        }
        
        # Load configuration
        self.config = self.load_config()
        
        # Create necessary directories
        self.create_directories()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                # Merge with defaults for any missing keys
                return self.merge_configs(self.default_config, config)
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.default_config.copy()
        else:
            # Create default config file
            self.save_config(self.default_config)
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Merge user config with defaults"""
        result = default.copy()
        
        def merge_dicts(d1: Dict[str, Any], d2: Dict[str, Any]) -> None:
            for key, value in d2.items():
                if key in d1 and isinstance(d1[key], dict) and isinstance(value, dict):
                    merge_dicts(d1[key], value)
                else:
                    d1[key] = value
        
        merge_dicts(result, user)
        return result
    
    def create_directories(self) -> None:
        """Create necessary directories"""
        directories = [
            Path(self.config["database"]["sqlite_path"]).parent,
            Path(self.config["database"]["chroma_path"]).parent,
            Path(self.config["file_processing"]["temp_dir"]),
            Path(self.config["file_processing"]["output_dir"]),
            Path(self.config["logging"]["file"]).parent
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value by key (supports dot notation)"""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        
        # Save to file
        self.save_config(self.config)
    
    def get_azure_config(self) -> Dict[str, str]:
        """Get Azure OpenAI configuration"""
        return {
            "api_key": self.get("azure_openai.api_key"),
            "endpoint": self.get("azure_openai.endpoint"),
            "deployment_name": self.get("azure_openai.deployment_name"),
            "api_version": self.get("azure_openai.api_version")
        }
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.get("database")
    
    def get_file_processing_config(self) -> Dict[str, Any]:
        """Get file processing configuration"""
        return self.get("file_processing")
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Get UI configuration"""
        return self.get("ui")
    
    def get_chatbot_config(self) -> Dict[str, Any]:
        """Get chatbot configuration"""
        return self.get("chatbot")
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.get("logging")
    
    def is_azure_configured(self) -> bool:
        """Check if Azure OpenAI is properly configured"""
        azure_config = self.get_azure_config()
        return all([
            azure_config["api_key"],
            azure_config["endpoint"],
            azure_config["deployment_name"]
        ])
    
    def validate_config(self) -> Dict[str, str]:
        """Validate configuration and return any errors"""
        errors = {}
        
        # Check Azure configuration
        if not self.is_azure_configured():
            errors["azure"] = "Azure OpenAI not properly configured"
        
        # Check file paths
        file_config = self.get_file_processing_config()
        for path_key in ["temp_dir", "output_dir"]:
            path = Path(file_config[path_key])
            if not path.parent.exists():
                errors[f"file_processing.{path_key}"] = f"Directory does not exist: {path.parent}"
        
        return errors 