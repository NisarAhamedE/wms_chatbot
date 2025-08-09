import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import threading
import queue
import asyncio
from typing import Dict, List, Optional, Any

# Import custom modules
from modules.database_manager import DatabaseManager
from modules.file_processor import FileProcessor
from modules.chatbot_manager import ChatbotManager
from modules.backup_scheduler import BackupScheduler
from modules.ui_components import (
    CaptureTab, ManagementTab, ChatbotTab,
    DragDropHandler, ProgressTracker
)
from modules.config_manager import ConfigManager
from modules.logger import setup_logger

class WMSScreenshotApp:
    """
    Main WMS Screenshot Application with enhanced three-tab interface
    """
    
    def __init__(self):
        self.root = tk.Tk()
        self.setup_main_window()
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.file_processor = FileProcessor(self.db_manager)
        self.chatbot_manager = ChatbotManager(self.db_manager)
        self.backup_scheduler = BackupScheduler(self.db_manager, self.config_manager)
        
        # Setup logging
        self.logger = setup_logger()
        
        # Start backup scheduler
        self.backup_scheduler.start()
        
        # Initialize data structures
        self.processing_queue = queue.Queue()
        self.progress_tracker = ProgressTracker()
        
        # Initialize UI components
        self.setup_ui()
        
        # Start background processing
        self.start_background_processing()
    
    def setup_main_window(self):
        """Configure main window properties"""
        self.root.title("WMS Screenshot & Document Management System")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Center window
        self.center_window()
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_ui(self):
        """Setup the main UI"""
        # Create main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.chatbot_tab = ChatbotTab(
            self.notebook, 
            self.chatbot_manager
        )
        
        self.capture_tab = CaptureTab(
            self.notebook, 
            self.file_processor, 
            self.progress_tracker,
            self.processing_queue
        )
        
        self.management_tab = ManagementTab(
            self.notebook, 
            self.db_manager, 
            self.file_processor
        )
        
        # Add tabs to notebook with WMS Chatbot as default
        self.notebook.add(self.chatbot_tab, text="🤖 WMS Chatbot")
        self.notebook.add(self.capture_tab, text="📸 Capture")
        self.notebook.add(self.management_tab, text="📁 Management")
        
        # Select WMS Chatbot tab by default
        self.notebook.select(0)
        
        # Bind tab change events
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Create status bar
        self.create_status_bar()
    
    def setup_styles(self):
        """Configure modern dark theme styles"""
        style = ttk.Style()
        
        # Configure dark theme colors
        style.configure('.',
            background='#1e1e2d',
            foreground='white',
            fieldbackground='#2d2d3f'
        )
        
        # Dark frame
        style.configure('Dark.TFrame',
            background='#1e1e2d'
        )
        
        # Card frame
        style.configure('Card.TFrame',
            background='#2d2d3f',
            relief='solid',
            borderwidth=1
        )
        
        # Card labelframe
        style.configure('Card.TLabelframe',
            background='#2d2d3f',
            foreground='white',
            relief='solid',
            borderwidth=1
        )
        style.configure('Card.TLabelframe.Label',
            background='#2d2d3f',
            foreground='white',
            font=('Segoe UI', 11, 'bold')
        )
        
        # Card title
        style.configure('CardTitle.TLabel',
            background='#2d2d3f',
            foreground='white',
            font=('Segoe UI', 11)
        )
        
        # Card value
        style.configure('CardValue.TLabel',
            background='#2d2d3f',
            foreground='white',
            font=('Segoe UI', 20, 'bold')
        )
        
        # Storage text
        style.configure('StorageText.TLabel',
            background='#1e1e2d',
            foreground='white',
            font=('Segoe UI', 16, 'bold'),
            justify='center'
        )
        
        # Notebook
        style.configure('TNotebook',
            background='#1e1e2d',
            borderwidth=0
        )
        style.configure('TNotebook.Tab',
            background='#2d2d3f',
            foreground='white',
            padding=[10, 5],
            font=('Segoe UI', 10)
        )
        style.map('TNotebook.Tab',
            background=[('selected', '#1a73e8')],
            foreground=[('selected', 'white')]
        )
        
        # Buttons
        style.configure('TButton',
            background='#1a73e8',
            foreground='white',
            padding=[10, 5],
            font=('Segoe UI', 10)
        )
        style.map('TButton',
            background=[('active', '#1557b0')]
        )
    
    def create_status_bar(self):
        """Create status bar at bottom of window"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Ready", 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_label.pack(fill=tk.X)
        
        # Progress bar for background tasks
        self.progress_bar = ttk.Progressbar(
            self.status_frame, 
            mode='indeterminate'
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
    
    def on_tab_changed(self, event):
        """Handle tab change events"""
        current_tab = self.notebook.select()
        tab_id = self.notebook.index(current_tab)
        
        if tab_id == 0:  # Dashboard tab
            self.status_label.config(text="Dashboard - System Overview")
        elif tab_id == 1:  # Chatbot tab
            self.status_label.config(text="WMS Chatbot - Ready for queries")
        elif tab_id == 2:  # Capture tab
            self.status_label.config(text="Capture tab - Ready to process documents")
        elif tab_id == 3:  # Management tab
            self.status_label.config(text="Management tab - Managing stored documents")
            self.management_tab.refresh_file_list()
    
    def start_background_processing(self):
        """Start background processing thread"""
        self.processing_thread = threading.Thread(
            target=self.process_queue, 
            daemon=True
        )
        self.processing_thread.start()
    
    def process_queue(self):
        """Process items in the processing queue"""
        while True:
            try:
                item = self.processing_queue.get(timeout=1)
                if item is None:
                    break
                
                # Process the item
                self.handle_processing_item(item)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing queue item: {e}")
    
    def handle_processing_item(self, item):
        """Handle individual processing items"""
        try:
            item_type = item.get('type')
            
            if item_type == 'file':
                self.process_file_item(item)
            elif item_type == 'text':
                self.process_text_item(item)
            elif item_type == 'screenshot':
                self.process_screenshot_item(item)
                
        except Exception as e:
            self.logger.error(f"Error handling processing item: {e}")
            self.update_status(f"Error: {str(e)}")
    
    def process_file_item(self, item):
        """Process file upload item"""
        file_path = item['file_path']
        callback = item.get('callback')
        
        try:
            # Update status
            self.update_status(f"Processing file: {os.path.basename(file_path)}")
            
            # Process file
            result = self.file_processor.process_file(file_path)
            
            # Call callback if provided
            if callback:
                self.root.after(0, lambda: callback(result))
            
            self.update_status(f"Completed: {os.path.basename(file_path)}")
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            self.update_status(f"Error processing {os.path.basename(file_path)}")
    
    def process_text_item(self, item):
        """Process text input item"""
        text = item['text']
        metadata = item.get('metadata', {})
        callback = item.get('callback')
        
        try:
            # Update status
            self.update_status("Processing text input...")
            
            # Process text
            result = self.file_processor.process_text(text, metadata)
            
            # Call callback if provided
            if callback:
                self.root.after(0, lambda: callback(result))
            
            self.update_status("Text processing completed")
            
        except Exception as e:
            self.logger.error(f"Error processing text: {e}")
            self.update_status("Error processing text")
    
    def process_screenshot_item(self, item):
        """Process screenshot item"""
        screenshot_path = item['screenshot_path']
        callback = item.get('callback')
        
        try:
            # Update status
            self.update_status("Processing screenshot...")
            
            # Process screenshot
            result = self.file_processor.process_screenshot(screenshot_path)
            
            # Call callback if provided
            if callback:
                self.root.after(0, lambda: callback(result))
            
            self.update_status("Screenshot processing completed")
            
        except Exception as e:
            self.logger.error(f"Error processing screenshot: {e}")
            self.update_status("Error processing screenshot")
    
    def update_status(self, message):
        """Update status bar message"""
        def update():
            self.status_label.config(text=message)
        
        self.root.after(0, update)
    
    def show_progress(self, show=True):
        """Show/hide progress bar"""
        def update():
            if show:
                self.progress_bar.start()
            else:
                self.progress_bar.stop()
        
        self.root.after(0, update)
    
    def run(self):
        """Start the application"""
        try:
            self.logger.info("Starting WMS Screenshot Application")
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            messagebox.showerror("Error", f"Application error: {str(e)}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources before exit"""
        try:
            self.logger.info("Cleaning up application resources")
            
            # Stop background processing
            self.processing_queue.put(None)
            
            # Stop backup scheduler
            if hasattr(self, 'backup_scheduler'):
                self.backup_scheduler.stop()
            
            # Close database connections
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
            
            # Close chatbot
            if hasattr(self, 'chatbot_manager'):
                self.chatbot_manager.close()
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

def main():
    """Main entry point"""
    try:
        app = WMSScreenshotApp()
        app.run()
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 