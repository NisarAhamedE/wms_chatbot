#!/usr/bin/env python3
"""
WMS Chatbot Environment Setup Script
Automated setup and configuration for WMS Chatbot deployment
"""

import os
import sys
import json
import subprocess
import urllib.request
import getpass
from pathlib import Path
from typing import Dict, Any, List
import argparse

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def log_info(message: str):
    """Log info message"""
    print(f"{Colors.BLUE}[INFO]{Colors.END} {message}")

def log_success(message: str):
    """Log success message"""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.END} {message}")

def log_warning(message: str):
    """Log warning message"""
    print(f"{Colors.YELLOW}[WARNING]{Colors.END} {message}")

def log_error(message: str):
    """Log error message"""
    print(f"{Colors.RED}[ERROR]{Colors.END} {message}")

def log_header(message: str):
    """Log header message"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{message}{Colors.END}")
    print("=" * len(message))

class WMSSetup:
    """WMS Chatbot setup and configuration"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.env_file = self.project_root / ".env"
        self.env_example = self.project_root / ".env.example"
        self.requirements_file = self.project_root / "requirements.txt"
        
    def check_system_requirements(self) -> bool:
        """Check system requirements"""
        log_header("Checking System Requirements")
        
        requirements_met = True
        
        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 11):
            log_success(f"Python {python_version.major}.{python_version.minor}.{python_version.micro} ✓")
        else:
            log_error(f"Python 3.11+ required, found {python_version.major}.{python_version.minor}")
            requirements_met = False
        
        # Check Docker
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                log_success(f"Docker: {result.stdout.strip()} ✓")
            else:
                raise subprocess.CalledProcessError(result.returncode, 'docker --version')
        except (subprocess.CalledProcessError, FileNotFoundError):
            log_error("Docker is not installed or not accessible")
            requirements_met = False
        
        # Check Docker Compose
        try:
            result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                log_success(f"Docker Compose: {result.stdout.strip()} ✓")
            else:
                raise subprocess.CalledProcessError(result.returncode, 'docker-compose --version')
        except (subprocess.CalledProcessError, FileNotFoundError):
            log_error("Docker Compose is not installed or not accessible")
            requirements_met = False
        
        # Check available disk space
        try:
            disk_usage = os.statvfs(self.project_root)
            free_gb = (disk_usage.f_bavail * disk_usage.f_frsize) / (1024**3)
            if free_gb >= 10:
                log_success(f"Disk space: {free_gb:.1f}GB available ✓")
            else:
                log_warning(f"Low disk space: {free_gb:.1f}GB available (recommended: 10GB+)")
        except:
            log_warning("Could not check disk space")
        
        return requirements_met
    
    def setup_python_environment(self) -> bool:
        """Setup Python virtual environment"""
        log_header("Setting Up Python Environment")
        
        venv_path = self.project_root / "venv"
        
        # Create virtual environment if it doesn't exist
        if not venv_path.exists():
            log_info("Creating Python virtual environment...")
            try:
                subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
                log_success("Virtual environment created")
            except subprocess.CalledProcessError:
                log_error("Failed to create virtual environment")
                return False
        
        # Activate virtual environment and install requirements
        if os.name == 'nt':  # Windows
            pip_path = venv_path / "Scripts" / "pip"
            python_path = venv_path / "Scripts" / "python"
        else:  # Unix/Linux/macOS
            pip_path = venv_path / "bin" / "pip"
            python_path = venv_path / "bin" / "python"
        
        # Upgrade pip
        try:
            log_info("Upgrading pip...")
            subprocess.run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], check=True)
            log_success("Pip upgraded")
        except subprocess.CalledProcessError:
            log_warning("Failed to upgrade pip")
        
        # Install requirements
        if self.requirements_file.exists():
            try:
                log_info("Installing Python dependencies...")
                subprocess.run([str(pip_path), "install", "-r", str(self.requirements_file)], check=True)
                log_success("Python dependencies installed")
            except subprocess.CalledProcessError:
                log_error("Failed to install dependencies")
                return False
        
        # Install spaCy model
        try:
            log_info("Installing spaCy English model...")
            subprocess.run([str(python_path), "-m", "spacy", "download", "en_core_web_sm"], check=True)
            log_success("spaCy model installed")
        except subprocess.CalledProcessError:
            log_warning("Failed to install spaCy model")
        
        return True
    
    def configure_environment(self) -> bool:
        """Configure environment variables"""
        log_header("Configuring Environment")
        
        # Copy .env.example if .env doesn't exist
        if not self.env_file.exists():
            if self.env_example.exists():
                log_info("Creating .env file from template...")
                with open(self.env_example, 'r') as src, open(self.env_file, 'w') as dst:
                    dst.write(src.read())
                log_success(".env file created")
            else:
                log_error(".env.example not found")
                return False
        
        # Interactive configuration
        config = self.load_env_config()
        
        print("\n" + Colors.BOLD + "Environment Configuration" + Colors.END)
        print("Please provide the following configuration values:")
        print("(Press Enter to keep current value)\n")
        
        # Azure OpenAI Configuration
        print(Colors.CYAN + "Azure OpenAI Configuration:" + Colors.END)
        config['AZURE_OPENAI_ENDPOINT'] = self.prompt_with_default(
            "Azure OpenAI Endpoint", 
            config.get('AZURE_OPENAI_ENDPOINT', '')
        )
        
        config['AZURE_OPENAI_API_KEY'] = self.prompt_password(
            "Azure OpenAI API Key",
            config.get('AZURE_OPENAI_API_KEY', '')
        )
        
        config['AZURE_OPENAI_DEPLOYMENT_CHAT'] = self.prompt_with_default(
            "Chat Model Deployment Name",
            config.get('AZURE_OPENAI_DEPLOYMENT_CHAT', 'gpt-4')
        )
        
        config['AZURE_OPENAI_DEPLOYMENT_EMBEDDING'] = self.prompt_with_default(
            "Embedding Model Deployment Name",
            config.get('AZURE_OPENAI_DEPLOYMENT_EMBEDDING', 'text-embedding-ada-002')
        )
        
        # Database Configuration
        print(f"\n{Colors.CYAN}Database Configuration:{Colors.END}")
        config['DATABASE_PASSWORD'] = self.prompt_password(
            "PostgreSQL Password",
            config.get('DATABASE_PASSWORD', 'wms_password_123')
        )
        
        # Security Configuration
        print(f"\n{Colors.CYAN}Security Configuration:{Colors.END}")
        config['JWT_SECRET_KEY'] = self.prompt_password(
            "JWT Secret Key",
            config.get('JWT_SECRET_KEY', self.generate_secret_key())
        )
        
        config['ENCRYPTION_KEY'] = self.prompt_password(
            "Encryption Key",
            config.get('ENCRYPTION_KEY', self.generate_secret_key())
        )
        
        # Save configuration
        self.save_env_config(config)
        log_success("Environment configuration saved")
        
        return True
    
    def load_env_config(self) -> Dict[str, str]:
        """Load current environment configuration"""
        config = {}
        
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key] = value.strip('"\'')
        
        return config
    
    def save_env_config(self, config: Dict[str, str]):
        """Save environment configuration"""
        with open(self.env_file, 'w') as f:
            f.write("# WMS Chatbot Environment Configuration\n")
            f.write("# Generated by setup script\n\n")
            
            # Group configurations
            groups = {
                "Azure OpenAI Configuration": [
                    'AZURE_OPENAI_ENDPOINT',
                    'AZURE_OPENAI_API_KEY',
                    'AZURE_OPENAI_API_VERSION',
                    'AZURE_OPENAI_DEPLOYMENT_CHAT',
                    'AZURE_OPENAI_DEPLOYMENT_EMBEDDING'
                ],
                "Database Configuration": [
                    'DATABASE_HOST',
                    'DATABASE_PORT',
                    'DATABASE_NAME',
                    'DATABASE_USER',
                    'DATABASE_PASSWORD',
                    'DATABASE_SSL_MODE'
                ],
                "Vector Database Configuration": [
                    'WEAVIATE_URL',
                    'WEAVIATE_API_KEY'
                ],
                "Security Configuration": [
                    'JWT_SECRET_KEY',
                    'ENCRYPTION_KEY'
                ],
                "Application Settings": [
                    'LOG_LEVEL',
                    'CORS_ORIGINS',
                    'MAX_QUERY_ROWS',
                    'QUERY_TIMEOUT_SECONDS',
                    'MAX_CONCURRENT_QUERIES'
                ]
            }
            
            # Set defaults
            defaults = {
                'AZURE_OPENAI_API_VERSION': '2023-12-01-preview',
                'DATABASE_HOST': 'postgres',
                'DATABASE_PORT': '5432',
                'DATABASE_NAME': 'wms_chatbot',
                'DATABASE_USER': 'wms_user',
                'DATABASE_SSL_MODE': 'prefer',
                'WEAVIATE_URL': 'http://weaviate:8080',
                'WEAVIATE_API_KEY': '',
                'LOG_LEVEL': 'INFO',
                'CORS_ORIGINS': 'http://localhost:5001,http://localhost:5002',
                'MAX_QUERY_ROWS': '10000',
                'QUERY_TIMEOUT_SECONDS': '300',
                'MAX_CONCURRENT_QUERIES': '3'
            }
            
            # Write grouped configuration
            for group_name, keys in groups.items():
                f.write(f"\n# {group_name}\n")
                for key in keys:
                    value = config.get(key, defaults.get(key, ''))
                    f.write(f"{key}={value}\n")
    
    def prompt_with_default(self, prompt: str, default: str = "") -> str:
        """Prompt user for input with default value"""
        display_default = default[:20] + "..." if len(default) > 20 else default
        user_input = input(f"{prompt} [{display_default}]: ").strip()
        return user_input if user_input else default
    
    def prompt_password(self, prompt: str, default: str = "") -> str:
        """Prompt user for password input"""
        display_default = "*" * min(len(default), 8) if default else ""
        user_input = getpass.getpass(f"{prompt} [{display_default}]: ").strip()
        return user_input if user_input else default
    
    def generate_secret_key(self) -> str:
        """Generate a random secret key"""
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def setup_directories(self) -> bool:
        """Setup required directories"""
        log_header("Setting Up Directory Structure")
        
        directories = [
            "logs",
            "data",
            "uploads",
            "backups",
            "temp",
            "monitoring",
            "nginx",
            "scripts"
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            if not dir_path.exists():
                dir_path.mkdir(parents=True)
                log_success(f"Created directory: {directory}")
            else:
                log_info(f"Directory exists: {directory}")
        
        # Create .gitkeep files for empty directories
        for directory in ["logs", "uploads", "temp", "backups"]:
            gitkeep = self.project_root / directory / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()
        
        return True
    
    def validate_configuration(self) -> bool:
        """Validate the configuration"""
        log_header("Validating Configuration")
        
        config = self.load_env_config()
        validation_passed = True
        
        # Required fields
        required_fields = [
            'AZURE_OPENAI_ENDPOINT',
            'AZURE_OPENAI_API_KEY',
            'DATABASE_PASSWORD',
            'JWT_SECRET_KEY'
        ]
        
        for field in required_fields:
            if not config.get(field):
                log_error(f"Required field missing: {field}")
                validation_passed = False
            else:
                log_success(f"Required field present: {field}")
        
        # Validate Azure OpenAI endpoint format
        endpoint = config.get('AZURE_OPENAI_ENDPOINT', '')
        if endpoint and not endpoint.startswith('https://'):
            log_warning("Azure OpenAI endpoint should start with https://")
        
        # Test Azure OpenAI connection
        if config.get('AZURE_OPENAI_ENDPOINT') and config.get('AZURE_OPENAI_API_KEY'):
            if self.test_azure_openai_connection(config):
                log_success("Azure OpenAI connection test passed")
            else:
                log_warning("Azure OpenAI connection test failed")
                validation_passed = False
        
        return validation_passed
    
    def test_azure_openai_connection(self, config: Dict[str, str]) -> bool:
        """Test Azure OpenAI connection"""
        try:
            import requests
            
            endpoint = config.get('AZURE_OPENAI_ENDPOINT', '').rstrip('/')
            api_key = config.get('AZURE_OPENAI_API_KEY', '')
            api_version = config.get('AZURE_OPENAI_API_VERSION', '2023-12-01-preview')
            
            url = f"{endpoint}/openai/deployments?api-version={api_version}"
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            return response.status_code == 200
        
        except Exception as e:
            log_warning(f"Azure OpenAI connection test failed: {e}")
            return False
    
    def create_docker_override(self):
        """Create docker-compose override for development"""
        log_header("Creating Docker Compose Override")
        
        override_content = """
version: '3.8'

# Development overrides
services:
  wms-chatbot:
    volumes:
      - ./src:/app/src:ro
      - ./logs:/app/logs
    environment:
      - LOG_LEVEL=DEBUG
      - RELOAD=true
    ports:
      - "5000:5000"
      - "5678:5678"  # Debugger port

  postgres:
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=${DATABASE_PASSWORD}

  weaviate:
    ports:
      - "8080:8080"

  grafana:
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin123}
"""
        
        override_file = self.project_root / "docker-compose.override.yml"
        with open(override_file, 'w') as f:
            f.write(override_content.strip())
        
        log_success("Docker Compose override created for development")
    
    def run_initial_setup(self):
        """Run initial setup tasks"""
        log_header("Running Initial Setup")
        
        # Pull Docker images
        log_info("Pulling Docker images...")
        try:
            subprocess.run(['docker-compose', 'pull'], cwd=self.project_root, check=True)
            log_success("Docker images pulled successfully")
        except subprocess.CalledProcessError:
            log_warning("Failed to pull some Docker images")
        
        # Build custom images
        log_info("Building custom Docker images...")
        try:
            subprocess.run(['docker-compose', 'build'], cwd=self.project_root, check=True)
            log_success("Docker images built successfully")
        except subprocess.CalledProcessError:
            log_error("Failed to build Docker images")
            return False
        
        return True
    
    def display_next_steps(self):
        """Display next steps for the user"""
        log_header("Setup Complete!")
        
        print(f"""
{Colors.GREEN}✓ WMS Chatbot setup completed successfully!{Colors.END}

{Colors.BOLD}Next Steps:{Colors.END}

1. {Colors.CYAN}Start the development environment:{Colors.END}
   docker-compose up -d

2. {Colors.CYAN}Access the application:{Colors.END}
   • API: http://localhost:5000
   • Documentation: http://localhost:5000/docs
   • Monitoring: http://localhost:5001

3. {Colors.CYAN}Test the API:{Colors.END}
   curl -X GET "http://localhost:5000/health/"

4. {Colors.CYAN}Connect to your operational database:{Colors.END}
   curl -X POST "http://localhost:5000/api/v1/operational-db/connect" \\
     -H "Authorization: Bearer admin_token" \\
     -d '{{"server": "your-server", "database": "your-db", ...}}'

5. {Colors.CYAN}Deploy to production:{Colors.END}
   ./scripts/deploy.sh production --build

{Colors.BOLD}Useful Commands:{Colors.END}
• View logs: docker-compose logs -f
• Stop services: docker-compose down
• Run tests: pytest tests/ -v

{Colors.BOLD}Configuration:{Colors.END}
• Environment: .env
• Documentation: docs/
• Monitoring: http://localhost:5001 (admin/admin123)

{Colors.YELLOW}Need help? Check the documentation or open an issue!{Colors.END}
""")

def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="WMS Chatbot Setup Script")
    parser.add_argument('--skip-requirements', action='store_true', 
                       help='Skip system requirements check')
    parser.add_argument('--skip-python', action='store_true',
                       help='Skip Python environment setup')
    parser.add_argument('--skip-docker', action='store_true',
                       help='Skip Docker setup')
    parser.add_argument('--non-interactive', action='store_true',
                       help='Run in non-interactive mode')
    
    args = parser.parse_args()
    
    setup = WMSSetup()
    
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("╔══════════════════════════════════════╗")
    print("║      WMS Chatbot Setup Script       ║")
    print("║   Enterprise Warehouse Management    ║")
    print("║         AI Assistant Setup          ║")
    print("╚══════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    # System requirements check
    if not args.skip_requirements:
        if not setup.check_system_requirements():
            log_error("System requirements not met. Please install missing components.")
            sys.exit(1)
    
    # Python environment setup
    if not args.skip_python:
        if not setup.setup_python_environment():
            log_error("Python environment setup failed")
            sys.exit(1)
    
    # Directory setup
    setup.setup_directories()
    
    # Environment configuration
    if not args.non_interactive:
        if not setup.configure_environment():
            log_error("Environment configuration failed")
            sys.exit(1)
        
        # Validate configuration
        if not setup.validate_configuration():
            log_warning("Configuration validation failed. Please review your settings.")
    
    # Docker setup
    if not args.skip_docker:
        setup.create_docker_override()
        if not setup.run_initial_setup():
            log_error("Initial setup failed")
            sys.exit(1)
    
    # Display next steps
    setup.display_next_steps()

if __name__ == "__main__":
    main()