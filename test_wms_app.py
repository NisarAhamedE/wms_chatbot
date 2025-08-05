#!/usr/bin/env python3
"""
Test script for WMS Screenshot & Document Management System
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing module imports...")
    
    try:
        from modules.config_manager import ConfigManager
        print("✓ ConfigManager imported successfully")
        
        from modules.logger import setup_logger
        print("✓ Logger imported successfully")
        
        from modules.database_manager import DatabaseManager
        print("✓ DatabaseManager imported successfully")
        
        from modules.file_processor import FileProcessor
        print("✓ FileProcessor imported successfully")
        
        from modules.chatbot_manager import ChatbotManager
        print("✓ ChatbotManager imported successfully")
        
        from modules.ui_components import CaptureTab, ManagementTab, ChatbotTab
        print("✓ UI components imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_config_manager():
    """Test configuration manager"""
    print("\nTesting ConfigManager...")
    
    try:
        from modules.config_manager import ConfigManager
        config = ConfigManager()
        print("✓ ConfigManager initialized successfully")
        
        # Test configuration methods
        azure_config = config.get_azure_config()
        print(f"✓ Azure config retrieved: {bool(azure_config['api_key'])}")
        
        file_config = config.get_file_processing_config()
        print(f"✓ File processing config retrieved: {len(file_config['supported_formats'])} formats")
        
        return True
        
    except Exception as e:
        print(f"✗ ConfigManager error: {e}")
        return False

def test_database_manager():
    """Test database manager"""
    print("\nTesting DatabaseManager...")
    
    try:
        from modules.database_manager import DatabaseManager
        db_manager = DatabaseManager()
        print("✓ DatabaseManager initialized successfully")
        
        # Test database operations
        stats = db_manager.get_database_stats()
        print(f"✓ Database stats retrieved: {stats['total_documents']} documents")
        
        db_manager.close()
        print("✓ DatabaseManager closed successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ DatabaseManager error: {e}")
        return False

def test_file_processor():
    """Test file processor"""
    print("\nTesting FileProcessor...")
    
    try:
        from modules.database_manager import DatabaseManager
        from modules.file_processor import FileProcessor
        db_manager = DatabaseManager()
        
        file_processor = FileProcessor(db_manager)
        print("✓ FileProcessor initialized successfully")
        
        # Test supported formats
        formats = file_processor.get_supported_formats()
        print(f"✓ Supported formats: {len(formats['documents'])} document types")
        
        db_manager.close()
        return True
        
    except Exception as e:
        print(f"✗ FileProcessor error: {e}")
        return False

def test_chatbot_manager():
    """Test chatbot manager"""
    print("\nTesting ChatbotManager...")
    
    try:
        from modules.database_manager import DatabaseManager
        from modules.chatbot_manager import ChatbotManager
        db_manager = DatabaseManager()
        
        chatbot_manager = ChatbotManager(db_manager)
        print("✓ ChatbotManager initialized successfully")
        
        # Test placeholder response
        response = chatbot_manager.process_query("test query")
        print(f"✓ Chatbot response generated: {response['success']}")
        
        chatbot_manager.close()
        db_manager.close()
        return True
        
    except Exception as e:
        print(f"✗ ChatbotManager error: {e}")
        return False

def test_ui_components():
    """Test UI components"""
    print("\nTesting UI Components...")
    
    try:
        import tkinter as tk
        from modules.database_manager import DatabaseManager
        from modules.file_processor import FileProcessor
        from modules.chatbot_manager import ChatbotManager
        from modules.ui_components import ProgressTracker
        
        # Create root window for testing
        root = tk.Tk()
        root.withdraw()  # Hide the window
        
        # Initialize managers
        db_manager = DatabaseManager()
        file_processor = FileProcessor(db_manager)
        chatbot_manager = ChatbotManager(db_manager)
        progress_tracker = ProgressTracker()
        
        print("✓ UI components initialized successfully")
        
        # Cleanup
        chatbot_manager.close()
        db_manager.close()
        root.destroy()
        
        return True
        
    except Exception as e:
        print(f"✗ UI components error: {e}")
        return False

def main():
    """Run all tests"""
    print("WMS Screenshot & Document Management System - Test Suite")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration Manager", test_config_manager),
        ("Database Manager", test_database_manager),
        ("File Processor", test_file_processor),
        ("Chatbot Manager", test_chatbot_manager),
        ("UI Components", test_ui_components)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} PASSED")
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The application is ready to run.")
        print("\nTo start the application, run:")
        print("python run_wms_app.py")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\nCommon solutions:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Install Tesseract OCR")
        print("3. Configure Azure OpenAI (optional)")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 