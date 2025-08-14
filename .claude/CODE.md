# Code Documentation
# WMS Chatbot - Complete Technical Implementation Guide

## Executive Summary
This document provides comprehensive technical documentation for the WMS Chatbot & Document Management System. The application combines a Tkinter desktop interface, FastAPI backend, dual-database architecture (PostgreSQL + ChromaDB), and Azure OpenAI integration to deliver an enterprise-grade warehouse management solution.

## Table of Contents
1. [Project Structure](#project-structure)
2. [Core Components](#core-components)
3. [Database Layer](#database-layer)
4. [Desktop Application](#desktop-application)
5. [Document Processing](#document-processing)
6. [Chatbot System](#chatbot-system)
7. [API Implementation](#api-implementation)
8. [Agent Framework](#agent-framework)
9. [Configuration Management](#configuration-management)
10. [Development & Deployment](#development--deployment)

---

## 1. Project Structure

```
wms_chatbot/
├── .claude/                     # Claude AI assistant documentation
│   ├── PRD.md                  # Product Requirements Document
│   ├── CODE.md                 # Technical documentation (this file)
│   └── CLAUDE.md               # AI assistant instructions
├── modules/                     # Desktop application modules
│   ├── database_manager.py     # PostgreSQL + ChromaDB management
│   ├── file_processor.py       # Document processing engine
│   ├── chatbot_manager.py      # LangChain chatbot implementation
│   ├── ui_components.py        # Tkinter UI components
│   ├── backup_scheduler.py     # Automated backup system
│   ├── config_manager.py       # Configuration management
│   ├── theme_manager.py        # UI theme management
│   └── logger.py               # Logging utilities
├── src/                        # Backend source code
│   ├── core/                   # Core utilities
│   │   ├── config.py          # Pydantic settings
│   │   ├── logging.py         # Structured logging
│   │   ├── llm_constraints.py # LLM validation
│   │   └── audit.py           # Audit logging
│   ├── database/              # Database layer
│   │   ├── connection.py      # Connection management
│   │   ├── models.py          # SQLAlchemy models
│   │   └── vector_store.py    # ChromaDB integration
│   ├── agents/                # Specialized WMS agents
│   │   ├── base.py            # Base agent class
│   │   ├── operational_db/    # Database query agents
│   │   └── categories/        # 11 category agents
│   │       ├── inventory.py
│   │       ├── allocation.py
│   │       ├── receiving.py
│   │       └── ... (8 more)
│   ├── api/                   # FastAPI implementation
│   │   ├── main.py           # FastAPI app
│   │   ├── routes/           # API endpoints
│   │   ├── auth.py          # Authentication
│   │   └── middleware.py     # Security middleware
│   └── processing/           # Data processing
│       └── text_pipeline.py  # Text extraction
├── frontend/                  # React web interface
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/           # Application pages
│   │   ├── services/        # API services
│   │   └── store/           # Redux store
│   └── package.json
├── data/                     # Data storage
│   ├── wms_screenshots.db   # SQLite database
│   └── chroma_db/           # Vector database
├── output/                   # Processed files
├── logs/                     # Application logs
├── docker/                   # Docker configuration
├── tests/                    # Test suite
├── wms_screenshot_app.py     # Main desktop application
├── config.json              # Application configuration
├── requirements.txt         # Python dependencies
└── docker-compose.yml       # Container orchestration
```

---

## 2. Core Components

### 2.1 Main Application (wms_screenshot_app.py)

**Location**: `wms_screenshot_app.py:26-405`

The main application class that orchestrates the entire desktop interface.

```python
class WMSScreenshotApp:
    """Main WMS Screenshot Application with enhanced three-tab interface"""
    
    def __init__(self):
        # Initialize managers
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager(config_manager=self.config_manager)
        self.file_processor = FileProcessor(self.db_manager)
        self.chatbot_manager = ChatbotManager(self.db_manager)
        self.backup_scheduler = BackupScheduler(self.db_manager, self.config_manager)
```

**Key Features**:
- Three-tab interface (Chatbot, Capture, Management)
- Background processing with threading
- Queue-based file processing
- Centralized error handling
- Resource cleanup on exit

**Important Methods**:
- `setup_ui()`: Initialize the three-tab interface
- `process_queue()`: Background file processing
- `handle_processing_item()`: Process individual queue items
- `cleanup()`: Resource cleanup before exit

### 2.2 Configuration Manager

**Location**: `modules/config_manager.py:1-200`

Centralized configuration management using Pydantic for validation.

```python
class ConfigManager:
    """Centralized configuration management with validation"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
```

**Key Features**:
- Environment variable integration
- Azure OpenAI configuration validation
- Database connection string management
- Default configuration generation
- Runtime configuration updates

---

## 3. Database Layer

### 3.1 Database Manager

**Location**: `modules/database_manager.py:18-500`

Manages dual-database architecture with PostgreSQL and ChromaDB.

```python
class DatabaseManager(LoggerMixin):
    """Manages PostgreSQL (TimescaleDB) + ChromaDB for the WMS application"""
    
    def __init__(self, sqlite_path: str = "data/wms_screenshots.db", 
                 chroma_path: str = "data/chroma_db",
                 max_connections: int = 10,
                 config_manager: ConfigManager = None):
```

**Database Architecture**:

#### 3.1.1 PostgreSQL/TimescaleDB (Structured Data)
- **Screenshots Table**: Metadata, timestamps, dimensions
- **Documents Table**: File information, processing status
- **Conversations Table**: Chat history and context
- **Users Table**: Authentication and preferences
- **Audit_Log Table**: System activity tracking

#### 3.1.2 ChromaDB (Vector Embeddings)
- **Documents Collection**: Document embeddings for semantic search
- **Conversations Collection**: Conversation context embeddings
- **Knowledge Base Collection**: Curated WMS knowledge

**Key Methods**:
- `store_screenshot()`: Store screenshot metadata
- `store_document()`: Store document with vector embedding
- `search_similar()`: Semantic search using embeddings
- `get_documents()`: Retrieve documents with metadata
- `backup_database()`: Automated backup operations

### 3.2 Vector Store Integration

**Location**: `src/database/vector_store.py:1-200`

ChromaDB integration for semantic search capabilities.

```python
class VectorStore:
    """ChromaDB integration for document embeddings"""
    
    def __init__(self, persist_directory: str = "data/chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="documents",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        )
```

---

## 4. Desktop Application

### 4.1 UI Components

**Location**: `modules/ui_components.py:1-1500`

Tkinter-based user interface with three main tabs.

#### 4.1.1 ChatbotTab
```python
class ChatbotTab(ttk.Frame):
    """Chatbot interface with conversation history and input methods"""
    
    def __init__(self, parent, chatbot_manager):
        super().__init__(parent)
        self.chatbot_manager = chatbot_manager
        self.setup_ui()
```

**Features**:
- Multi-modal input (text, voice, image)
- Conversation history display
- Rich text formatting with markdown support
- Image upload and analysis
- Context-aware responses

#### 4.1.2 CaptureTab
```python
class CaptureTab(ttk.Frame):
    """Document capture and processing interface"""
    
    def __init__(self, parent, file_processor, progress_tracker, processing_queue):
        super().__init__(parent)
        self.file_processor = file_processor
        self.setup_ui()
```

**Features**:
- Drag & drop file upload
- Batch processing with progress tracking
- Screenshot capture functionality
- Text input for articles
- File validation and preview

#### 4.1.3 ManagementTab
```python
class ManagementTab(ttk.Frame):
    """File and database management interface"""
    
    def __init__(self, parent, db_manager, file_processor):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setup_ui()
```

**Features**:
- Document browser with metadata
- Search and filter capabilities
- Export functionality
- Database statistics
- Bulk operations

### 4.2 Theme Management

**Location**: `modules/theme_manager.py:1-200`

Modern dark theme with customizable styling.

```python
class ThemeManager:
    """Manages application themes and styling"""
    
    def __init__(self):
        self.current_theme = "dark"
        self.themes = {
            "dark": self._get_dark_theme(),
            "light": self._get_light_theme()
        }
```

---

## 5. Document Processing

### 5.1 File Processor

**Location**: `modules/file_processor.py:1-800`

Multi-format document processing with OCR capabilities.

```python
class FileProcessor(LoggerMixin):
    """Handles multi-format document processing with OCR"""
    
    def __init__(self, database_manager):
        super().__init__()
        self.db_manager = database_manager
        self.supported_formats = [
            '.pdf', '.docx', '.doc', '.txt', '.md', '.rtf',
            '.xlsx', '.xls', '.csv', '.png', '.jpg', '.jpeg',
            '.gif', '.bmp', '.tiff', '.ppt', '.pptx', '.html', '.htm'
        ]
```

**Processing Pipeline**:
1. **File Validation**: Format and size verification
2. **Text Extraction**: Format-specific parsers
3. **OCR Processing**: Tesseract for images
4. **Metadata Extraction**: File properties and content analysis
5. **Embedding Generation**: Vector representations
6. **Storage**: Dual database storage

**Key Methods**:
- `process_file()`: Main processing entry point
- `extract_text_from_pdf()`: PDF text extraction
- `extract_text_from_image()`: OCR processing
- `extract_text_from_office()`: Office document processing
- `generate_embeddings()`: Vector embedding creation

### 5.2 OCR Integration

**Dependencies**: Tesseract OCR engine

```python
def extract_text_from_image(self, image_path: str) -> str:
    """Extract text from image using Tesseract OCR"""
    try:
        # Image preprocessing
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Noise reduction and enhancement
        denoised = cv2.medianBlur(gray, 5)
        
        # OCR with optimized configuration
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(denoised, config=custom_config)
        
        return text.strip()
    except Exception as e:
        self.log_error(f"OCR processing failed: {e}")
        return ""
```

---

## 6. Chatbot System

### 6.1 Chatbot Manager

**Location**: `modules/chatbot_manager.py:20-400`

LangChain-based chatbot with RAG implementation.

```python
class ChatbotManager(LoggerMixin):
    """Manages WMS chatbot functionality with conversation memory"""
    
    def __init__(self, db_manager, config_manager: ConfigManager = None):
        super().__init__()
        self.db_manager = db_manager
        self.llm = None  # Azure OpenAI client
        self.memory = None  # Conversation memory
        self.init_chatbot()
```

**RAG Pipeline**:
1. **Query Processing**: Natural language understanding
2. **Document Retrieval**: Semantic search in vector database
3. **Context Assembly**: Relevant document chunks
4. **Response Generation**: Azure OpenAI with context
5. **Memory Update**: Conversation history management

**Key Features**:
- Azure OpenAI GPT-4 integration
- Conversation memory with LangChain
- Multi-modal input support
- Source attribution for responses
- Context-aware query handling

### 6.2 Conversation Memory

```python
def init_chatbot(self):
    """Initialize chatbot components"""
    # Initialize Azure OpenAI client
    self.llm = AzureChatOpenAI(
        azure_deployment=azure_config["deployment"]["chat"],
        openai_api_version=azure_config["api_version"],
        azure_endpoint=azure_config["endpoint"],
        api_key=azure_config["api_key"],
        temperature=0.0,
        max_tokens=4000
    )
    
    # Initialize conversation memory
    self.message_history = ChatMessageHistory()
    self.memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        chat_memory=self.message_history,
        max_token_limit=4000
    )
```

---

## 7. API Implementation

### 7.1 FastAPI Backend

**Location**: `src/api/main.py:1-200`

RESTful API for web interface and external integrations.

```python
from fastapi import FastAPI, HTTPException, Depends, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="WMS Chatbot API",
    description="Enterprise Warehouse Management System API",
    version="2.0.0"
)
```

**API Endpoints**:

#### 7.1.1 Chat Endpoints
- `POST /chat/query`: Process chatbot queries
- `GET /chat/history`: Retrieve conversation history
- `DELETE /chat/clear`: Clear conversation memory
- `POST /chat/image`: Process image queries

#### 7.1.2 Document Endpoints
- `POST /documents/upload`: Upload and process documents
- `GET /documents/`: List documents with pagination
- `GET /documents/{doc_id}`: Retrieve specific document
- `DELETE /documents/{doc_id}`: Delete document
- `GET /documents/search`: Semantic search

#### 7.1.3 System Endpoints
- `GET /health`: Health check
- `GET /metrics`: System metrics
- `POST /auth/login`: Authentication
- `GET /config`: Configuration status

### 7.2 Authentication & Security

**Location**: `src/api/auth.py:1-150`

JWT-based authentication with role-based access control.

```python
class AuthManager:
    """JWT authentication and authorization"""
    
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
```

---

## 8. Agent Framework

### 8.1 Base Agent Class

**Location**: `src/agents/base.py:1-200`

Foundation for specialized WMS agents.

```python
class BaseAgent:
    """Base class for all WMS agents"""
    
    def __init__(self, name: str, description: str, llm_client=None):
        self.name = name
        self.description = description
        self.llm_client = llm_client
        self.capabilities = []
```

### 8.2 Specialized Agents

**Location**: `src/agents/categories/`

11 specialized agents for different WMS domains:

#### 8.2.1 Inventory Agent
```python
class InventoryAgent(BaseAgent):
    """Handles inventory-related queries and operations"""
    
    def __init__(self, llm_client=None):
        super().__init__(
            name="InventoryAgent",
            description="Manages inventory levels, stock tracking, and availability queries"
        )
```

#### 8.2.2 Allocation Agent
```python
class AllocationAgent(BaseAgent):
    """Handles order allocation and prioritization"""
    
    def process_allocation_query(self, query: str, context: dict) -> dict:
        """Process allocation-specific queries"""
        # Implementation for allocation logic
```

**Complete Agent List**:
1. **InventoryAgent**: Stock levels, tracking, availability
2. **AllocationAgent**: Order allocation, prioritization
3. **ReceivingAgent**: Inbound processing, verification
4. **LocationsPutawayAgent**: Location assignments, optimization
5. **ReplenishmentAgent**: Stock replenishment strategies
6. **WaveManagementAgent**: Order wave processing
7. **CycleCountingAgent**: Inventory accuracy, audits
8. **WorkAgent**: Task management, assignments
9. **ItemsAgent**: Product master data, specifications
10. **LocationsAgent**: Warehouse layout, zones
11. **DataCategorizationAgent**: Query routing, classification

---

## 9. Configuration Management

### 9.1 Configuration Files

#### 9.1.1 config.json
```json
{
  "database": {
    "postgres": {
      "host": "localhost",
      "port": 5432,
      "database": "wms",
      "pool_min": 1,
      "pool_max": 10
    },
    "chroma": {
      "path": "data/chroma_db",
      "collection_name": "documents"
    }
  },
  "azure_openai": {
    "endpoint": "",
    "api_key": "",
    "deployment": {
      "chat": "gpt-4",
      "embedding": "text-embedding-ada-002"
    },
    "api_version": "2024-02-15-preview"
  },
  "file_processing": {
    "max_file_size": 52428800,
    "supported_formats": [".txt", ".pdf", ".docx", ".xlsx", ".png", ".jpg"],
    "temp_dir": "temp",
    "output_dir": "output"
  },
  "chatbot": {
    "max_tokens": 4000,
    "temperature": 0.0,
    "context_window": 10,
    "enable_voice": false,
    "enable_image_input": true
  }
}
```

#### 9.1.2 Environment Variables (.env)
```bash
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# PostgreSQL Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=wms
DB_USER=wms_user
DB_PASSWORD=your_password_here
DB_SSLMODE=prefer

# Security
JWT_SECRET_KEY=your_jwt_secret_key
```

### 9.2 Backup Scheduler

**Location**: `modules/backup_scheduler.py:1-200`

Automated backup system with configurable schedules.

```python
class BackupScheduler(LoggerMixin):
    """Automated backup scheduler for databases"""
    
    def __init__(self, db_manager, config_manager, interval_hours: int = 24):
        super().__init__()
        self.db_manager = db_manager
        self.config_manager = config_manager
        self.interval_hours = interval_hours
        self.backup_thread = None
        self.running = False
```

---

## 10. Development & Deployment

### 10.1 Development Setup

#### 10.1.1 Prerequisites
- Python 3.8+
- PostgreSQL 13+ with TimescaleDB
- Tesseract OCR
- Node.js 16+ (for frontend)
- Docker & Docker Compose

#### 10.1.2 Installation Steps
```bash
# Clone repository
git clone <repository-url>
cd wms_chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize databases
python -c "from modules.database_manager import DatabaseManager; db = DatabaseManager(); db.create_tables()"

# Run desktop application
python wms_screenshot_app.py

# Or run API server
python src/api/main.py
```

### 10.2 Docker Deployment

#### 10.2.1 docker-compose.yml
```yaml
version: '3.8'

services:
  postgres:
    image: timescale/timescaledb:latest-pg14
    environment:
      POSTGRES_DB: wms
      POSTGRES_USER: wms_user
      POSTGRES_PASSWORD: change_me
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  wms_api:
    build: .
    environment:
      - DB_HOST=postgres
      - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
      - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
    depends_on:
      - postgres
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - wms_api

volumes:
  postgres_data:
```

### 10.3 Testing Strategy

#### 10.3.1 Test Structure
```
tests/
├── unit/
│   ├── test_database_manager.py
│   ├── test_file_processor.py
│   ├── test_chatbot_manager.py
│   └── test_agents.py
├── integration/
│   ├── test_api_endpoints.py
│   ├── test_document_pipeline.py
│   └── test_chat_flow.py
└── e2e/
    ├── test_desktop_app.py
    └── test_web_interface.py
```

#### 10.3.2 Running Tests
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# All tests with coverage
pytest --cov=modules --cov=src tests/
```

### 10.4 Performance Monitoring

#### 10.4.1 Logging Configuration
**Location**: `modules/logger.py:1-100`

```python
class LoggerMixin:
    """Mixin class for standardized logging"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setup_logger()
    
    def setup_logger(self):
        """Setup structured logging with file and console handlers"""
        # Implementation for structured logging
```

#### 10.4.2 Metrics Collection
- Response time tracking
- Database query performance
- Memory usage monitoring
- Error rate tracking
- User interaction analytics

---

## Appendix A: Code Standards

### A.1 Python Style Guide
- Follow PEP 8 guidelines
- Use type hints for all functions
- Comprehensive docstrings
- Error handling with logging
- Unit test coverage > 80%

### A.2 Database Standards
- Use parameterized queries
- Connection pooling
- Transaction management
- Index optimization
- Regular backup procedures

### A.3 Security Guidelines
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- Authentication for all endpoints
- Audit logging for sensitive operations

---

## Appendix B: Troubleshooting

### B.1 Common Issues
1. **Azure OpenAI Connection**: Verify API keys and endpoints
2. **Database Connection**: Check PostgreSQL service and credentials
3. **OCR Errors**: Ensure Tesseract is properly installed
4. **Memory Issues**: Monitor ChromaDB index size
5. **File Processing**: Check file permissions and formats

### B.2 Debug Commands
```bash
# Check database connections
python -c "from modules.database_manager import DatabaseManager; DatabaseManager().test_connection()"

# Verify Azure OpenAI
python -c "from modules.config_manager import ConfigManager; ConfigManager().test_azure_connection()"

# Check file processing
python -c "from modules.file_processor import FileProcessor; FileProcessor().test_ocr()"
```

---

**Document Version**: 2.0  
**Last Updated**: August 14, 2025  
**Maintainer**: Development Team