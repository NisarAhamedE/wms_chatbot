# WMS Screenshot & Document Management System - Core Files Documentation

## Main Application Files

### 1. `run_wms_app.py` - Application Entry Point
- Main launcher for the application
- Handles Python path setup and initialization
- Error handling for dependencies
- Imports and runs the main application logic

### 2. `wms_screenshot_app.py` - Main Application Logic
- Contains the main application class
- Initializes all components and modules
- Manages the application lifecycle
- Handles the main event loop

## Core Modules (`modules/`)

### 1. `ui_components.py` (57KB)
Primary UI Components and Interface Management
```python
class CaptureTab:
    # Handles screenshot capture and file uploads
    # Screenshot area selection
    # File processing queue management
    # Preview and status updates

class ManagementTab:
    # Document list and management
    # File details display
    # Export and deletion functionality
    # Database statistics

class ChatbotTab:
    # Chat interface for WMS queries
    # Message history display
    # User input handling
    # Response formatting
```

### 2. `file_processor.py` (22KB)
File Processing and Analysis Engine
```python
class FileProcessor:
    # Multi-format document processing
    # Azure Vision API integration for images
    # Background processing queue
    # File type detection and validation
```

### 3. `database_manager.py` (28KB)
Data Storage and Retrieval System
```python
class DatabaseManager:
    # Dual database management (SQLite + ChromaDB)
    # Document storage and retrieval
    # Vector search functionality
    # Backup and consistency management
```

### 4. `chatbot_manager.py` (11KB)
Chatbot and AI Integration
```python
class ChatbotManager:
    # Azure OpenAI integration
    # Conversation memory management
    # Document context processing
    # Query handling and response generation
```

### 5. `config_manager.py` (8.2KB)
Configuration Management
```python
class ConfigManager:
    # Application settings management
    # Azure API configuration
    # User preferences
    # Configuration validation
```

### 6. `theme_manager.py` (5.0KB)
UI Theme System
```python
class ThemeManager:
    # Application theming
    # Color scheme management
    # Style customization
    # Theme switching
```

### 7. `backup_scheduler.py` (11KB)
Backup Management System
```python
class BackupScheduler:
    # Automated database backups
    # Backup scheduling
    # Verification and validation
    # Restoration handling
```

### 8. `logger.py` (3.1KB)
Logging System
```python
class LoggerMixin:
    # Application-wide logging
    # Error tracking
    # Debug information
    # Log rotation
```

## Architecture Overview

The application follows a modular architecture with clear separation of concerns:

1. **User Interface Layer** (`ui_components.py`)
   - Handles all user interactions
   - Manages visual components
   - Provides feedback and status updates

2. **Processing Layer** (`file_processor.py`)
   - Handles file operations
   - Manages background tasks
   - Integrates with Azure Vision API

3. **Data Layer** (`database_manager.py`)
   - Manages data persistence
   - Handles search and retrieval
   - Ensures data consistency

4. **AI Layer** (`chatbot_manager.py`)
   - Provides AI functionality
   - Manages conversations
   - Processes user queries

5. **Support Systems**
   - Configuration (`config_manager.py`)
   - Theming (`theme_manager.py`)
   - Backup (`backup_scheduler.py`)
   - Logging (`logger.py`)

## Dependencies
- Azure OpenAI for vision and chat functionality
- ChromaDB for vector storage
- SQLite for relational data storage
- tkinter for UI components
- LangChain for conversation memory management

## Key Features
1. Screenshot capture with area selection
2. Text extraction using Azure Vision API
3. Document management and organization
4. AI-powered chatbot interface
5. Vector-based document search
6. Automated backup system
7. Themeable user interface
8. Comprehensive logging system
