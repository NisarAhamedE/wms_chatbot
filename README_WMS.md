# WMS Screenshot & Document Management System

A powerful Warehouse Management System (WMS) chatbot application with enhanced document processing, OCR capabilities, and intelligent query handling using Retrieval-Augmented Generation (RAG).

## 🚀 Features

### 📸 Enhanced Capture Tab
- **Multi-format Document Processing**: Support for PDF, Word, Excel, CSV, Markdown, HTML, and image files
- **Drag & Drop Interface**: User-friendly file upload with visual feedback
- **Text Input**: Direct article/text pasting with character/word count
- **Screenshot Capture**: Integrated screenshot functionality with OCR
- **Batch Processing**: Process multiple files simultaneously with progress tracking
- **File Validation**: Automatic format detection and validation

### 📁 Management Tab
- **Document Browser**: View all stored documents with metadata
- **Search & Filter**: Find documents by type, date, or content
- **Export Functionality**: Export documents to various formats
- **Database Statistics**: View comprehensive storage statistics
- **Delete Operations**: Remove documents from both SQL and vector databases

### 🤖 WMS Chatbot Tab
- **RAG-powered Queries**: Intelligent responses using document knowledge base
- **Conversation Memory**: Maintains context across multiple interactions
- **Multi-modal Input**: Support for text, voice, and image queries
- **Source Attribution**: Shows which documents were used for responses
- **Azure OpenAI Integration**: Advanced AI capabilities with vision support

## 🏗️ Architecture

### Core Components
- **Database Manager**: Handles SQLite and ChromaDB operations
- **File Processor**: Multi-format document processing with OCR
- **Chatbot Manager**: RAG implementation with LangChain
- **UI Components**: Three-tab interface with modern design
- **Configuration Manager**: Centralized settings management

### Technology Stack
- **GUI**: Tkinter with ttk styling
- **Database**: SQLite (metadata) + ChromaDB (vector embeddings)
- **AI/ML**: Azure OpenAI, LangChain, Tesseract OCR
- **Document Processing**: PyPDF2, python-docx, openpyxl, BeautifulSoup
- **Image Processing**: OpenCV, Pillow, NumPy

## 📋 Requirements

### System Requirements
- Python 3.8 or higher
- Windows 10/11 (tested on Windows 10)
- 4GB RAM minimum (8GB recommended)
- 2GB free disk space

### Python Dependencies
```
# Core GUI and System
tkinter
tkinterdnd2

# Screenshot and Image Processing
pyautogui
Pillow
opencv-python
numpy

# OCR and Text Processing
pytesseract
langchain
langchain-openai
langchain-community

# Azure OpenAI Integration
openai

# Database
sqlite3
chromadb
pymongo

# Document Processing
PyPDF2
python-docx
openpyxl
beautifulsoup4
markdown

# File Handling
pathlib
shutil
mimetypes

# Audio Processing
speech_recognition
pyaudio

# Vector Database
sentence-transformers
faiss-cpu

# Utilities
python-dotenv
asyncio
threading
queue
datetime
json
os
sys
logging

# UI Enhancements
ttk
tkinter.ttk
tkinter.messagebox
tkinter.filedialog
tkinter.scrolledtext

# Progress and Feedback
tqdm

# Error Handling
traceback
```

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd scale_docs
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Tesseract OCR
- **Windows**: Download and install from [GitHub Releases](https://github.com/UB-Mannheim/tesseract/wiki)
- **Linux**: `sudo apt-get install tesseract-ocr`
- **macOS**: `brew install tesseract`

### 4. Configure Azure OpenAI (Optional)
Create a `.env` file in the project root:
```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

## 🚀 Usage

### Starting the Application
```bash
python run_wms_app.py
```

### Basic Workflow

#### 1. Capture Documents
1. **File Upload**: Drag & drop or browse for documents
2. **Text Input**: Paste articles or text directly
3. **Screenshots**: Capture or load images for OCR processing
4. **Batch Processing**: Process multiple files simultaneously

#### 2. Manage Documents
1. **View Documents**: Browse all stored documents with metadata
2. **Search**: Find specific documents using filters
3. **Export**: Download documents in various formats
4. **Delete**: Remove unwanted documents from databases

#### 3. Chat with WMS Bot
1. **Ask Questions**: Query about warehouse operations, inventory, etc.
2. **Image Analysis**: Upload images for AI-powered analysis
3. **Voice Input**: Use voice commands (future feature)
4. **Context Memory**: Maintain conversation history

## 📁 Project Structure

```
scale_docs/
├── wms_screenshot_app.py          # Main application
├── run_wms_app.py                 # Launcher script
├── requirements.txt               # Python dependencies
├── README_WMS.md                  # This file
├── .env                          # Environment variables (create this)
├── modules/                      # Core modules
│   ├── __init__.py
│   ├── config_manager.py         # Configuration management
│   ├── database_manager.py       # Database operations
│   ├── file_processor.py         # Document processing
│   ├── chatbot_manager.py        # RAG chatbot
│   ├── ui_components.py          # UI components
│   └── logger.py                 # Logging utilities
├── data/                         # Database files (auto-created)
│   ├── wms_screenshots.db        # SQLite database
│   └── chroma_db/                # ChromaDB vector store
├── logs/                         # Application logs (auto-created)
├── temp/                         # Temporary files (auto-created)
├── output/                       # Processed outputs (auto-created)
└── backup/                       # Database backups (auto-created)
```

## ⚙️ Configuration

### Application Settings
The application uses a `config.json` file for settings:

```json
{
  "database": {
    "sqlite_path": "data/wms_screenshots.db",
    "chroma_path": "data/chroma_db",
    "backup_enabled": true,
    "backup_interval": 24
  },
  "azure_openai": {
    "api_key": "",
    "endpoint": "",
    "deployment_name": "",
    "api_version": "2024-02-15-preview"
  },
  "file_processing": {
    "max_file_size": 52428800,
    "supported_formats": [".txt", ".doc", ".docx", ".pdf", ".md", ".rtf", ".xlsx", ".xls", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".ppt", ".pptx", ".html", ".htm"],
    "temp_dir": "temp",
    "output_dir": "output"
  },
  "ui": {
    "theme": "clam",
    "window_size": "1200x800",
    "min_window_size": "1000x600",
    "auto_save_interval": 30
  },
  "chatbot": {
    "model_name": "gpt-4-vision-preview",
    "max_tokens": 4000,
    "temperature": 0.7,
    "context_window": 10,
    "enable_voice": true,
    "enable_image_input": true
  },
  "logging": {
    "level": "INFO",
    "file": "logs/app.log",
    "max_size": 10485760,
    "backup_count": 5
  }
}
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
pip install -r requirements.txt
```

#### 2. Tesseract Not Found
- Ensure Tesseract is installed and in PATH
- Windows: Add Tesseract installation directory to system PATH

#### 3. Azure OpenAI Errors
- Verify API credentials in `.env` file
- Check Azure OpenAI service status
- Ensure deployment name is correct

#### 4. Database Errors
- Check file permissions for `data/` directory
- Ensure sufficient disk space
- Restart application if database is locked

#### 5. Memory Issues
- Close other applications
- Reduce batch processing size
- Increase system RAM

### Log Files
Check `logs/app.log` for detailed error information and debugging.

## 🔮 Future Enhancements

### Planned Features
- **Voice Recognition**: Speech-to-text input
- **Advanced OCR**: Better image preprocessing
- **Real-time Collaboration**: Multi-user support
- **Cloud Integration**: Azure Blob Storage support
- **Mobile App**: Companion mobile application
- **API Endpoints**: RESTful API for integration
- **Advanced Analytics**: Document usage statistics
- **Custom Workflows**: User-defined processing pipelines

### Performance Optimizations
- **Caching**: Intelligent document caching
- **Parallel Processing**: Multi-threaded file processing
- **Database Optimization**: Query performance improvements
- **Memory Management**: Better resource utilization

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the log files for errors

## 🎯 Use Cases

### Warehouse Management
- **Inventory Tracking**: Process inventory reports and documents
- **Shipping Documentation**: Analyze shipping manifests and labels
- **Receiving Procedures**: Process receiving documents and quality checks
- **Safety Compliance**: Review safety documentation and procedures

### Document Management
- **Multi-format Support**: Handle various document types seamlessly
- **Search & Retrieval**: Find specific information quickly
- **Knowledge Base**: Build comprehensive document knowledge base
- **Compliance**: Maintain audit trails and document history

### AI-Powered Assistance
- **Natural Language Queries**: Ask questions in plain English
- **Context-Aware Responses**: Get relevant answers based on stored documents
- **Image Analysis**: Analyze warehouse photos and diagrams
- **Process Optimization**: Get suggestions for workflow improvements

---

**Note**: This application is designed for warehouse management professionals and can be customized for specific industry needs. 