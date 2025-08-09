import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import threading
import queue
import random
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import time
from datetime import datetime

from .logger import LoggerMixin
from .theme_manager import ThemeManager

class ProgressTracker(LoggerMixin):
    """Track progress of file processing operations"""
    
    def __init__(self):
        super().__init__()
        self.current_task = None
        self.progress = 0
        self.total = 0
        self.status = "idle"
        self.callbacks = []
    
    def start_task(self, task_name: str, total: int):
        """Start a new task"""
        self.current_task = task_name
        self.total = total
        self.progress = 0
        self.status = "running"
        self._notify_callbacks()
    
    def update_progress(self, progress: int):
        """Update progress"""
        self.progress = progress
        self._notify_callbacks()
    
    def complete_task(self):
        """Mark task as complete"""
        self.progress = self.total
        self.status = "completed"
        self._notify_callbacks()
    
    def add_callback(self, callback: Callable):
        """Add progress callback"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self):
        """Notify all callbacks of progress update"""
        for callback in self.callbacks:
            try:
                callback(self.current_task, self.progress, self.total, self.status)
            except Exception as e:
                self.log_error(f"Error in progress callback: {e}")


class DragDropHandler(LoggerMixin):
    """Handle drag and drop functionality"""
    
    def __init__(self, parent, on_files_dropped: Callable):
        super().__init__()
        self.parent = parent
        self.on_files_dropped = on_files_dropped
        self.drop_zone = None
        self.setup_drop_zone()
    
    def setup_drop_zone(self):
        """Setup drop zone for files"""
        self.drop_zone = tk.Frame(self.parent, relief=tk.RAISED, borderwidth=2)
        self.drop_zone.configure(bg='lightblue', height=200)
        
        # Drop zone label
        label = tk.Label(
            self.drop_zone, 
            text="Drag & Drop files here\nor click to browse",
            font=('Arial', 12),
            bg='lightblue'
        )
        label.pack(expand=True)
        
        # Bind events
        self.drop_zone.bind('<Button-1>', self.on_click)
        self.drop_zone.bind('<Enter>', self.on_enter)
        self.drop_zone.bind('<Leave>', self.on_leave)
        
        # Note: Full drag & drop requires tkinterdnd2 library
        # For now, we'll use click-to-browse functionality
    
    def on_click(self, event):
        """Handle click on drop zone"""
        files = filedialog.askopenfilenames(
            title="Select files to process",
            filetypes=[
                ("All supported", "*.pdf *.doc *.docx *.txt *.md *.xlsx *.xls *.csv *.png *.jpg *.jpeg *.gif *.bmp *.tiff *.html *.htm"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.doc *.docx"),
                ("Text files", "*.txt *.md"),
                ("Excel files", "*.xlsx *.xls *.csv"),
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff"),
                ("Web files", "*.html *.htm"),
                ("All files", "*.*")
            ]
        )
        if files:
            self.on_files_dropped(files)
    
    def on_enter(self, event):
        """Handle mouse enter"""
        # Use a subtle color change without flickering
        self.drop_zone.configure(bg='#e6f3ff')  # Light blue with less contrast
    
    def on_leave(self, event):
        """Handle mouse leave"""
        self.drop_zone.configure(bg='#f0f0f0')  # Light gray background


class CaptureTab(ttk.Frame, LoggerMixin):
    """Capture tab for file upload and text input"""
    
    def __init__(self, parent, file_processor, progress_tracker, processing_queue):
        super().__init__(parent)
        LoggerMixin.__init__(self)
        
        self.file_processor = file_processor
        self.progress_tracker = progress_tracker
        self.processing_queue = processing_queue
        
        self.setup_ui()
        self.log_info("Capture tab initialized")
    
    def setup_ui(self):
        """Setup the capture tab UI"""
        # Apply theme
        ThemeManager.setup_theme()
        
        # Main container with background color
        main_frame = ttk.Frame(self, style='Group.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Title with improved styling
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ttk.Label(
            title_frame,
            text="Document Capture & Processing",
            style='Title.TLabel'
        )
        title_label.pack(side=tk.LEFT)
        
        # Subtitle
        subtitle_label = ttk.Label(
            title_frame,
            text="Upload, input text, or capture screenshots",
            style='Subtitle.TLabel'
        )
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Create notebook for different input methods with custom style
        self.input_notebook = ttk.Notebook(main_frame)
        self.input_notebook.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Screenshot tab (first and default)
        self.create_screenshot_tab()
        
        # File upload tab
        self.create_file_upload_tab()
        
        # Text input tab
        self.create_text_input_tab()
        
        # Select screenshot tab by default
        self.input_notebook.select(0)
        
        # Processing status in a separate group
        self.create_status_section(main_frame)
    
    def create_file_upload_tab(self):
        """Create file upload tab"""
        file_frame = ttk.Frame(self.input_notebook)
        self.input_notebook.add(file_frame, text="📁 File Upload")
        
        # Upload section in blue group
        upload_frame = ttk.LabelFrame(
            file_frame,
            text="Upload Files",
            style='BlueGroup.TLabelframe'
        )
        upload_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Drag & drop zone with improved styling
        self.drag_drop = DragDropHandler(upload_frame, self.process_files)
        self.drag_drop.drop_zone.configure(
            bg=ThemeManager.get_color('group_blue'),
            relief='solid',
            borderwidth=1
        )
        self.drag_drop.drop_zone.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # File list in green group
        self.file_list_frame = ttk.LabelFrame(
            file_frame,
            text="Selected Files",
            style='GreenGroup.TLabelframe'
        )
        self.file_list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(self.file_list_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.file_listbox = tk.Listbox(
            list_frame,
            height=8,
            bg=ThemeManager.get_color('surface'),
            fg=ThemeManager.get_color('text'),
            selectbackground=ThemeManager.get_color('primary'),
            selectforeground=ThemeManager.get_color('surface'),
            font=('Segoe UI', 10)
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons in a styled frame
        button_frame = ttk.Frame(file_frame)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(
            button_frame,
            text="Add Files",
            style='Primary.TButton',
            command=self.browse_files
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame,
            text="Clear List",
            style='Secondary.TButton',
            command=self.clear_file_list
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame,
            text="Process Files",
            style='Success.TButton',
            command=self.process_selected_files
        ).pack(side=tk.RIGHT)
    
    def create_text_input_tab(self):
        """Create text input tab"""
        text_frame = ttk.Frame(self.input_notebook)
        self.input_notebook.add(text_frame, text="📝 Text Input")
        
        # Text input area in purple group
        input_frame = ttk.LabelFrame(
            text_frame,
            text="Text Input",
            style='PurpleGroup.TLabelframe'
        )
        input_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Instructions
        text_label = ttk.Label(
            input_frame,
            text="Enter or paste text content:",
            style='Subtitle.TLabel'
        )
        text_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # Text area with scrollbar in styled container
        text_container = ttk.Frame(input_frame)
        text_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.text_input = scrolledtext.ScrolledText(
            text_container,
            height=15,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg=ThemeManager.get_color('surface'),
            fg=ThemeManager.get_color('text'),
            insertbackground=ThemeManager.get_color('primary')
        )
        self.text_input.pack(fill=tk.BOTH, expand=True)
        
        # Stats in orange group
        stats_frame = ttk.LabelFrame(
            text_frame,
            text="Statistics",
            style='OrangeGroup.TLabelframe'
        )
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Character/word count with improved styling
        self.text_stats_label = ttk.Label(
            stats_frame,
            text="Characters: 0 | Words: 0",
            style='Subtitle.TLabel'
        )
        self.text_stats_label.pack(anchor=tk.W, padx=10, pady=5)
        
        # Bind text change event
        self.text_input.bind('<KeyRelease>', self.update_text_stats)
        
        # Buttons in styled frame
        button_frame = ttk.Frame(text_frame)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(
            button_frame,
            text="Clear Text",
            style='Secondary.TButton',
            command=self.clear_text
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame,
            text="Process Text",
            style='Primary.TButton',
            command=self.process_text
        ).pack(side=tk.RIGHT)
    
    def create_screenshot_tab(self):
        """Create screenshot tab"""
        screenshot_frame = ttk.Frame(self.input_notebook)
        self.input_notebook.add(screenshot_frame, text="📸 Screenshot")
        
        # Quick capture controls in blue group
        quick_frame = ttk.LabelFrame(
            screenshot_frame,
            text="Quick Capture",
            style='BlueGroup.TLabelframe'
        )
        quick_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Screenshot mode toggle with improved styling
        self.screenshot_mode = False
        self.screenshot_button = ttk.Button(
            quick_frame,
            text="Screenshot by Mouse",
            style='Primary.TButton',
            command=self.toggle_screenshot_mode
        )
        self.screenshot_button.pack(fill=tk.X, padx=10, pady=10)
        
        # Manual capture controls in green group
        manual_frame = ttk.LabelFrame(
            screenshot_frame,
            text="Manual Capture",
            style='GreenGroup.TLabelframe'
        )
        manual_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Coordinate inputs in a grid
        coord_frame = ttk.Frame(manual_frame)
        coord_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Style for coordinate labels
        coord_style = {'font': ('Segoe UI', 10), 'background': ThemeManager.get_color('group_green')}
        entry_style = {'width': 8, 'font': ('Segoe UI', 10)}
        
        # X coordinate
        ttk.Label(coord_frame, text="X:", **coord_style).grid(row=0, column=0, padx=(0, 5))
        self.x_var = tk.IntVar(value=0)
        ttk.Entry(coord_frame, textvariable=self.x_var, **entry_style).grid(row=0, column=1, padx=(0, 10))
        
        # Y coordinate
        ttk.Label(coord_frame, text="Y:", **coord_style).grid(row=0, column=2, padx=(0, 5))
        self.y_var = tk.IntVar(value=0)
        ttk.Entry(coord_frame, textvariable=self.y_var, **entry_style).grid(row=0, column=3, padx=(0, 10))
        
        # Width
        ttk.Label(coord_frame, text="Width:", **coord_style).grid(row=0, column=4, padx=(0, 5))
        self.width_var = tk.IntVar(value=800)
        ttk.Entry(coord_frame, textvariable=self.width_var, **entry_style).grid(row=0, column=5, padx=(0, 10))
        
        # Height
        ttk.Label(coord_frame, text="Height:", **coord_style).grid(row=0, column=6, padx=(0, 5))
        self.height_var = tk.IntVar(value=600)
        ttk.Entry(coord_frame, textvariable=self.height_var, **entry_style).grid(row=0, column=7, padx=(0, 10))
        
        # Capture buttons with improved styling
        button_frame = ttk.Frame(manual_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(
            button_frame,
            text="Capture Area",
            style='Primary.TButton',
            command=self.capture_manual_area
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame,
            text="Select Area",
            style='Primary.TButton',
            command=self.take_screenshot
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame,
            text="Center Position",
            style='Secondary.TButton',
            command=self.center_position
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            button_frame,
            text="Load Image",
            style='Secondary.TButton',
            command=self.load_image
        ).pack(side=tk.LEFT)
        
        # Create preview container frame
        preview_container = ttk.Frame(screenshot_frame)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Screenshot preview in purple group (left side)
        preview_frame = ttk.LabelFrame(
            preview_container,
            text="Screenshot Preview",
            style='PurpleGroup.TLabelframe'
        )
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.screenshot_label = ttk.Label(
            preview_frame,
            text="No screenshot taken",
            style='Subtitle.TLabel'
        )
        self.screenshot_label.pack(expand=True, pady=10)
        
        # Center button frame
        button_frame = ttk.Frame(preview_container)
        button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Add vertical centering frame
        button_center = ttk.Frame(button_frame)
        button_center.pack(expand=True)
        
        ttk.Button(
            button_center,
            text="Process\nScreenshot",
            style='Success.TButton',
            command=self.process_screenshot
        ).pack(pady=(0, 10))
        
        ttk.Button(
            button_center,
            text="Clear",
            style='Secondary.TButton',
            command=self.clear_screenshot
        ).pack()
        
        # Extracted text preview (right side)
        text_frame = ttk.LabelFrame(
            preview_container,
            text="Extracted Text Preview",
            style='PurpleGroup.TLabelframe'
        )
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.text_preview = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            height=10,
            font=('Segoe UI', 10)
        )
        self.text_preview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_preview.insert('1.0', "No text extracted yet")
        self.text_preview.config(state='disabled')
    
    def create_status_section(self, parent):
        """Create status section"""
        status_frame = ttk.LabelFrame(
            parent,
            text="Processing Status",
            style='OrangeGroup.TLabelframe'
        )
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Status content frame
        content_frame = ttk.Frame(status_frame)
        content_frame.pack(fill=tk.BOTH, padx=10, pady=10)
        
        # Progress bar with custom styling
        self.progress_bar = ttk.Progressbar(
            content_frame,
            mode='determinate',
            style='Horizontal.TProgressbar'
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Status label with improved styling
        self.status_label = ttk.Label(
            content_frame,
            text="Ready",
            style='Subtitle.TLabel'
        )
        self.status_label.pack(anchor=tk.W)
        
        # Add custom style for progress bar
        style = ttk.Style()
        style.configure(
            'Horizontal.TProgressbar',
            troughcolor=ThemeManager.get_color('border'),
            background=ThemeManager.get_color('primary'),
            thickness=10
        )
        
        # Bind progress tracker
        self.progress_tracker.add_callback(self.update_progress)
    
    def browse_files(self):
        """Browse for files"""
        files = filedialog.askopenfilenames(
            title="Select files to process",
            filetypes=[
                ("All supported", "*.pdf *.doc *.docx *.txt *.md *.xlsx *.xls *.csv *.png *.jpg *.jpeg *.gif *.bmp *.tiff *.html *.htm"),
                ("All files", "*.*")
            ]
        )
        if files:
            self.add_files_to_list(files)
    
    def add_files_to_list(self, files):
        """Add files to the listbox"""
        for file_path in files:
            if file_path not in self.file_listbox.get(0, tk.END):
                self.file_listbox.insert(tk.END, file_path)
    
    def clear_file_list(self):
        """Clear the file list"""
        self.file_listbox.delete(0, tk.END)
    
    def process_files(self, files):
        """Process dropped files"""
        self.add_files_to_list(files)
        self.process_selected_files()
    
    def process_selected_files(self):
        """Process selected files"""
        selected_files = list(self.file_listbox.get(0, tk.END))
        if not selected_files:
            messagebox.showwarning("No Files", "Please select files to process")
            return
        
        # Start processing
        self.progress_tracker.start_task("Processing files", len(selected_files))
        
        for i, file_path in enumerate(selected_files):
            try:
                # Add to processing queue
                self.processing_queue.put({
                    'type': 'file',
                    'file_path': file_path,
                    'callback': self.on_file_processed
                })
                
                self.progress_tracker.update_progress(i + 1)
                
            except Exception as e:
                self.log_error(f"Error processing file {file_path}: {e}")
                messagebox.showerror("Error", f"Error processing {os.path.basename(file_path)}: {str(e)}")
        
        self.progress_tracker.complete_task()
    
    def process_text(self):
        """Process text input"""
        text = self.text_input.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "Please enter some text to process")
            return
        
        # Add to processing queue
        self.processing_queue.put({
            'type': 'text',
            'text': text,
            'callback': self.on_text_processed
        })
        
        self.status_label.config(text="Processing text...")
    
    def toggle_screenshot_mode(self):
        """Toggle screenshot mode"""
        try:
            self.screenshot_mode = not self.screenshot_mode
            if self.screenshot_mode:
                self.screenshot_button.configure(text="Cancel Screenshot Mode")
                # Wait for button update to be visible
                self.update()
                # Schedule area selection after a short delay
                self.after(100, self.start_area_selection)
            else:
                self.screenshot_button.configure(text="Screenshot by Mouse")
                self.cancel_selection()
        except Exception as e:
            self.log_error(f"Error toggling screenshot mode: {e}")
            messagebox.showerror("Error", f"Failed to toggle screenshot mode: {str(e)}")
            # Ensure we reset the mode and button text
            self.screenshot_mode = False
            self.screenshot_button.configure(text="Screenshot by Mouse")
    
    def take_screenshot(self):
        """Take screenshot with area selection"""
        try:
            if not self.screenshot_mode:
                self.toggle_screenshot_mode()
            else:
                self.start_area_selection()
        except Exception as e:
            self.log_error(f"Error starting screenshot: {e}")
            messagebox.showerror("Error", f"Failed to start screenshot: {str(e)}")
    
    def start_area_selection(self):
        """Start area selection for screenshot"""
        try:
            # Hide main window - find the root window
            root_window = self.winfo_toplevel()
            root_window.withdraw()
            
            # Create selection window
            self.create_selection_window()
            
        except Exception as e:
            # Show main window back
            root_window = self.winfo_toplevel()
            root_window.deiconify()
            self.screenshot_mode = False
            self.screenshot_button.configure(text="Screenshot by Mouse")
            raise e
    
    def create_selection_window(self):
        """Create fullscreen transparent window for area selection"""
        try:
            import pyautogui
            
            # Get screen dimensions
            screen_width, screen_height = pyautogui.size()
            
            # Create selection window
            self.selection_window = tk.Toplevel()
            self.selection_window.title("Select Screenshot Area")
            self.selection_window.geometry(f"{screen_width}x{screen_height}+0+0")
            self.selection_window.attributes('-alpha', 0.2)  # More transparent background
            self.selection_window.attributes('-topmost', True)
            self.selection_window.attributes('-transparentcolor', 'black')
            self.selection_window.overrideredirect(True)  # Remove window decorations
            
            # Create canvas for selection
            self.selection_canvas = tk.Canvas(
                self.selection_window, 
                width=screen_width, 
                height=screen_height,
                bg='black',
                highlightthickness=0,
                cursor='crosshair'
            )
            self.selection_canvas.pack(fill=tk.BOTH, expand=True)
            
            # Create overlay effect
            self.selection_canvas.create_rectangle(
                0, 0, screen_width, screen_height,
                fill='gray20', stipple='gray50'
            )
            
            # Bind mouse events
            self.selection_canvas.bind('<Button-1>', self.on_selection_start)
            self.selection_canvas.bind('<B1-Motion>', self.on_selection_drag)
            self.selection_canvas.bind('<ButtonRelease-1>', self.on_selection_end)
            
            # Bind keyboard events
            self.selection_window.bind('<Escape>', self.cancel_selection)
            self.selection_canvas.bind('<Escape>', self.cancel_selection)
            self.selection_window.bind('<Key>', self.handle_selection_key)
            self.selection_canvas.bind('<Key>', self.handle_selection_key)
            
            # Focus the window and canvas
            self.selection_window.focus_force()
            self.selection_canvas.focus_set()
            
            # Add instructions with better visibility
            instruction_text = "Click and drag to select screenshot area. Press ESC to cancel."
            self.selection_canvas.create_text(
                screen_width//2, 50,
                text=instruction_text,
                fill='white',
                font=('Arial', 16, 'bold'),
                tags='instructions'
            )
            
            # Add shadow effect for better text visibility
            self.selection_canvas.create_text(
                screen_width//2 + 2, 52,
                text=instruction_text,
                fill='black',
                font=('Arial', 16, 'bold'),
                tags='instructions_shadow'
            )
            
            # Store initial state
            self.selection_start = None
            self.selection_rect = None
            self.dimensions_text = None
            
        except Exception as e:
            self.log_error(f"Error creating selection window: {e}")
            # Show main window back
            root_window = self.winfo_toplevel()
            root_window.deiconify()
            root_window.lift()
            root_window.focus_force()
            raise e
    
    def on_selection_start(self, event):
        """Handle selection start"""
        self.selection_start = (event.x, event.y)
        self.selection_rect = None
    
    def handle_selection_key(self, event):
        """Handle keyboard events during selection"""
        if event.keysym == 'Escape':
            self.cancel_selection()
        elif event.keysym in ['Return', 'space']:
            # Capture current selection if exists
            if hasattr(self, 'selection_rect') and self.selection_rect:
                self.on_selection_end(None)

    def on_selection_drag(self, event):
        """Handle selection drag"""
        if self.selection_start:
            # Remove previous shapes
            if self.selection_rect:
                self.selection_canvas.delete(self.selection_rect)
            if hasattr(self, 'dimensions_text'):
                self.selection_canvas.delete(self.dimensions_text)
            if hasattr(self, 'dimensions_bg'):
                self.selection_canvas.delete(self.dimensions_bg)
            
            # Calculate coordinates
            x1, y1 = self.selection_start
            x2, y2 = event.x, event.y
            
            # Calculate dimensions
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            
            # Draw selection rectangle with enhanced visibility
            self.selection_rect = self.selection_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline='#00FF00',  # Bright green outline
                width=3,           # Thicker border
                fill='#FFFFFF',    # White fill
                stipple='gray25'   # Less dense pattern for better visibility
            )
            
            # Create background for dimensions text
            text_x = (x1 + x2) // 2
            text_y = min(y1, y2) - 25
            self.dimensions_bg = self.selection_canvas.create_rectangle(
                text_x - 50, text_y - 10,
                text_x + 50, text_y + 10,
                fill='black',
                outline='#00FF00',
                width=2
            )
            
            # Add dimensions display with enhanced visibility
            self.dimensions_text = self.selection_canvas.create_text(
                text_x, text_y,
                text=f'{width} × {height}',
                fill='#00FF00',
                font=('Arial', 12, 'bold')
            )
    
    def on_selection_end(self, event=None):
        """Handle selection end and capture screenshot"""
        try:
            if self.selection_start:
                # Get coordinates
                x1, y1 = self.selection_start
                x2, y2 = event.x if event else self.selection_canvas.winfo_pointerx(), event.y if event else self.selection_canvas.winfo_pointery()
                
                # Calculate coordinates and dimensions
                x = min(x1, x2)
                y = min(y1, y2)
                width = abs(x2 - x1)
                height = abs(y2 - y1)
                
                # Validate minimum dimensions
                if width < 10 or height < 10:
                    messagebox.showwarning("Invalid Selection", "Selection area is too small. Please select a larger area.")
                    return
                
                # Store coordinates for screenshot
                screenshot_coords = (x, y, width, height)
                
                # Hide selection window temporarily
                if hasattr(self, 'selection_window') and self.selection_window:
                    self.selection_window.withdraw()
                
                # Wait a moment for windows to settle
                self.selection_window.after(100, lambda: self._complete_screenshot(screenshot_coords))
                
        except Exception as e:
            self.log_error(f"Error in screenshot selection: {e}")
            self._cleanup_screenshot_mode()
            messagebox.showerror("Error", f"Failed to capture screenshot: {str(e)}")

    def _complete_screenshot(self, screenshot_coords):
        """Complete the screenshot capture process"""
        try:
            # Capture the screenshot
            self.capture_screenshot_area(*screenshot_coords)
            
            # Clean up screenshot mode
            self._cleanup_screenshot_mode()
            
        except Exception as e:
            self.log_error(f"Error completing screenshot: {e}")
            self._cleanup_screenshot_mode()
            messagebox.showerror("Error", f"Failed to complete screenshot: {str(e)}")

    def _cleanup_screenshot_mode(self):
        """Clean up screenshot mode and restore windows"""
        try:
            # Close selection window if it exists
            if hasattr(self, 'selection_window') and self.selection_window:
                self.selection_window.destroy()
                self.selection_window = None
                self.selection_canvas = None
            
            # Show and focus main window
            root_window = self.winfo_toplevel()
            root_window.deiconify()
            root_window.lift()
            root_window.focus_force()
            
            # Reset screenshot mode
            self.screenshot_mode = False
            self.screenshot_button.configure(text="Screenshot by Mouse")
            
            # Update window to ensure it's visible
            root_window.update()
            
        except Exception as e:
            self.log_error(f"Error cleaning up screenshot mode: {e}")
            # Final attempt to restore main window
            try:
                root_window = self.winfo_toplevel()
                root_window.deiconify()
                root_window.lift()
                root_window.focus_force()
            except:
                pass
    
    def cancel_selection(self, event=None):
        """Cancel area selection"""
        if hasattr(self, 'selection_window') and self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
            self.selection_canvas = None
        
        # Show main window
        root_window = self.winfo_toplevel()
        root_window.deiconify()
        root_window.lift()
        root_window.focus_force()
    
    def capture_manual_area(self):
        """Capture screenshot using manual coordinates"""
        try:
            x = self.x_var.get()
            y = self.y_var.get()
            width = self.width_var.get()
            height = self.height_var.get()
            
            if width <= 0 or height <= 0:
                messagebox.showwarning("Invalid Dimensions", "Width and height must be greater than 0")
                return
            
            if x < 0 or y < 0:
                messagebox.showwarning("Invalid Coordinates", "X and Y coordinates must be non-negative")
                return
            
            self.capture_screenshot_area(x, y, width, height)
            
        except Exception as e:
            self.log_error(f"Error in manual capture: {e}")
            messagebox.showerror("Error", f"Failed to capture area: {str(e)}")
    
    def capture_screenshot_area(self, x, y, width, height):
        """Capture screenshot of specified area"""
        try:
            import pyautogui
            from PIL import Image, ImageTk
            
            # Update status
            self.status_label.config(text="Capturing screenshot...")
            self.update()  # Force update to show status
            
            # Create output directory if it doesn't exist
            output_dir = os.path.join("output", "screenshots")
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            output_path = os.path.join(output_dir, filename)
            
            # Capture screenshot
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            
            # Save screenshot directly to output directory
            screenshot.save(output_path)
            self.current_screenshot = screenshot
            self.current_screenshot_path = output_path
            
            # Display preview
            self.display_screenshot_preview(screenshot)
            
            # Update status with success message
            success_msg = f"Screenshot saved: {filename}\nLocation: {width}×{height} at ({x}, {y})"
            self.status_label.config(text=success_msg)
            
            # Show success notification
            messagebox.showinfo("Success", f"Screenshot saved to:\n{output_path}")
            
        except Exception as e:
            self.log_error(f"Error capturing screenshot: {e}")
            error_msg = str(e)
            self.status_label.config(text="Screenshot capture failed")
            messagebox.showerror("Error", f"Failed to capture screenshot:\n{error_msg}")
            
        finally:
            # Ensure main window is visible and focused
            root_window = self.winfo_toplevel()
            root_window.lift()
            root_window.focus_force()
    
    def display_screenshot_preview(self, screenshot):
        """Display screenshot preview"""
        try:
            from PIL import ImageTk, Image
            
            # Resize image for preview (max 300x300)
            max_size = (300, 300)
            screenshot.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(screenshot)
            
            # Update label
            self.screenshot_label.configure(image=photo, text="")
            self.screenshot_label.image = photo  # Keep a reference
            
        except Exception as e:
            self.log_error(f"Error displaying preview: {e}")
            self.screenshot_label.config(text="Error displaying preview")
    
    def load_image(self):
        """Load image file"""
        file_path = filedialog.askopenfilename(
            title="Select image file",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            try:
                from PIL import Image
                
                # Load image
                image = Image.open(file_path)
                self.current_screenshot = image
                self.current_screenshot_path = file_path
                
                # Display preview
                self.display_screenshot_preview(image)
                
                self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
                
            except Exception as e:
                self.log_error(f"Error loading image: {e}")
                messagebox.showerror("Error", f"Failed to load image: {str(e)}")
                self.screenshot_label.config(text="Error loading image")
    
    def process_screenshot(self):
        """Process screenshot with Azure Vision API"""
        if hasattr(self, 'current_screenshot_path') and self.current_screenshot_path:
            try:
                # Add to processing queue
                self.processing_queue.put({
                    'type': 'screenshot',
                    'screenshot_path': self.current_screenshot_path,
                    'callback': self.on_screenshot_processed
                })
                
                self.status_label.config(text="Processing screenshot with Azure Vision API...")
                
            except Exception as e:
                self.log_error(f"Error processing screenshot: {e}")
                messagebox.showerror("Error", f"Failed to process screenshot: {str(e)}")
        else:
            messagebox.showwarning("No Screenshot", "Please take a screenshot or load an image first")
    
    def update_text_stats(self, event=None):
        """Update text statistics"""
        text = self.text_input.get(1.0, tk.END)
        char_count = len(text)
        word_count = len(text.split())
        self.text_stats_label.config(text=f"Characters: {char_count} | Words: {word_count}")
    
    def clear_text(self):
        """Clear text input"""
        self.text_input.delete(1.0, tk.END)
        self.update_text_stats()
    
    def clear_screenshot(self):
        """Clear screenshot preview"""
        self.screenshot_label.config(image="", text="No screenshot taken")
        if hasattr(self, 'current_screenshot'):
            delattr(self, 'current_screenshot')
        if hasattr(self, 'current_screenshot_path'):
            delattr(self, 'current_screenshot_path')
    
    def center_position(self):
        """Center the capture area on screen"""
        try:
            import pyautogui
            
            # Get screen size
            screen_width, screen_height = pyautogui.size()
            
            # Calculate center position
            width = self.width_var.get()
            height = self.height_var.get()
            
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            # Update variables
            self.x_var.set(max(0, x))
            self.y_var.set(max(0, y))
            
            self.status_label.config(text=f"Centered: ({x}, {y}) {width}x{height}")
            
        except Exception as e:
            self.log_error(f"Error centering position: {e}")
            messagebox.showerror("Error", f"Failed to center position: {str(e)}")
    
    def update_progress(self, task, progress, total, status):
        """Update progress display"""
        if total > 0:
            percentage = (progress / total) * 100
            self.progress_bar['value'] = percentage
            self.status_label.config(text=f"{task}: {progress}/{total} ({percentage:.1f}%)")
        else:
            self.progress_bar['value'] = 0
            self.status_label.config(text=task)
    
    def on_file_processed(self, result):
        """Handle file processing result"""
        if result.get('success'):
            messagebox.showinfo("Success", f"File processed: {os.path.basename(result['file_path'])}")
        else:
            messagebox.showerror("Error", f"Failed to process file: {result.get('error', 'Unknown error')}")
    
    def on_text_processed(self, result):
        """Handle text processing result"""
        if result.get('success'):
            messagebox.showinfo("Success", "Text processed successfully")
            self.clear_text()
        else:
            messagebox.showerror("Error", f"Failed to process text: {result.get('error', 'Unknown error')}")
    
    def on_screenshot_processed(self, result):
        """Handle screenshot processing result"""
        if result.get('success'):
            # Enable text preview for editing
            self.text_preview.config(state='normal')
            self.text_preview.delete('1.0', tk.END)
            
            # Insert extracted text
            content = result.get('content', 'No text extracted')
            self.text_preview.insert('1.0', content)
            
            # Disable text preview for read-only
            self.text_preview.config(state='disabled')
            
            messagebox.showinfo("Success", "Screenshot processed successfully")
        else:
            # Show error in text preview
            self.text_preview.config(state='normal')
            self.text_preview.delete('1.0', tk.END)
            self.text_preview.insert('1.0', f"Error: {result.get('error', 'Unknown error')}")
            self.text_preview.config(state='disabled')
            
            messagebox.showerror("Error", f"Failed to process screenshot: {result.get('error', 'Unknown error')}")


class ManagementTab(ttk.Frame, LoggerMixin):
    """Management tab for viewing and managing stored documents"""
    
    def __init__(self, parent, db_manager, file_processor):
        super().__init__(parent)
        LoggerMixin.__init__(self)
        
        self.db_manager = db_manager
        self.file_processor = file_processor
        
        self.setup_ui()
        self.log_info("Management tab initialized")
    
    def setup_ui(self):
        """Setup the management tab UI"""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Document Management", font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Control panel
        self.create_control_panel(main_frame)
        
        # Document list
        self.create_document_list(main_frame)
        
        # Details panel
        self.create_details_panel(main_frame)
        
        # Load initial data
        self.refresh_file_list()
    
    def create_control_panel(self, parent):
        """Create control panel"""
        control_frame = ttk.LabelFrame(parent, text="Controls")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Store button references
        self.refresh_btn = ttk.Button(button_frame, text="Refresh", command=self.refresh_file_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.delete_btn = ttk.Button(button_frame, text="Delete Selected", command=self.delete_selected)
        self.delete_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.export_btn = ttk.Button(button_frame, text="Export Selected", command=self.export_selected)
        self.export_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stats_btn = ttk.Button(button_frame, text="Database Stats", command=self.show_stats)
        self.stats_btn.pack(side=tk.RIGHT)
    
    def create_document_list(self, parent):
        """Create document list"""
        list_frame = ttk.LabelFrame(parent, text="Documents")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Split frame for two treeviews
        split_frame = ttk.Frame(list_frame)
        split_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # SQLite documents (left side)
        sql_frame = ttk.LabelFrame(split_frame, text="SQLite Database")
        sql_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        columns = ('Filename', 'Type', 'Size', 'Date', 'Status')
        self.sql_tree = ttk.Treeview(sql_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            self.sql_tree.heading(col, text=col)
            self.sql_tree.column(col, width=100)
        
        # Scrollbar for SQLite tree
        sql_scrollbar = ttk.Scrollbar(sql_frame, orient=tk.VERTICAL, command=self.sql_tree.yview)
        self.sql_tree.configure(yscrollcommand=sql_scrollbar.set)
        
        self.sql_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sql_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Migration buttons (center)
        migration_frame = ttk.Frame(split_frame)
        migration_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Add vertical centering frame
        button_center = ttk.Frame(migration_frame)
        button_center.pack(expand=True)
        
        # Store migration button references
        self.migrate_btn = ttk.Button(
            button_center,
            text="→\nMigrate to\nVector DB",
            command=self.migrate_to_vector
        )
        self.migrate_btn.pack(pady=(0, 10))
        
        self.delete_vector_btn = ttk.Button(
            button_center,
            text="Delete from\nVector Only",
            command=self.delete_from_vector
        )
        self.delete_vector_btn.pack()
        
        # Vector DB documents (right side)
        vector_frame = ttk.LabelFrame(split_frame, text="Vector Database")
        vector_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.vector_tree = ttk.Treeview(vector_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            self.vector_tree.heading(col, text=col)
            self.vector_tree.column(col, width=100)
        
        # Scrollbar for vector tree
        vector_scrollbar = ttk.Scrollbar(vector_frame, orient=tk.VERTICAL, command=self.vector_tree.yview)
        self.vector_tree.configure(yscrollcommand=vector_scrollbar.set)
        
        self.vector_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vector_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection events
        self.sql_tree.bind('<<TreeviewSelect>>', self.on_document_selected)
        self.vector_tree.bind('<<TreeviewSelect>>', self.on_document_selected)
    
    def create_details_panel(self, parent):
        """Create details panel"""
        details_frame = ttk.LabelFrame(parent, text="Document Details")
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Details text area
        self.details_text = scrolledtext.ScrolledText(details_frame, height=10, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def refresh_file_list(self):
        """Refresh the document list with synchronized view of both databases"""
        try:
            # Disable all control buttons during refresh
            self._disable_controls()
            
            # Clear existing items
            self._clear_trees()
            
            # Configure tag colors
            self._configure_tree_tags()
            
            # Show loading message with progress
            self._show_loading_messages()
            
            # Update UI
            self.update_idletasks()
            
            # Create queue for results
            self.result_queue = queue.Queue()
            
            # Start loading in background with queue
            loading_thread = threading.Thread(target=self._load_file_list_async)
            loading_thread.daemon = True  # Thread will be terminated when main thread ends
            loading_thread.start()
            
            # Schedule periodic UI updates while loading
            self._check_loading_status()
            
        except Exception as e:
            self.log_error(f"Error refreshing file list: {e}")
            messagebox.showerror("Error", f"Failed to refresh file list: {str(e)}")
            self._enable_controls()  # Re-enable controls
            
    def _disable_controls(self):
        """Disable all controls during operations"""
        self.details_text.config(state='disabled')
        self.sql_tree.bind('<<TreeviewSelect>>', lambda e: 'break')
        self.vector_tree.bind('<<TreeviewSelect>>', lambda e: 'break')
        
        # Disable buttons
        for button in [self.refresh_btn, self.delete_btn, self.export_btn, 
                      self.migrate_btn, self.delete_vector_btn, self.stats_btn]:
            button.config(state='disabled')
            
    def _enable_controls(self):
        """Re-enable all controls after operations"""
        self.details_text.config(state='normal')
        self.sql_tree.bind('<<TreeviewSelect>>', self.on_document_selected)
        self.vector_tree.bind('<<TreeviewSelect>>', self.on_document_selected)
        
        # Re-enable buttons
        for button in [self.refresh_btn, self.delete_btn, self.export_btn, 
                      self.migrate_btn, self.delete_vector_btn, self.stats_btn]:
            button.config(state='normal')
            
    def _configure_tree_tags(self):
        """Configure tree view tags"""
        for tree in [self.sql_tree, self.vector_tree]:
            tree.tag_configure('in_both', background='#e6f3ff')  # Light blue
            tree.tag_configure('loading', background='#f0f0f0')  # Light gray
            tree.tag_configure('selected', background='#cce8ff')  # Lighter blue
            
    def _show_loading_messages(self):
        """Show loading messages in trees"""
        self.loading_id_sql = self.sql_tree.insert('', tk.END, 
            values=('Loading SQLite database...', '', '', '', ''), 
            tags=['loading'])
        self.loading_id_vector = self.vector_tree.insert('', tk.END, 
            values=('Loading Vector database...', '', '', '', ''), 
            tags=['loading'])
    
    def _process_batch_operation(self, operation_name, items, operation_func, progress_callback=None):
        """Process a batch operation with progress tracking"""
        try:
            if not items:
                return
                
            # Create progress dialog
            progress = ttk.Progressbar(self, mode='determinate')
            progress.place(relx=0.5, rely=0.5, anchor='center')
            
            total_items = len(items)
            processed = 0
            
            def update_progress():
                nonlocal processed
                processed += 1
                progress['value'] = (processed / total_items) * 100
                self.update_idletasks()
                if progress_callback:
                    progress_callback()
            
            # Process items
            for item in items:
                if not self.winfo_exists():
                    return
                try:
                    operation_func(item)
                except Exception as e:
                    self.log_error(f"Error processing {operation_name} for item {item}: {e}")
                self.after(0, update_progress)
            
            # Cleanup
            progress.destroy()
            
        except Exception as e:
            self.log_error(f"Error in batch {operation_name}: {e}")
            if 'progress' in locals():
                progress.destroy()
            raise
            
    def _check_loading_status(self):
        """Check loading status and update UI"""
        try:
            # Process any available results from the queue
            while True:
                try:
                    items = self.result_queue.get_nowait()
                    if items is None:  # End signal
                        # Loading finished
                        self._loading_complete = True
                        break
                    else:
                        # Update trees with batch
                        self._do_update_trees(items)
                except queue.Empty:
                    break
            
            if hasattr(self, '_loading_complete') and self._loading_complete:
                # Loading finished, remove loading messages if they still exist
                try:
                    if hasattr(self, 'loading_id_sql'):
                        self.sql_tree.delete(self.loading_id_sql)
                except:
                    pass
                try:
                    if hasattr(self, 'loading_id_vector'):
                        self.vector_tree.delete(self.loading_id_vector)
                except:
                    pass
                
                # Re-enable UI elements
                self.details_text.config(state='normal')
                self.sql_tree.bind('<<TreeviewSelect>>', self.on_document_selected)  # Re-enable selection
                self.vector_tree.bind('<<TreeviewSelect>>', self.on_document_selected)
                return
            
            # Update loading message with progress if available
            if hasattr(self, '_loading_progress'):
                try:
                    if hasattr(self, 'loading_id_sql'):
                        self.sql_tree.set(self.loading_id_sql, 0, f"Loading SQLite database... ({self._loading_progress}%)")
                except:
                    pass
                try:
                    if hasattr(self, 'loading_id_vector'):
                        self.vector_tree.set(self.loading_id_vector, 0, f"Loading Vector database... ({self._loading_progress}%)")
                except:
                    pass
            
            # Check again in 100ms
            self.after(100, self._check_loading_status)
            
        except Exception as e:
            self.log_error(f"Error checking loading status: {e}")
            # Continue checking even if there's an error
            self.after(100, self._check_loading_status)
    
    def _load_file_list_async(self):
        """Load file list asynchronously with queue"""
        try:
            # Helper function to format file size
            def format_file_size(size):
                if size > 1024 * 1024:
                    return f"{size / (1024 * 1024):.2f} MB"
                elif size > 1024:
                    return f"{size / 1024:.2f} KB"
                return f"{size} bytes"
            
            # Set initial progress
            self._loading_progress = 0
            
            # Get SQL documents in chunks
            sql_documents = []
            try:
                # Get documents in smaller chunks
                offset = 0
                chunk_size = 20
                while True:
                    chunk = self.db_manager.get_documents(limit=chunk_size, offset=offset)
                    if not chunk:
                        break
                    sql_documents.extend(chunk)
                    offset += chunk_size
                    self._loading_progress = min(25, int((offset / (offset + chunk_size)) * 25))
                    time.sleep(0.01)  # Allow UI to update
            except Exception as e:
                self.log_error(f"Error getting SQL documents: {e}")
            
            # Get Vector documents in chunks
            vector_documents = []
            try:
                vector_documents = self.db_manager.get_vector_documents()
                self._loading_progress = 50
            except Exception as e:
                self.log_error(f"Error getting Vector documents: {e}")
            
            # Create lookup dictionaries
            sql_lookup = {doc['document_id']: doc for doc in sql_documents}
            vector_lookup = {doc['id']: doc for doc in vector_documents}
            
            # Get all unique document IDs
            all_doc_ids = list(set(sql_lookup.keys()) | set(vector_lookup.keys()))
            total_docs = len(all_doc_ids)
            
            # Clear loading message
            self.after(0, self._clear_trees)
            
            # Process documents in small batches
            batch_size = 10
            for i in range(0, len(all_doc_ids), batch_size):
                batch_ids = all_doc_ids[i:i + batch_size]
                items_to_add = []
                
                for doc_id in batch_ids:
                    # Update progress (50-100%)
                    self._loading_progress = 50 + int((i / total_docs) * 50) if total_docs > 0 else 100
                    
                    sql_doc = sql_lookup.get(doc_id)
                    vector_doc = vector_lookup.get(doc_id)
                    
                    # Get base document info (prefer SQL version if available)
                    if sql_doc:
                        filename = sql_doc.get('filename', 'Unknown')
                        file_type = sql_doc.get('file_type', 'Unknown')
                        file_size = format_file_size(sql_doc.get('file_size', 0))
                        created_at = sql_doc.get('created_at', 'Unknown')
                        
                        # Parse metadata for additional info
                        try:
                            metadata = json.loads(sql_doc.get('metadata', '{}'))
                            processor = metadata.get('processor', '')
                            type_str = f"{file_type} ({processor})" if processor else file_type
                        except:
                            type_str = file_type
                        
                        # Format status
                        status = sql_doc.get('status', 'Unknown')
                        if status == 'processed' and sql_doc.get('content'):
                            content_len = len(sql_doc.get('content', ''))
                            status = f"Processed ({content_len} chars)"
                        
                    elif vector_doc:
                        # Use vector DB metadata if SQL version not available
                        metadata = vector_doc.get('metadata', {})
                        filename = metadata.get('filename', 'Unknown')
                        file_type = metadata.get('file_type', 'Unknown')
                        file_size = 'N/A'  # Vector DB might not store file size
                        created_at = metadata.get('created_at', 'Unknown')
                        type_str = file_type
                        status = 'In Vector DB'
                    
                    # Create display values
                    values = (filename, type_str, file_size, created_at, status)
                    
                    # Add to batch
                    items_to_add.append({
                        'doc_id': doc_id,
                        'values': values,
                        'in_sql': bool(sql_doc),
                        'in_vector': bool(vector_doc)
                    })
                
                # Put batch in queue for UI thread
                self.result_queue.put(items_to_add)
                time.sleep(0.05)  # Small delay between batches
            
            self.log_info(f"Loaded {len(all_doc_ids)} unique documents")
            
            # Signal completion
            self.result_queue.put(None)
            self._loading_complete = True
            
        except Exception as e:
            self.log_error(f"Error loading file list: {e}")
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to load file list: {str(e)}"))
            # Signal completion even on error
            self.result_queue.put(None)
            self._loading_complete = True
    
    def _clear_trees(self):
        """Clear both trees in main thread"""
        try:
            for item in self.sql_tree.get_children():
                self.sql_tree.delete(item)
            for item in self.vector_tree.get_children():
                self.vector_tree.delete(item)
        except Exception as e:
            self.log_error(f"Error clearing trees: {e}")
    
    def _do_update_trees(self, items):
        """Update trees with batch of items in main thread"""
        try:
            for item in items:
                doc_id = item['doc_id']
                values = item['values']
                
                # Add to SQL tree if exists in SQLite
                if item['in_sql']:
                    item_id = self.sql_tree.insert('', tk.END, values=values, tags=(doc_id,))
                    # Highlight if also in vector DB
                    if item['in_vector']:
                        self.sql_tree.item(item_id, tags=(doc_id, 'in_both'))
                
                # Add to Vector tree if exists in Vector DB
                if item['in_vector']:
                    item_id = self.vector_tree.insert('', tk.END, values=values, tags=(doc_id,))
                    # Highlight if also in SQL DB
                    if item['in_sql']:
                        self.vector_tree.item(item_id, tags=(doc_id, 'in_both'))
                        
        except Exception as e:
            self.log_error(f"Error updating trees: {e}")
    
    def on_document_selected(self, event):
        """Handle document selection with linked selection between trees"""
        # Get the tree widget that triggered the event
        tree = event.widget
        
        # Get selection from the active tree
        selection = tree.selection()
        if not selection:
            return
        
        # Get document ID from tags
        item = tree.item(selection[0])
        document_id = item['tags'][0] if item['tags'] else None
        
        if document_id:
            # Get document status in both DBs
            status = self.db_manager.get_document_status(document_id)
            
            # Clear previous selections in both trees
            self.sql_tree.selection_remove(*self.sql_tree.selection())
            self.vector_tree.selection_remove(*self.vector_tree.selection())
            
            # Find and select corresponding items in both trees
            def select_in_tree(tree_widget, doc_id):
                for item in tree_widget.get_children():
                    if tree_widget.item(item)['tags'] and tree_widget.item(item)['tags'][0] == doc_id:
                        tree_widget.selection_add(item)
                        tree_widget.see(item)  # Ensure the item is visible
                        return True
                return False
            
            # Select in SQL tree if exists
            if status['sql_exists']:
                select_in_tree(self.sql_tree, document_id)
            
            # Select in Vector tree if exists
            if status['vector_exists']:
                select_in_tree(self.vector_tree, document_id)
            
            # Show document details
            self.show_document_details(document_id, 'both')
    
    def show_document_details(self, document_id, source='sql'):
        """Show document details with content from both databases"""
        try:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            
            # Show loading message
            self.details_text.insert(1.0, "Loading document details...")
            self.details_text.config(state=tk.DISABLED)
            self.update_idletasks()  # Force UI update
            
            # Start loading details in a separate thread
            threading.Thread(target=self._load_document_details, args=(document_id, source)).start()
            
        except Exception as e:
            self.log_error(f"Error showing document details: {e}")
            self._update_details_text(f"Error loading details: {str(e)}")
    
    def _load_document_details(self, document_id, source):
        """Load document details with simplified approach to avoid hanging"""
        try:
            # Show loading indicator
            self._update_details_text("Loading document details...")
            
            try:
                # Get SQL document first (primary source)
                sql_doc = self.db_manager.get_document_by_id(document_id)
                if not sql_doc:
                    self._update_details_text("Document not found in SQLite database")
                    return
                
                # Format basic details
                file_size = sql_doc.get('file_size', 0)
                if file_size > 1024 * 1024:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                elif file_size > 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size} bytes"
                
                # Parse metadata
                try:
                    metadata = json.loads(sql_doc.get('metadata', '{}'))
                except:
                    metadata = {}
                
                # Build details text
                details = f"""Document Details:
----------------------------------------
Document ID: {document_id}
Filename: {sql_doc.get('filename', 'N/A')}
File Type: {sql_doc.get('file_type', 'N/A')}
File Size: {size_str}
Created: {sql_doc.get('created_at', 'N/A')}
Status: {sql_doc.get('status', 'N/A')}
Selected From: {source.upper()} Database

Processing Information:
----------------------------------------
Processor: {metadata.get('processor', 'N/A')}
Processing Time: {metadata.get('processing_time', 'N/A')} seconds
Input Type: {metadata.get('input_type', 'N/A')}"""
                
                # Update UI with basic details
                self._update_details_text(details)
                
                # Add content preview
                content = sql_doc.get('content', '')
                if content:
                    preview = f"\n\nContent Preview:\n----------------------------------------\n{content[:500]}"
                    if len(content) > 500:
                        preview += "...\n"
                    preview += f"[Full content length: {len(content)} characters]"
                    self._append_details_text(preview)
                
                # Try to get vector status without full document fetch
                try:
                    vector_status = "Checking vector database status..."
                    self._append_details_text(f"\n\nVector Database Status:\n----------------------------------------\n{vector_status}")
                    
                    if hasattr(self.db_manager, 'collection') and self.db_manager.collection:
                        try:
                            result = self.db_manager.collection.get(
                                ids=[document_id],
                                include=[]
                            )
                            vector_status = "Present in vector database" if result and result.get('ids') else "Not present in vector database"
                        except Exception as e:
                            vector_status = f"Vector database error: {str(e)}"
                    else:
                        vector_status = "Vector database not initialized"
                    
                    # Update vector status
                    self._update_details_text(self.details_text.get("1.0", "end-1c").replace(
                        "Checking vector database status...",
                        vector_status
                    ))
                    
                except Exception as e:
                    self.log_error(f"Error checking vector status: {e}")
                    # Don't update UI - keep the "checking" message
                
            except Exception as e:
                self.log_error(f"Error loading document details: {e}")
                self._update_details_text(f"Error loading document details: {str(e)}")
            
        finally:
            # Always re-enable controls
            self.after(100, self._enable_controls)
    
    def _update_details_text(self, text):
        """Update details text from any thread"""
        if not self.winfo_exists():
            return
        self.after(0, self._do_update_details_text, text)
    
    def _append_details_text(self, text):
        """Append to details text from any thread"""
        if not self.winfo_exists():
            return
        self.after(0, self._do_append_details_text, text)
    
    def _do_update_details_text(self, text):
        """Actually update details text in main thread"""
        try:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, text)
            self.details_text.config(state=tk.DISABLED)
        except Exception as e:
            self.log_error(f"Error updating details text: {e}")
    
    def _do_append_details_text(self, text):
        """Actually append to details text in main thread"""
        try:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.insert(tk.END, text)
            self.details_text.config(state=tk.DISABLED)
        except Exception as e:
            self.log_error(f"Error appending to details text: {e}")
    
    def migrate_to_vector(self):
        """Migrate selected document to vector DB"""
        # Get selection from SQL tree
        selection = self.sql_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select documents to migrate")
            return
        
        migrated = 0
        for item in selection:
            doc_id = self.sql_tree.item(item)['tags'][0]
            if self.db_manager.migrate_to_vector(doc_id):
                migrated += 1
        
        # Refresh list
        self.refresh_file_list()
        messagebox.showinfo("Migration Complete", f"Migrated {migrated} document(s) to vector DB")
    
    def delete_from_vector(self):
        """Delete selected document from vector DB only"""
        # Get selection from vector tree
        selection = self.vector_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select documents to delete")
            return
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Delete {len(selection)} document(s) from vector DB?"):
            return
        
        deleted = 0
        for item in selection:
            doc_id = self.vector_tree.item(item)['tags'][0]
            if self.db_manager.delete_document(doc_id, delete_from_vector=False):
                deleted += 1
        
        # Refresh list
        self.refresh_file_list()
        messagebox.showinfo("Delete Complete", f"Deleted {deleted} document(s) from vector DB")
    
    def delete_selected(self):
        """Delete selected documents from both DBs"""
        # Get selection from either tree
        sql_selection = self.sql_tree.selection()
        vector_selection = self.vector_tree.selection()
        
        if not sql_selection and not vector_selection:
            messagebox.showwarning("No Selection", "Please select documents to delete")
            return
        
        # Confirm deletion
        total_selected = len(sql_selection) + len(vector_selection)
        if not messagebox.askyesno("Confirm Delete", f"Delete {total_selected} selected document(s)?"):
            return
        
        # Delete documents
        deleted_count = 0
        
        # Delete from SQL tree
        for item in sql_selection:
            doc_id = self.sql_tree.item(item)['tags'][0]
            if self.db_manager.delete_document(doc_id, delete_from_vector=True):
                deleted_count += 1
        
        # Delete from vector tree
        for item in vector_selection:
            doc_id = self.vector_tree.item(item)['tags'][0]
            if self.db_manager.delete_document(doc_id, delete_from_vector=True):
                deleted_count += 1
        
        # Refresh list
        self.refresh_file_list()
        messagebox.showinfo("Delete Complete", f"Deleted {deleted_count} document(s)")
    
    def export_selected(self):
        """Export selected documents"""
        # Get selections from both trees
        sql_selection = self.sql_tree.selection()
        vector_selection = self.vector_tree.selection()
        
        if not sql_selection and not vector_selection:
            messagebox.showwarning("No Selection", "Please select documents to export")
            return
        
        # Choose export directory
        export_dir = filedialog.askdirectory(title="Choose export directory")
        if not export_dir:
            return
        
        # Export documents
        exported_count = 0
        processed_ids = set()  # Track processed documents to avoid duplicates
        
        # Helper function to export a document
        def export_document(tree, item):
            nonlocal exported_count
            document_id = tree.item(item)['tags'][0] if tree.item(item)['tags'] else None
            if document_id and document_id not in processed_ids:
                document = self.db_manager.get_document_by_id(document_id)
                if document:
                    try:
                        export_path = os.path.join(export_dir, f"{document['filename']}.txt")
                        with open(export_path, 'w', encoding='utf-8') as f:
                            f.write(document.get('content', ''))
                        exported_count += 1
                        processed_ids.add(document_id)
                    except Exception as e:
                        self.log_error(f"Error exporting document {document_id}: {e}")
        
        # Export from SQL tree
        for item in sql_selection:
            export_document(self.sql_tree, item)
        
        # Export from Vector tree
        for item in vector_selection:
            export_document(self.vector_tree, item)
        
        messagebox.showinfo("Export Complete", f"Exported {exported_count} document(s)")
    
    def show_stats(self):
        """Show database statistics"""
        try:
            stats = self.db_manager.get_database_stats()
            
            stats_text = f"""Database Statistics:
            
Total Documents: {stats.get('total_documents', 0)}
Total Screenshots: {stats.get('total_screenshots', 0)}
Vector Documents: {stats.get('vector_documents', 0)}

File Type Distribution:"""
            
            for file_type, count in stats.get('file_type_distribution', {}).items():
                stats_text += f"\n  {file_type}: {count}"
            
            messagebox.showinfo("Database Statistics", stats_text)
            
        except Exception as e:
            self.log_error(f"Error showing stats: {e}")
            messagebox.showerror("Error", f"Failed to load statistics: {str(e)}")


class DashboardTab(ttk.Frame, LoggerMixin):
    """Dashboard tab for WMS system overview"""
    
    def __init__(self, parent, db_manager):
        super().__init__(parent)
        LoggerMixin.__init__(self)
        
        self.db_manager = db_manager
        self.setup_ui()
        self.update_stats()
        
        # Update stats every 30 seconds
        self.after(30000, self.update_stats)
    
    def setup_ui(self):
        """Setup the dashboard UI"""
        # Main container with dark theme
        main_frame = ttk.Frame(self, style='Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Top stats panel
        self.create_top_stats(main_frame)
        
        # Middle section with storage and grid
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        # Storage usage (left)
        self.create_storage_section(middle_frame)
        
        # Document grid (right)
        self.create_document_grid(middle_frame)
        
        # Bottom section
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        # Processing trends (left)
        self.create_trends_section(bottom_frame)
        
        # Top types chart (right)
        self.create_types_chart(bottom_frame)
    
    def create_top_stats(self, parent):
        """Create top statistics panel"""
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Stats boxes
        self.total_docs = self.create_stat_box(
            stats_frame,
            "Total Documents",
            "0",
            "📄",
            "#1a73e8"
        )
        
        self.queue_size = self.create_stat_box(
            stats_frame,
            "Processing Queue",
            "0",
            "⏳",
            "#e8710a"
        )
        
        self.storage_used = self.create_stat_box(
            stats_frame,
            "Storage Used",
            "0 MB",
            "💾",
            "#23a455"
        )
        
        self.new_today = self.create_stat_box(
            stats_frame,
            "New Today",
            "0",
            "📈",
            "#9333ea"
        )
    
    def create_stat_box(self, parent, title, value, icon, color):
        """Create a statistics box"""
        frame = ttk.Frame(parent, style='Card.TFrame')
        frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Icon and title
        header = ttk.Frame(frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ttk.Label(
            header,
            text=icon,
            font=('Segoe UI', 24)
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            header,
            text=title,
            style='CardTitle.TLabel'
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        # Value
        value_label = ttk.Label(
            frame,
            text=value,
            style='CardValue.TLabel'
        )
        value_label.pack(padx=10, pady=(0, 10))
        
        return value_label
    
    def create_storage_section(self, parent):
        """Create storage usage section"""
        frame = ttk.LabelFrame(
            parent,
            text="Storage Usage",
            style='Card.TLabelframe'
        )
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Canvas for circular progress
        self.storage_canvas = tk.Canvas(
            frame,
            width=200,
            height=200,
            bg='#1e1e2d',
            highlightthickness=0
        )
        self.storage_canvas.pack(pady=20)
        
        # Progress text
        self.storage_text = ttk.Label(
            frame,
            text="58%\nUsed",
            style='StorageText.TLabel'
        )
        self.storage_text.pack(pady=(0, 20))
        
        # Draw initial progress
        self.draw_storage_progress(58)
    
    def create_document_grid(self, parent):
        """Create document storage grid visualization"""
        frame = ttk.LabelFrame(
            parent,
            text="Document Storage Overview",
            style='Card.TLabelframe'
        )
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas for grid
        self.grid_canvas = tk.Canvas(
            frame,
            bg='#1e1e2d',
            highlightthickness=0
        )
        self.grid_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Draw initial grid
        self.draw_document_grid()
    
    def create_trends_section(self, parent):
        """Create processing trends graph"""
        frame = ttk.LabelFrame(
            parent,
            text="Processing Trends",
            style='Card.TLabelframe'
        )
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Canvas for graph
        self.trends_canvas = tk.Canvas(
            frame,
            height=200,
            bg='#1e1e2d',
            highlightthickness=0
        )
        self.trends_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Draw initial graph
        self.draw_trends_graph()
    
    def create_types_chart(self, parent):
        """Create document types chart"""
        frame = ttk.LabelFrame(
            parent,
            text="Top Document Types",
            style='Card.TLabelframe'
        )
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas for chart
        self.types_canvas = tk.Canvas(
            frame,
            height=200,
            bg='#1e1e2d',
            highlightthickness=0
        )
        self.types_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Draw initial chart
        self.draw_types_chart()
    
    def draw_storage_progress(self, percentage):
        """Draw circular progress indicator"""
        self.storage_canvas.delete("progress")
        
        # Calculate coordinates
        cx = 100
        cy = 100
        r = 80
        start = 90
        extent = -(percentage * 3.6)  # Convert percentage to degrees
        
        # Draw background circle
        self.storage_canvas.create_arc(
            cx-r, cy-r, cx+r, cy+r,
            start=0, extent=359,
            fill='#2d2d3f',
            tags="progress"
        )
        
        # Draw progress arc
        self.storage_canvas.create_arc(
            cx-r, cy-r, cx+r, cy+r,
            start=start, extent=extent,
            fill='#23a455',
            tags="progress"
        )
    
    def draw_document_grid(self):
        """Draw document storage grid"""
        self.grid_canvas.delete("grid")
        
        # Calculate grid dimensions
        width = self.grid_canvas.winfo_width()
        height = self.grid_canvas.winfo_height()
        
        cell_size = min(width // 10, height // 5)
        margin = 10
        
        # Draw cells
        for row in range(5):
            for col in range(10):
                x = margin + col * (cell_size + 5)
                y = margin + row * (cell_size + 5)
                
                # Randomly determine if cell is occupied
                if random.random() > 0.4:
                    fill = '#23a455'  # Occupied
                else:
                    fill = '#2d2d3f'  # Empty
                
                self.grid_canvas.create_rectangle(
                    x, y, x + cell_size, y + cell_size,
                    fill=fill,
                    outline='#1e1e2d',
                    width=2,
                    tags="grid"
                )
    
    def draw_trends_graph(self):
        """Draw processing trends graph"""
        self.trends_canvas.delete("graph")
        
        # Get canvas dimensions
        width = self.trends_canvas.winfo_width()
        height = self.trends_canvas.winfo_height()
        
        # Sample data (replace with real data)
        data = [30, 45, 60, 40, 55]
        max_value = max(data)
        
        # Calculate points
        points = []
        x_step = width / (len(data) - 1)
        for i, value in enumerate(data):
            x = i * x_step
            y = height - (value / max_value * height * 0.8)
            points.extend([x, y])
        
        # Draw line
        self.trends_canvas.create_line(
            points,
            fill='#1a73e8',
            width=3,
            smooth=True,
            tags="graph"
        )
    
    def draw_types_chart(self):
        """Draw document types horizontal bar chart"""
        self.types_canvas.delete("chart")
        
        # Get canvas dimensions
        width = self.types_canvas.winfo_width()
        height = self.types_canvas.winfo_height()
        
        # Sample data (replace with real data)
        data = [
            ("PDF", 45),
            ("Images", 30),
            ("Text", 15),
            ("Other", 10)
        ]
        
        # Calculate bar dimensions
        bar_height = height / (len(data) + 1)
        max_value = max(d[1] for d in data)
        
        # Draw bars
        for i, (label, value) in enumerate(data):
            y = i * bar_height + 20
            bar_width = (value / max_value) * (width - 100)
            
            # Draw bar
            self.types_canvas.create_rectangle(
                60, y,
                60 + bar_width, y + bar_height - 10,
                fill='#1a73e8',
                tags="chart"
            )
            
            # Draw label
            self.types_canvas.create_text(
                10, y + bar_height/2,
                text=label,
                anchor='w',
                fill='white',
                tags="chart"
            )
            
            # Draw value
            self.types_canvas.create_text(
                width - 10, y + bar_height/2,
                text=f"{value}%",
                anchor='e',
                fill='white',
                tags="chart"
            )
    
    def update_stats(self):
        """Update dashboard statistics"""
        try:
            # Get database stats
            stats = self.db_manager.get_database_stats()
            
            # Update top stats
            self.total_docs.config(text=str(stats['total_documents']))
            self.queue_size.config(text=str(stats.get('processing_queue', 0)))
            
            # Calculate storage
            total_size = sum(doc.get('file_size', 0) for doc in self.db_manager.get_documents())
            size_mb = total_size / (1024 * 1024)
            self.storage_used.config(text=f"{size_mb:.1f} MB")
            
            # Calculate today's documents
            today = datetime.now().date()
            today_docs = sum(
                1 for doc in self.db_manager.get_documents()
                if datetime.fromisoformat(doc['created_at']).date() == today
            )
            self.new_today.config(text=str(today_docs))
            
            # Update visualizations
            self.draw_storage_progress(min(100, size_mb / 1000 * 100))  # Assuming 1GB limit
            self.draw_document_grid()
            self.draw_trends_graph()
            self.draw_types_chart()
            
            # Schedule next update
            self.after(30000, self.update_stats)
            
        except Exception as e:
            self.log_error(f"Error updating dashboard: {e}")

class ChatbotTab(ttk.Frame, LoggerMixin):
    """Chatbot tab for WMS queries"""
    
    def __init__(self, parent, chatbot_manager):
        super().__init__(parent)
        LoggerMixin.__init__(self)
        
        self.chatbot_manager = chatbot_manager
        
        self.setup_ui()
        self.log_info("Chatbot tab initialized")
    
    def setup_ui(self):
        """Setup the chatbot tab UI"""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="WMS Chatbot", font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Chat area
        self.create_chat_area(main_frame)
        
        # Input area
        self.create_input_area(main_frame)
        
        # Control panel
        self.create_control_panel(main_frame)
    
    def create_chat_area(self, parent):
        """Create chat display area with memory panel"""
        # Main container with split view
        chat_container = ttk.Frame(parent)
        chat_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Left side: Chat display
        chat_frame = ttk.LabelFrame(chat_container, text="Conversation")
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Chat text area
        self.chat_text = scrolledtext.ScrolledText(
            chat_frame,
            height=20,
            wrap=tk.WORD,
            font=('Segoe UI', 10)
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.chat_text.config(state=tk.DISABLED)
        
        # Right side: Memory display
        memory_frame = ttk.LabelFrame(chat_container, text="Conversation Memory")
        memory_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Set fixed width for memory frame
        memory_frame.update()
        memory_frame.pack_propagate(False)
        memory_frame.configure(width=300)
        
        self.memory_text = scrolledtext.ScrolledText(
            memory_frame,
            height=20,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg='#f5f5f5'  # Light gray background
        )
        self.memory_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.memory_text.config(state=tk.DISABLED)
    
    def create_input_area(self, parent):
        """Create input area"""
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Text input
        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Send button
        ttk.Button(input_frame, text="Send", command=self.send_message).pack(side=tk.RIGHT)
        
        # Bind Enter key
        self.input_entry.bind('<Return>', lambda e: self.send_message())
    
    def create_control_panel(self, parent):
        """Create control panel"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X)
        
        ttk.Button(control_frame, text="Clear Chat", command=self.clear_chat).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="Voice Input", command=self.voice_input).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="Image Input", command=self.image_input).pack(side=tk.LEFT)
    
    def send_message(self):
        """Send message to chatbot"""
        message = self.input_entry.get().strip()
        if not message:
            return
        
        # Add user message to chat
        self.add_message("User", message)
        
        # Clear input
        self.input_entry.delete(0, tk.END)
        
        # Get response from chatbot
        self.get_chatbot_response(message)
    
    def add_message(self, sender: str, message: str):
        """Add message to chat area"""
        self.chat_text.config(state=tk.NORMAL)
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        self.chat_text.insert(tk.END, f"[{timestamp}] {sender}: {message}\n\n")
        
        # Scroll to bottom
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)
    
    def get_chatbot_response(self, message: str):
        """Get response from chatbot"""
        try:
            # Process query using chatbot manager
            result = self.chatbot_manager.process_query(message)
            
            # Add response to chat
            if result.get('success'):
                response = result['response']
                
                # Add sources if available
                if result.get('sources'):
                    response += "\n\nSource Documents:"
                    for source in result['sources']:
                        response += f"\n[Doc ID: {source.get('document_id', 'N/A')}] {source['filename']}"
                        if source.get('content_preview'):
                            response += f"\nPreview: {source['content_preview']}\n"
                
                self.add_message("WMS Chatbot", response)
                
                # Update memory display
                self.update_memory_display()
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                self.add_message("System", f"Error: {error_msg}")
            
        except Exception as e:
            self.log_error(f"Error getting chatbot response: {e}")
            self.add_message("System", f"Error: {str(e)}")
            
    def update_memory_display(self):
        """Update memory display with current conversation history"""
        try:
            # Get conversation history from chatbot
            history = self.chatbot_manager.get_conversation_history()
            
            # Update memory display
            self.memory_text.config(state=tk.NORMAL)
            self.memory_text.delete(1.0, tk.END)
            
            for entry in history:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M:%S")
                role = entry['role'].title()
                content = entry['content']
                
                # Format memory entry
                memory_text = f"[{timestamp}] {role}:\n{content}\n\n"
                self.memory_text.insert(tk.END, memory_text)
            
            self.memory_text.see(tk.END)
            self.memory_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.log_error(f"Error updating memory display: {e}")
            self.memory_text.config(state=tk.NORMAL)
            self.memory_text.delete(1.0, tk.END)
            self.memory_text.insert(tk.END, "Error loading conversation memory")
            self.memory_text.config(state=tk.DISABLED)
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)
        self.chat_text.config(state=tk.DISABLED)
    
    def voice_input(self):
        """Handle voice input"""
        messagebox.showinfo("Voice Input", "Voice input functionality will be implemented")
    
    def image_input(self):
        """Handle image input"""
        file_path = filedialog.askopenfilename(
            title="Select image for analysis",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            try:
                # Add message about uploaded image
                self.add_message("User", f"Uploaded image: {os.path.basename(file_path)}")
                
                # Optional: Get specific query from user
                query = self.input_entry.get().strip()
                
                # Process image with chatbot
                result = self.chatbot_manager.process_image_query(file_path, query)
                
                if result.get('success'):
                    self.add_message("WMS Chatbot", result['response'])
                else:
                    error_msg = result.get('error', 'Unknown error occurred')
                    self.add_message("System", f"Error: {error_msg}")
                    
                # Clear input field
                self.input_entry.delete(0, tk.END)
                
            except Exception as e:
                self.log_error(f"Error processing image: {e}")
                self.add_message("System", f"Error processing image: {str(e)}") 