# Design Document
## Enhanced Screenshot Capture App with WMS Chatbot

**Version:** 1.0  
**Date:** August 5, 2025  
**Based on PRD:** v1.1  

---

## 1. System Overview

### 1.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│  Tab 1: Capture    │  Tab 2: Management    │  Tab 3: Chatbot   │
│  - Screenshot UI   │  - File Browser       │  - Chat Interface │
│  - Area Selection  │  - Database Status    │  - Multi-Modal    │
│  - Preview         │  - Bulk Operations    │  - Rich Output    │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│  ScreenshotApp    │  DatabaseManager    │  ChatbotEngine      │
│  - Core Logic     │  - SQL Operations   │  - LangChain RAG    │
│  - UI Controller  │  - Vector Ops       │  - Conversation Mgmt│
│  - Workflow Mgmt  │  - Sync Engine      │  - Multi-Modal Proc │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│  TextExtractor    │  FileManager        │  EmbeddingService   │
│  - OCR Engine     │  - File Operations  │  - Vector Generation│
│  - LLM Vision     │  - Backup/Restore   │  - Semantic Search  │
│  - Preprocessing  │  - Export/Import    │  - Index Management │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│  SQL Database     │  Vector Database    │  File System        │
│  - Metadata       │  - Embeddings       │  - Screenshots      │
│  - Relationships  │  - Documents        │  - Markdown Files   │
│  - Transactions   │  - Indexes          │  - Exports          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Interaction Diagram

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Capture   │    │ Management  │    │  Chatbot    │
│    Tab      │    │    Tab      │    │    Tab      │
└─────┬───────┘    └─────┬───────┘    └─────┬───────┘
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
              ┌──────────┴──────────┐
              │   ScreenshotApp     │
              │   (Main Controller) │
              └──────────┬──────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐ ┌───────▼──────┐ ┌───────▼──────┐
│DatabaseManager│ │TextExtractor │ │ChatbotEngine │
│              │ │              │ │              │
│• SQL DB      │ │• OCR         │ │• LangChain   │
│• Vector DB   │ │• LLM Vision  │ │• RAG Pipeline│
│• Sync Engine │ │• Preprocessing│ │• Multi-Modal │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## 2. Database Design

### 2.1 Entity Relationship Diagram

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   screenshots   │         │ extracted_text  │         │   metadata      │
├─────────────────┤         ├─────────────────┤         ├─────────────────┤
│ id (PK)         │◄────────┤ id (PK)         │         │ id (PK)         │
│ filename        │         │ screenshot_id   │         │ screenshot_id   │
│ capture_timestamp│         │ text_content    │         │ key             │
│ x_coordinate    │         │ confidence_score│         │ value           │
│ y_coordinate    │         │ processing_time │         │ created_at      │
│ width           │         │ created_at      │         └─────────────────┘
│ height          │         └─────────────────┘
│ extraction_method│
│ created_at      │
│ updated_at      │
└─────────────────┘
         │
         │
┌─────────────────┐         ┌─────────────────┐
│ vector_mappings │         │ conversations   │
├─────────────────┤         ├─────────────────┤
│ id (PK)         │         │ id (PK)         │
│ sql_id (FK)     │         │ session_id      │
│ vector_id       │         │ user_input      │
│ embedding_model │         │ bot_response    │
│ chunk_index     │         │ input_type      │
│ created_at      │         │ response_time   │
└─────────────────┘         │ created_at      │
                            └─────────────────┘
```

### 2.2 Database Schema Design

```sql
-- Core Screenshots Table
CREATE TABLE screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    capture_timestamp DATETIME NOT NULL,
    x_coordinate INTEGER,
    y_coordinate INTEGER,
    width INTEGER,
    height INTEGER,
    extraction_method VARCHAR(50), -- 'ocr', 'llm', 'none'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Extracted Text Table
CREATE TABLE extracted_text (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_id INTEGER,
    text_content TEXT,
    confidence_score FLOAT,
    processing_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (screenshot_id) REFERENCES screenshots(id)
);

-- Metadata Table
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_id INTEGER,
    key VARCHAR(100),
    value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (screenshot_id) REFERENCES screenshots(id)
);

-- Vector Database Mappings
CREATE TABLE vector_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sql_id INTEGER,
    vector_id VARCHAR(100),
    embedding_model VARCHAR(50),
    chunk_index INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sql_id) REFERENCES screenshots(id)
);

-- Chatbot Conversations
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(100),
    user_input TEXT,
    bot_response TEXT,
    input_type VARCHAR(20), -- 'text', 'voice', 'image'
    response_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. User Interface Design

### 3.1 Enhanced Capture Tab Features

The Capture Tab provides multiple input methods for data extraction and storage:

#### **3.1.1 Input Methods Section**
- **Screenshot Capture**: Traditional screen capture with area selection
- **File Upload**: Browse and select individual or multiple files
- **Text Input**: Direct text entry and article pasting
- **Drag & Drop**: Visual file dropping interface

#### **3.1.2 Drag & Drop Zone**
- **Visual Feedback**: Highlighted drop zone with file type icons
- **File Validation**: Real-time validation of supported file types
- **Progress Indicators**: Upload and processing progress bars
- **File List**: Scrollable list of selected files with status

#### **3.1.3 Supported File Types**
- **Documents**: .txt, .doc, .docx, .pdf, .md, .rtf
- **Spreadsheets**: .xlsx, .xls, .csv
- **Images**: .png, .jpg, .jpeg, .gif, .bmp, .tiff
- **Presentations**: .ppt, .pptx
- **Web Content**: .html, .htm

#### **3.1.4 Text Input Features**
- **Article Pasting**: Large text area for article content
- **Rich Text Support**: Preserve formatting when possible
- **Character Count**: Real-time character and word count
- **Auto-save**: Draft saving for long articles

#### **3.1.5 Enhanced File Processing Features**
- **Batch Processing**: Process multiple files simultaneously
- **Progress Tracking**: Real-time progress bars for each file
- **Error Handling**: Graceful handling of unsupported files
- **File Validation**: Size and format validation before processing
- **Duplicate Detection**: Prevent duplicate file processing
- **Processing Queue**: Manage file processing order and priority

#### **3.1.6 User Experience Enhancements**
- **Visual Feedback**: Color-coded status indicators
- **Keyboard Shortcuts**: Quick access to common functions
- **Context Menus**: Right-click options for file operations
- **Tooltips**: Helpful information on hover
- **Responsive Design**: Adapt to different screen sizes
- **Accessibility**: Support for screen readers and keyboard navigation

### 3.2 Three-Tab Interface Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    Screenshot Capture App                       │
├─────────────────────────────────────────────────────────────────┤
│ [📷 Capture] [📁 Management] [🤖 Chatbot]                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    CAPTURE TAB                              │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │System Status│  │Text Extract │  │  Auto Mode  │         │ │
│  │  │OCR: ✓       │  │○ None       │  │[🚀 Enable]  │         │ │
│  │  │LLM: ✓       │  │● OCR        │  │             │         │ │
│  │  │DB: ✓        │  │○ LLM        │  │             │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    Input Methods                        │ │ │
│  │  │┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │ │ │
│  │  ││  Screenshot │ │ File Upload │ │ Text Input  │         │ │ │
│  │  ││   Capture   │ │             │ │             │         │ │ │
│  │  ││[📷 Capture] │ │[📁 Browse]  │ │[📝 Paste]   │         │ │ │
│  │  ││[🎯 Area]    │ │[📂 Multiple]│ │[📄 Article] │         │ │ │
│  │  │└─────────────┘ └─────────────┘ └─────────────┘         │ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    Drag & Drop Zone                     │ │ │
│  │  │┌───────────────────────────────────────────────────────┐│ │ │
│  │  ││                                                       ││ │ │
│  │  ││  🗂️  Drag & Drop files here or click to browse       ││ │ │
│  │  ││                                                       ││ │ │
│  │  ││  Supported: .txt, .doc, .docx, .xlsx, .pdf, .md,     ││ │ │
│  │  ││  .png, .jpg, .jpeg, .gif, .bmp, .tiff               ││ │ │
│  │  ││                                                       ││ │ │
│  │  ││  [📁 Select Files] [🗑️ Clear All] [📋 File List]     ││ │ │
│  │  │└───────────────────────────────────────────────────────┘│ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │ Dimensions  │  │  Position   │  │   Output    │         │ │
│  │  │Width: [800] │  │X: [100]     │  │Dir: [./]    │         │ │
│  │  │Height:[600] │  │Y: [200]     │  │[Browse]     │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │   Controls  │  │   Preview   │  │Extracted Text│         │ │
│  │  │[📷 Capture] │  │┌───────────┐│  │┌───────────┐│         │ │
│  │  │[💾 Save]    │  ││           ││  ││           ││         │ │
│  │  │[📖 Read]    │  ││ Screenshot││  ││ Text Area ││         │ │
│  │  │[🗑️ Clear]   │  ││ Preview   ││  ││           ││         │ │
│  │  └─────────────┘  │└───────────┘│  │└───────────┘│         │ │
│  │                   └─────────────┘  └─────────────┘         │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Enhanced Capture Tab Detailed Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    Screenshot Capture App                       │
├─────────────────────────────────────────────────────────────────┤
│ [📷 Capture] [📁 Management] [🤖 Chatbot]                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    CAPTURE TAB - ENHANCED                   │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │System Status│  │Text Extract │  │  Auto Mode  │         │ │
│  │  │OCR: ✓       │  │○ None       │  │[🚀 Enable]  │         │ │
│  │  │LLM: ✓       │  │● OCR        │  │             │         │ │
│  │  │DB: ✓        │  │○ LLM        │  │             │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    Input Methods                        │ │ │
│  │  │┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │ │ │
│  │  ││  Screenshot │ │ File Upload │ │ Text Input  │         │ │ │
│  │  ││   Capture   │ │             │ │             │         │ │ │
│  │  ││[📷 Capture] │ │[📁 Browse]  │ │[📝 Paste]   │         │ │ │
│  │  ││[🎯 Area]    │ │[📂 Multiple]│ │[📄 Article] │         │ │ │
│  │  │└─────────────┘ └─────────────┘ └─────────────┘         │ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    Drag & Drop Zone                     │ │ │
│  │  │┌───────────────────────────────────────────────────────┐│ │ │
│  │  ││                                                       ││ │ │
│  │  ││  🗂️  Drag & Drop files here or click to browse       ││ │ │
│  │  ││                                                       ││ │ │
│  │  ││  Supported: .txt, .doc, .docx, .xlsx, .pdf, .md,     ││ │ │
│  │  ││  .png, .jpg, .jpeg, .gif, .bmp, .tiff               ││ │ │
│  │  ││                                                       ││ │ │
│  │  ││  [📁 Select Files] [🗑️ Clear All] [📋 File List]     ││ │ │
│  │  │└───────────────────────────────────────────────────────┘│ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    File Processing Status               │ │ │
│  │  │┌───────────────────────────────────────────────────────┐│ │ │
│  │  ││📄 document1.pdf    [██████████] 100% ✓ Processed     ││ │ │
│  │  ││📊 spreadsheet.xlsx [██████░░░░]  60% ⏳ Processing   ││ │ │
│  │  ││🖼️  image1.png      [░░░░░░░░░░]   0% ⏸️  Queued     ││ │ │
│  │  ││📝 article.txt      [████████░░]  80% ⏳ Processing   ││ │ │
│  │  │└───────────────────────────────────────────────────────┘│ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │ Dimensions  │  │  Position   │  │   Output    │         │ │
│  │  │Width: [800] │  │X: [100]     │  │Dir: [./]    │         │ │
│  │  │Height:[600] │  │Y: [200]     │  │[Browse]     │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │   Controls  │  │   Preview   │  │Extracted Text│         │ │
│  │  │[📷 Capture] │  │┌───────────┐│  │┌───────────┐│         │ │
│  │  │[💾 Save]    │  ││           ││  ││           ││         │ │
│  │  │[📖 Read]    │  ││ Screenshot││  ││ Text Area ││         │ │
│  │  │[🗑️ Clear]   │  ││ Preview   ││  ││           ││         │ │
│  │  └─────────────┘  │└───────────┘│  │└───────────┘│         │ │
│  │                   └─────────────┘  └─────────────┘         │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Management Tab Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    Screenshot Capture App                       │
├─────────────────────────────────────────────────────────────────┤
│ [📷 Capture] [📁 Management] [🤖 Chatbot]                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  MANAGEMENT TAB                             │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    File Browser                         │ │ │
│  │  │┌───────────────────────────────────────────────────────┐│ │ │
│  │  ││Filename    │Date       │SQL DB│Vector DB│Size        ││ │ │
│  │  │├───────────────────────────────────────────────────────┤│ │ │
│  │  ││screenshot_1│2025-08-05 │  ✓   │   ✓     │ 1.2MB      ││ │ │
│  │  ││screenshot_2│2025-08-05 │  ✓   │   ✓     │ 856KB      ││ │ │
│  │  ││screenshot_3│2025-08-05 │  ✓   │   ✗     │ 2.1MB      ││ │ │
│  │  │└───────────────────────────────────────────────────────┘│ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │   Controls  │  │   Search    │  │   Actions   │         │ │
│  │  │[🔄 Refresh] │  │[🔍 Search]  │  │[🗑️ Delete]  │         │ │
│  │  │[📤 Export]  │  │[Filter]     │  │[📋 Select]  │         │ │
│  │  │[💾 Backup]  │  │             │  │[📁 Archive] │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    File Preview                         │ │ │
│  │  │┌───────────┐  ┌───────────────────────────────────────┐│ │ │
│  │  ││           │  │              Metadata                  ││ │ │
│  │  ││ Screenshot│  │• Filename: screenshot_1.png           ││ │ │
│  │  ││   Image   │  │• Captured: 2025-08-05 14:30:25       ││ │ │
│  │  ││           │  │• Dimensions: 800x600                  ││ │ │
│  │  ││           │  │• Position: (100, 200)                 ││ │ │
│  │  ││           │  │• Extraction: OCR                      ││ │ │
│  │  │└───────────┘  └───────────────────────────────────────┘│ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Chatbot Tab Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    Screenshot Capture App                       │
├─────────────────────────────────────────────────────────────────┤
│ [📷 Capture] [📁 Management] [🤖 Chatbot]                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    CHATBOT TAB                              │ │
│  │                                                             │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    Chat Display                         │ │ │
│  │  │┌───────────────────────────────────────────────────────┐│ │ │
│  │  ││🤖 Bot: Hello! I'm your WMS assistant. How can I help?││ │ │
│  │  ││                                                       ││ │ │
│  │  ││👤 User: Show me inventory levels for zone A          ││ │ │
│  │  ││                                                       ││ │ │
│  │  ││🤖 Bot: Based on the latest data, Zone A inventory:   ││ │ │
│  │  ││    • Product A: 150 units                             ││ │ │
│  │  ││    • Product B: 75 units                              ││ │ │
│  │  ││    • Product C: 200 units                             ││ │ │
│  │  ││                                                       ││ │ │
│  │  ││📊 [Chart showing inventory levels]                    ││ │ │
│  │  │└───────────────────────────────────────────────────────┘│ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌───────────────────────────────────────┐ │ │
│  │  │   Input     │  │              Controls                 │ │ │
│  │  │○ Text       │  │[🗑️ Clear Chat] [📤 Export] [💾 Save] │ │ │
│  │  │● Voice      │  │                                        │ │ │
│  │  │○ Image      │  │[🎤 Record] [🖼️ Upload] [➤ Send]      │ │ │
│  │  │             │  │                                        │ │ │
│  │  │┌───────────┐│  │                                        │ │ │
│  │  ││Type your  ││  │                                        │ │ │
│  │  ││message... ││  │                                        │ │ │
│  │  │└───────────┘│  │                                        │ │ │
│  │  └─────────────┘  └───────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. AI and Chatbot Architecture

### 4.1 RAG Pipeline Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   User      │    │ Multi-Modal │    │  RAG        │    │   Response  │
│   Input     │───▶│  Processor  │───▶│  Pipeline   │───▶│  Generator  │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │ Text        │    │ Vector      │    │ Rich        │
                   │ Conversion  │    │ Search      │    │ Output      │
                   │             │    │             │    │ Display     │
                   └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                     ┌─────────────┐
                                     │ Document    │
                                     │ Retrieval   │
                                     │             │
                                     └─────────────┘
```

### 4.2 Multi-Modal Input Processing

```
┌─────────────┐
│   Input     │
│  Sources    │
└─────┬───────┘
      │
      ├─────────────┬─────────────┬─────────────┐
      │             │             │             │
      ▼             ▼             ▼             ▼
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│  Text   │   │  Voice  │   │  Image  │   │  File   │
│ Input   │   │ Input   │   │ Input   │   │ Upload  │
└────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘
     │             │             │             │
     │             ▼             ▼             │
     │      ┌─────────────┐ ┌─────────────┐   │
     │      │   Whisper   │ │   OCR/LLM   │   │
     │      │ Speech-to-  │ │ Text        │   │
     │      │ Text        │ │ Extraction  │   │
     │      └─────────────┘ └─────────────┘   │
     │             │             │             │
     └─────────────┼─────────────┼─────────────┘
                   ▼             ▼
            ┌─────────────────────────┐
            │   Text Normalization    │
            │   and Preprocessing     │
            └─────────────┬───────────┘
                          │
                          ▼
            ┌─────────────────────────┐
            │   RAG Query Processing  │
            └─────────────────────────┘
```

### 4.3 Conversation Management Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   User      │    │ Conversation│    │  Context    │    │   Memory    │
│   Message   │───▶│  Manager    │───▶│  Builder    │───▶│  Storage    │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │ Session     │    │ Context     │    │ Conversation│
                   │ Management  │    │ Window      │    │ History     │
                   │             │    │ Control     │    │             │
                   └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                     ┌─────────────┐
                                     │   RAG       │
                                     │  Query      │
                                     │             │
                                     └─────────────┘
```

---

## 5. Data Flow Diagrams

### 5.1 Enhanced Data Capture and Storage Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Multiple  │    │ File Type   │    │ Content     │    │   Database  │
│   Input     │───▶│  Detection  │───▶│ Extraction  │───▶│   Storage   │
│   Sources   │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│• Screenshot │    │• Document   │    │• OCR        │    │• SQL DB     │
│• File Upload│    │• Image      │    │• LLM Vision │    │ (Metadata)  │
│• Drag & Drop│    │• Text       │    │• Text Parse │    │             │
│• Text Paste │    │• Spreadsheet│    │• PDF Extract│    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │                   │
                                              ▼                   ▼
                                     ┌─────────────┐    ┌─────────────┐
                                     │   Unified   │    │   Vector    │
                                     │   Content   │    │    DB       │
                                     │   Storage   │    │ (Embeddings)│
                                     └─────────────┘    └─────────────┘
                                              │                   │
                                              └─────────┬─────────┘
                                                        ▼
                                               ┌─────────────┐
                                               │   Sync      │
                                               │  Engine     │
                                               │             │
                                               └─────────────┘
```

### 5.1.1 Multi-Input Processing Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Input Processing Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Input     │    │   File      │    │  Content    │        │
│  │  Detection  │───▶│  Validation │───▶│  Extraction │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│           │                   │                   │            │
│           ▼                   ▼                   ▼            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │• Screenshot │    │• File Type  │    │• OCR Engine │        │
│  │• File Drop  │    │• Size Check │    │• LLM Vision │        │
│  │• Text Paste │    │• Format     │    │• PDF Parser │        │
│  │• Browse     │    │  Validation │    │• Doc Parser │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Progress  │    │   Error     │    │   Success   │        │
│  │  Tracking   │    │  Handling   │    │  Storage    │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Chatbot Query Processing Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   User      │    │ Multi-Modal │    │   RAG       │    │   Response  │
│   Query     │───▶│  Processor  │───▶│  Pipeline   │───▶│  Generator  │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │   Text      │    │   Vector    │    │   Rich      │
                   │ Conversion  │    │   Search    │    │   Output    │
                   │             │    │             │    │   Display   │
                   └─────────────┘    └─────────────┘    └─────────────┘
                                              │                   │
                                              ▼                   ▼
                                     ┌─────────────┐    ┌─────────────┐
                                     │ Document    │    │   Context   │
                                     │ Retrieval   │    │  Management │
                                     │             │    │             │
                                     └─────────────┘    └─────────────┘
                                              │                   │
                                              └─────────┬─────────┘
                                                        ▼
                                               ┌─────────────┐
                                               │   Memory    │
                                               │  Storage    │
                                               │             │
                                               └─────────────┘
```

---

## 6. Component Design

### 6.1 Core Classes and Relationships

```python
# Main Application Class
class ScreenshotApp:
    def __init__(self):
        self.ui_manager = UIManager()
        self.database_manager = DatabaseManager()
        self.chatbot_engine = ChatbotEngine()
        self.file_manager = FileManager()
        self.text_extractor = TextExtractor()
        self.file_processor = FileProcessor()
        self.drag_drop_handler = DragDropHandler()

# Enhanced File Processing
class FileProcessor:
    def __init__(self):
        self.supported_formats = {
            'documents': ['.txt', '.doc', '.docx', '.pdf', '.md', '.rtf'],
            'spreadsheets': ['.xlsx', '.xls', '.csv'],
            'images': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'],
            'presentations': ['.ppt', '.pptx'],
            'web': ['.html', '.htm']
        }
        self.extractors = {
            'pdf': PDFExtractor(),
            'doc': DocExtractor(),
            'xlsx': ExcelExtractor(),
            'image': ImageExtractor(),
            'text': TextExtractor()
        }

class DragDropHandler:
    def __init__(self):
        self.drop_zone = DropZone()
        self.file_validator = FileValidator()
        self.progress_tracker = ProgressTracker()
        self.file_list = FileList()

# Database Management
class DatabaseManager:
    def __init__(self):
        self.sql_db = SQLDatabase()
        self.vector_db = VectorDatabase()
        self.sync_engine = DataSyncEngine()

# Chatbot Engine
class ChatbotEngine:
    def __init__(self):
        self.llm = self.setup_llm()
        self.embeddings = self.setup_embeddings()
        self.vectorstore = self.setup_vectorstore()
        self.rag_chain = self.setup_rag_chain()
        self.conversation_manager = ConversationManager()

# Multi-Modal Processor
class MultiModalProcessor:
    def __init__(self):
        self.speech_recognizer = self.setup_speech_recognition()
        self.image_processor = self.setup_image_processing()
        self.text_processor = self.setup_text_processing()
        self.file_processor = self.setup_file_processing()
```

### 6.2 Interface Design Patterns

```python
# Observer Pattern for UI Updates
class UIObserver:
    def update(self, event_type, data):
        pass

class ScreenshotApp(UIObserver):
    def update(self, event_type, data):
        if event_type == "screenshot_captured":
            self.update_preview(data)
        elif event_type == "text_extracted":
            self.update_text_area(data)
        elif event_type == "database_updated":
            self.update_status(data)

# Strategy Pattern for Text Extraction
class TextExtractionStrategy:
    def extract_text(self, image):
        pass

class OCRExtractionStrategy(TextExtractionStrategy):
    def extract_text(self, image):
        # OCR implementation
        pass

class LLMExtractionStrategy(TextExtractionStrategy):
    def extract_text(self, image):
        # LLM implementation
        pass

# Factory Pattern for Input Processing
class InputProcessorFactory:
    @staticmethod
    def create_processor(input_type):
        if input_type == "text":
            return TextProcessor()
        elif input_type == "voice":
            return VoiceProcessor()
        elif input_type == "image":
            return ImageProcessor()
        elif input_type == "file":
            return FileProcessor()
        elif input_type == "document":
            return DocumentProcessor()

# Enhanced File Processing Components
class FileProcessor:
    def __init__(self):
        self.processors = {
            '.pdf': PDFProcessor(),
            '.doc': DocProcessor(),
            '.docx': DocxProcessor(),
            '.xlsx': ExcelProcessor(),
            '.txt': TextProcessor(),
            '.md': MarkdownProcessor(),
            '.html': HTMLProcessor()
        }
        self.queue_manager = ProcessingQueueManager()
        self.progress_tracker = ProgressTracker()

class DragDropHandler:
    def __init__(self):
        self.drop_zone = DropZone()
        self.file_validator = FileValidator()
        self.batch_processor = BatchProcessor()
        self.error_handler = ErrorHandler()

class ProcessingQueueManager:
    def __init__(self):
        self.queue = []
        self.active_processes = []
        self.max_concurrent = 3
        self.priority_queue = PriorityQueue()
```

---

## 7. Security and Performance Design

### 7.1 Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Security Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  API Key Management │  Data Encryption │  Access Control       │
│  • Environment      │  • At Rest       │  • Local Only         │
│    Variables        │  • In Transit    │  • No Network         │
│  • Secure Storage   │  • Database      │    Access             │
│  • No Hardcoding    │    Encryption    │  • File Permissions   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                        │
├─────────────────────────────────────────────────────────────────┤
│  Input Validation │  Error Handling │  Logging & Monitoring    │
│  • Sanitization   │  • Graceful     │  • Audit Trail           │
│  • Type Checking  │    Degradation  │  • Performance Metrics   │
│  • Size Limits    │  • User Feedback│  • Error Tracking        │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Performance Optimization

```
┌─────────────────────────────────────────────────────────────────┐
│                      Performance Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  Caching Strategy │  Async Processing │  Resource Management    │
│  • Query Cache    │  • Non-blocking   │  • Memory Pool          │
│  • Result Cache   │    Operations     │  • Connection Pool      │
│  • Image Cache    │  • Background     │  • Garbage Collection   │
│  • Embedding Cache│    Tasks          │  • Resource Limits      │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        Optimization Layer                       │
├─────────────────────────────────────────────────────────────────┤
│  Database Indexing│  Vector Search   │  UI Responsiveness      │
│  • Primary Keys   │  • Efficient      │  • Event-driven         │
│  • Foreign Keys   │    Indexing       │  • Background Threads   │
│  • Query          │  • Approximate    │  • Progressive Loading  │
│    Optimization   │    Search         │  • Lazy Loading         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Deployment Architecture

### 8.1 Development Environment

```
┌─────────────────────────────────────────────────────────────────┐
│                    Development Environment                      │
├─────────────────────────────────────────────────────────────────┤
│  Source Code      │  Dependencies    │  Configuration          │
│  • Python Files   │  • requirements.txt│  • .env files         │
│  • UI Resources   │  • Virtual Env   │  • config.json         │
│  • Documentation  │  • Local DBs     │  • Log Files           │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        Build Process                            │
├─────────────────────────────────────────────────────────────────┤
│  Testing          │  Packaging       │  Distribution           │
│  • Unit Tests     │  • PyInstaller   │  • Executable           │
│  • Integration    │  • Dependencies  │  • Installer            │
│  • Performance    │  • Resources     │  • Documentation        │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Production Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    Production Environment                       │
├─────────────────────────────────────────────────────────────────┤
│  Application      │  Data Storage    │  Monitoring             │
│  • Executable     │  • SQL Database  │  • Log Files            │
│  • Configuration  │  • Vector DB     │  • Performance Metrics  │
│  • Resources      │  • File System   │  • Error Tracking       │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        User Environment                         │
├─────────────────────────────────────────────────────────────────┤
│  Installation     │  Configuration   │  Usage                  │
│  • Setup Wizard   │  • Environment   │  • Screenshot Capture   │
│  • Dependencies   │    Variables     │  • Database Operations  │
│  • Permissions    │  • API Keys      │  • Chatbot Interaction  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Testing Strategy

### 9.1 Testing Pyramid

```
                    ┌─────────────────┐
                    │   E2E Tests     │
                    │   (10%)         │
                    └─────────────────┘
                           │
                    ┌─────────────────┐
                    │ Integration     │
                    │ Tests (20%)     │
                    └─────────────────┘
                           │
                    ┌─────────────────┐
                    │   Unit Tests    │
                    │   (70%)         │
                    └─────────────────┘
```

### 9.2 Test Coverage Areas

```
┌─────────────────────────────────────────────────────────────────┐
│                        Test Coverage                            │
├─────────────────────────────────────────────────────────────────┤
│  Unit Tests       │  Integration Tests │  E2E Tests            │
│  • Database       │  • Database        │  • Complete Workflow   │
│    Operations     │    Integration     │  • UI Interactions     │
│  • Text           │  • API Integration │  • Cross-tab           │
│    Extraction     │  • File Operations │    Communication      │
│  • Chatbot        │  • Data Sync       │  • Error Scenarios     │
│    Logic          │  • UI Components   │  • Performance Tests   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Conclusion

This design document provides a comprehensive blueprint for implementing the enhanced Screenshot Capture App with WMS chatbot functionality. Key design principles include:

1. **Modular Architecture**: Clean separation of concerns with well-defined interfaces
2. **Scalable Design**: Support for growing data and user requirements
3. **Performance Optimization**: Sub-second response times for critical operations
4. **Security First**: Local processing, secure storage, and data protection
5. **User Experience**: Intuitive interface with seamless workflows

The design emphasizes maintainability, extensibility, and reliability while ensuring optimal performance and user satisfaction.

---

**Document End** 