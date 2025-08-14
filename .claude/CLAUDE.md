# CLAUDE.md - AI Assistant Instructions
# WMS Chatbot & Document Management System

## Project Overview
This is a comprehensive Warehouse Management System (WMS) chatbot application with document processing capabilities, combining desktop (Tkinter) and web (React) interfaces with AI-powered conversational features.

## Key Documentation References
Before working on this project, **ALWAYS** read these critical documentation files:

### 📋 Primary Documentation
1. **`.claude/PRD.md`** - Product Requirements Document
   - Complete feature specifications
   - System architecture overview
   - Technical and business requirements
   - Success metrics and compliance standards

2. **`.claude/CODE.md`** - Technical Implementation Guide
   - Detailed code architecture
   - Component documentation with file locations
   - Database schemas and API endpoints
   - Development and deployment procedures

### 📁 Project Structure
```
wms_chatbot/
├── .claude/               # AI Assistant documentation (READ FIRST)
├── modules/               # Desktop app core modules
├── src/                   # Backend source code
├── frontend/              # React web interface
├── wms_screenshot_app.py  # Main desktop application
├── config.json           # Application configuration
└── requirements.txt       # Dependencies
```

## Core System Components

### 🖥️ Desktop Application (Primary Interface)
- **Main File**: `wms_screenshot_app.py` (lines 26-405)
- **Architecture**: Three-tab Tkinter interface
  - **Chatbot Tab**: AI-powered conversational interface
  - **Capture Tab**: Document/screenshot processing
  - **Management Tab**: File and database management
- **Key Modules**: 
  - `modules/database_manager.py` - PostgreSQL + ChromaDB
  - `modules/chatbot_manager.py` - LangChain RAG implementation
  - `modules/file_processor.py` - Multi-format document processing
  - `modules/ui_components.py` - Tkinter UI components

### 🤖 AI & Chatbot System
- **Framework**: LangChain with Azure OpenAI GPT-4
- **Architecture**: RAG (Retrieval-Augmented Generation)
- **Features**: Conversation memory, multi-modal input, specialized WMS agents
- **Agents**: 11 specialized agents (Inventory, Allocation, Receiving, etc.)
- **Location**: `modules/chatbot_manager.py` + `src/agents/`

### 🗄️ Database Architecture
- **Dual Database System**:
  - **PostgreSQL/TimescaleDB**: Structured data, metadata, time-series
  - **ChromaDB**: Vector embeddings for semantic search
- **Key Tables**: Screenshots, Documents, Conversations, Users, Audit_Log
- **Location**: `modules/database_manager.py` (lines 18-500)

### 📄 Document Processing
- **Supported Formats**: PDF, Word, Excel, images, HTML, Markdown, and more
- **Features**: OCR (Tesseract), text extraction, batch processing
- **Pipeline**: Validation → Extraction → OCR → Embeddings → Storage
- **Location**: `modules/file_processor.py` (lines 1-800)

### 🌐 Web Interface (Secondary)
- **Framework**: React + TypeScript with Redux
- **API**: FastAPI backend with JWT authentication
- **Features**: File management, chat interface, dashboard
- **Location**: `frontend/src/` + `src/api/`

## Important Development Guidelines

### ⚠️ Critical Rules
1. **ALWAYS preserve existing functionality** - this is a production system
2. **NEVER modify database schemas** without understanding the full impact
3. **READ documentation files first** before making any changes
4. **Test thoroughly** - affects both desktop and web interfaces
5. **Follow established patterns** - examine existing code before implementing

### 🔧 Code Standards
- **Python**: PEP 8, type hints, comprehensive docstrings
- **Error Handling**: Use LoggerMixin for consistent logging
- **Database**: Parameterized queries, connection pooling
- **Security**: Input validation, authentication for all endpoints

### 🏗️ Architecture Patterns
- **Desktop App**: Manager pattern (ConfigManager, DatabaseManager, etc.)
- **API**: FastAPI with dependency injection
- **Database**: Repository pattern with dual storage
- **UI**: Component-based with separation of concerns

## Configuration & Environment

### 🔐 Required Environment Variables
```bash
# Azure OpenAI (REQUIRED for chatbot)
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment

# PostgreSQL (REQUIRED for production)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=wms
DB_USER=wms_user
DB_PASSWORD=your_password

# Security (for web interface)
JWT_SECRET_KEY=your_secret_key
```

### 📝 Configuration Files
- **`config.json`**: Application settings, feature flags, processing limits
- **`.env`**: Sensitive credentials and connection strings
- **`docker-compose.yml`**: Container orchestration for deployment

## Common Development Tasks

### 🚀 Getting Started
1. **Read PRD.md and CODE.md first** - understand the system
2. **Check environment setup** - ensure all dependencies are installed
3. **Verify configuration** - Azure OpenAI and database connections
4. **Run tests** - `pytest tests/` to ensure system health
5. **Start desktop app** - `python wms_screenshot_app.py`

### 🔍 Debugging & Troubleshooting
- **Check logs**: `logs/app.log` for detailed error information
- **Database issues**: Verify PostgreSQL service and ChromaDB persistence
- **Azure OpenAI**: Test API credentials and deployment names
- **OCR problems**: Ensure Tesseract is installed and in PATH
- **File processing**: Check supported formats and size limits

### 🧪 Testing Approach
```bash
# Unit tests
pytest tests/unit/

# Integration tests  
pytest tests/integration/

# Full test suite with coverage
pytest --cov=modules --cov=src tests/
```

## Key File Locations & Line Numbers

### Critical Components
- **Main App**: `wms_screenshot_app.py:26-405`
- **Database Manager**: `modules/database_manager.py:18-500`
- **Chatbot Manager**: `modules/chatbot_manager.py:20-400`
- **File Processor**: `modules/file_processor.py:1-800`
- **UI Components**: `modules/ui_components.py:1-1500`
- **FastAPI Server**: `src/api/main.py:1-200`

### Configuration & Settings
- **Config Manager**: `modules/config_manager.py:1-200`
- **Environment Setup**: `modules/config_manager.py:50-100`
- **Theme Management**: `modules/theme_manager.py:1-200`
- **Logging Setup**: `modules/logger.py:1-100`

## Development Workflow

### 🔄 Typical Change Process
1. **Understand the requirement** - read documentation
2. **Locate relevant code** - use file locations in CODE.md
3. **Examine existing patterns** - follow established conventions
4. **Implement changes** - maintain backward compatibility
5. **Test thoroughly** - unit, integration, and manual testing
6. **Update documentation** - if architecture changes

### 🚨 Change Impact Assessment
Before modifying:
- **Desktop app changes**: Test all three tabs
- **Database changes**: Verify both PostgreSQL and ChromaDB
- **API changes**: Test both desktop and web interfaces
- **Configuration changes**: Check default values and validation
- **Agent changes**: Test chatbot functionality and responses

## Security & Compliance

### 🔒 Security Considerations
- **API Keys**: Store in environment variables only
- **Database Access**: Use connection pooling and parameterized queries
- **File Processing**: Validate file types and sizes
- **User Authentication**: JWT tokens for web interface
- **Audit Logging**: Track all sensitive operations

### 📊 Performance Guidelines
- **Response Times**: < 3 seconds for chatbot queries
- **File Processing**: < 10 seconds per document
- **Database Queries**: < 1 second for standard operations
- **Memory Usage**: Monitor ChromaDB index size
- **Concurrent Users**: Support 100+ simultaneous users

## Integration Points

### 🔌 External Dependencies
- **Azure OpenAI**: GPT-4 for chat, embeddings for search
- **PostgreSQL**: Structured data and TimescaleDB for time-series
- **ChromaDB**: Vector embeddings and semantic search
- **Tesseract**: OCR for image text extraction
- **LangChain**: RAG framework and conversation memory

### 📡 API Integrations
- **Chat API**: `/chat/query`, `/chat/history`, `/chat/clear`
- **Document API**: `/documents/upload`, `/documents/search`
- **Health Check**: `/health`, `/metrics` for monitoring
- **Authentication**: `/auth/login` for web interface

## Maintenance & Operations

### 🔧 Regular Maintenance
- **Database Backups**: Automated daily backups via BackupScheduler
- **Log Rotation**: Configured in logging settings
- **Performance Monitoring**: Track response times and resource usage
- **Security Updates**: Keep dependencies current
- **Configuration Review**: Periodically review and optimize settings

### 📈 Monitoring & Alerts
- **Application Logs**: Structured logging with levels
- **Performance Metrics**: Response times, throughput, errors
- **Resource Usage**: CPU, memory, disk space
- **Health Checks**: Endpoint monitoring for uptime
- **User Analytics**: Feature usage and satisfaction metrics

---

## Quick Reference Commands

```bash
# Start desktop application
python wms_screenshot_app.py

# Start API server
python src/api/main.py

# Run tests
pytest tests/

# Check system health
python -c "from modules.database_manager import DatabaseManager; DatabaseManager().test_connection()"

# Verify Azure OpenAI
python -c "from modules.config_manager import ConfigManager; ConfigManager().test_azure_connection()"

# Docker deployment
docker-compose up -d
```

---

**Remember**: This is a complex, production-grade system. Always read the documentation in `.claude/PRD.md` and `.claude/CODE.md` before making changes. The system serves both desktop and web users with real-time AI capabilities, so changes must be thoroughly tested and backward-compatible.

**Document Version**: 1.0  
**Created**: August 14, 2025  
**Purpose**: Claude AI Assistant guidance for WMS Chatbot development