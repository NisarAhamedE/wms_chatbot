import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import threading
import queue
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import time
from datetime import datetime

from .logger import LoggerMixin

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
        self.drop_zone.configure(bg='lightgreen')
    
    def on_leave(self, event):
        """Handle mouse leave"""
        self.drop_zone.configure(bg='lightblue')


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
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Document Capture & Processing", font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Create notebook for different input methods
        self.input_notebook = ttk.Notebook(main_frame)
        self.input_notebook.pack(fill=tk.BOTH, expand=True)
        
        # File upload tab
        self.create_file_upload_tab()
        
        # Text input tab
        self.create_text_input_tab()
        
        # Screenshot tab
        self.create_screenshot_tab()
        
        # Processing status
        self.create_status_section(main_frame)
    
    def create_file_upload_tab(self):
        """Create file upload tab"""
        file_frame = ttk.Frame(self.input_notebook)
        self.input_notebook.add(file_frame, text="📁 File Upload")
        
        # Drag & drop zone
        self.drag_drop = DragDropHandler(file_frame, self.process_files)
        self.drag_drop.drop_zone.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # File list
        self.file_list_frame = ttk.LabelFrame(file_frame, text="Selected Files")
        self.file_list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(self.file_list_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.file_listbox = tk.Listbox(list_frame, height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(file_frame)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        ttk.Button(button_frame, text="Add Files", command=self.browse_files).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Clear List", command=self.clear_file_list).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Process Files", command=self.process_selected_files).pack(side=tk.RIGHT)
    
    def create_text_input_tab(self):
        """Create text input tab"""
        text_frame = ttk.Frame(self.input_notebook)
        self.input_notebook.add(text_frame, text="📝 Text Input")
        
        # Text input area
        text_label = ttk.Label(text_frame, text="Enter or paste text content:")
        text_label.pack(anchor=tk.W, padx=20, pady=(20, 5))
        
        # Text area with scrollbar
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        self.text_input = scrolledtext.ScrolledText(text_container, height=15, wrap=tk.WORD)
        self.text_input.pack(fill=tk.BOTH, expand=True)
        
        # Character/word count
        self.text_stats_label = ttk.Label(text_frame, text="Characters: 0 | Words: 0")
        self.text_stats_label.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Bind text change event
        self.text_input.bind('<KeyRelease>', self.update_text_stats)
        
        # Buttons
        button_frame = ttk.Frame(text_frame)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        ttk.Button(button_frame, text="Clear Text", command=self.clear_text).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Process Text", command=self.process_text).pack(side=tk.RIGHT)
    
    def create_screenshot_tab(self):
        """Create screenshot tab"""
        screenshot_frame = ttk.Frame(self.input_notebook)
        self.input_notebook.add(screenshot_frame, text="📸 Screenshot")
        
        # Screenshot controls
        control_frame = ttk.Frame(screenshot_frame)
        control_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Manual capture controls
        manual_frame = ttk.LabelFrame(control_frame, text="Manual Capture")
        manual_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Coordinate inputs
        coord_frame = ttk.Frame(manual_frame)
        coord_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(coord_frame, text="X:").grid(row=0, column=0, padx=(0, 5))
        self.x_var = tk.IntVar(value=0)
        ttk.Entry(coord_frame, textvariable=self.x_var, width=8).grid(row=0, column=1, padx=(0, 10))
        
        ttk.Label(coord_frame, text="Y:").grid(row=0, column=2, padx=(0, 5))
        self.y_var = tk.IntVar(value=0)
        ttk.Entry(coord_frame, textvariable=self.y_var, width=8).grid(row=0, column=3, padx=(0, 10))
        
        ttk.Label(coord_frame, text="Width:").grid(row=0, column=4, padx=(0, 5))
        self.width_var = tk.IntVar(value=800)
        ttk.Entry(coord_frame, textvariable=self.width_var, width=8).grid(row=0, column=5, padx=(0, 10))
        
        ttk.Label(coord_frame, text="Height:").grid(row=0, column=6, padx=(0, 5))
        self.height_var = tk.IntVar(value=600)
        ttk.Entry(coord_frame, textvariable=self.height_var, width=8).grid(row=0, column=7, padx=(0, 10))
        
        # Capture buttons
        button_frame = ttk.Frame(manual_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(button_frame, text="Capture Area", command=self.capture_manual_area).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Select Area", command=self.take_screenshot).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Center Position", command=self.center_position).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Load Image", command=self.load_image).pack(side=tk.LEFT)
        
        # Screenshot preview
        preview_frame = ttk.LabelFrame(screenshot_frame, text="Screenshot Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.screenshot_label = ttk.Label(preview_frame, text="No screenshot taken")
        self.screenshot_label.pack(expand=True)
        
        # Process and clear buttons
        button_frame = ttk.Frame(screenshot_frame)
        button_frame.pack(pady=(0, 20))
        
        ttk.Button(button_frame, text="Process Screenshot", command=self.process_screenshot).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Clear", command=self.clear_screenshot).pack(side=tk.LEFT)
    
    def create_status_section(self, parent):
        """Create status section"""
        status_frame = ttk.LabelFrame(parent, text="Processing Status")
        status_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(status_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        # Status label
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(anchor=tk.W, padx=10, pady=(0, 10))
        
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
    
    def take_screenshot(self):
        """Take screenshot with area selection"""
        try:
            # Start area selection
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
            self.selection_window.attributes('-alpha', 0.3)  # Semi-transparent
            self.selection_window.attributes('-topmost', True)
            self.selection_window.overrideredirect(True)  # Remove window decorations
            
            # Create canvas for selection
            self.selection_canvas = tk.Canvas(self.selection_window, 
                                            width=screen_width, 
                                            height=screen_height,
                                            bg='black',
                                            highlightthickness=0)
            self.selection_canvas.pack()
            
            # Bind mouse events
            self.selection_canvas.bind('<Button-1>', self.on_selection_start)
            self.selection_canvas.bind('<B1-Motion>', self.on_selection_drag)
            self.selection_canvas.bind('<ButtonRelease-1>', self.on_selection_end)
            self.selection_canvas.bind('<Escape>', self.cancel_selection)
            
            # Add instructions
            instruction_text = "Click and drag to select screenshot area. Press ESC to cancel."
            self.selection_canvas.create_text(screen_width//2, 50, 
                                            text=instruction_text,
                                            fill='white', font=('Arial', 16, 'bold'))
            
        except Exception as e:
            # Show main window back
            root_window = self.winfo_toplevel()
            root_window.deiconify()
            raise e
    
    def on_selection_start(self, event):
        """Handle selection start"""
        self.selection_start = (event.x, event.y)
        self.selection_rect = None
    
    def on_selection_drag(self, event):
        """Handle selection drag"""
        if self.selection_start:
            # Remove previous rectangle
            if self.selection_rect:
                self.selection_canvas.delete(self.selection_rect)
            
            # Draw new rectangle
            x1, y1 = self.selection_start
            x2, y2 = event.x, event.y
            
            self.selection_rect = self.selection_canvas.create_rectangle(
                x1, y1, x2, y2, outline='red', width=2, fill='blue', stipple='gray50'
            )
    
    def on_selection_end(self, event):
        """Handle selection end and capture screenshot"""
        if self.selection_start:
            x1, y1 = self.selection_start
            x2, y2 = event.x, event.y
            
            # Calculate coordinates and dimensions
            x = min(x1, x2)
            y = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            
            # Validate minimum dimensions
            if width < 10 or height < 10:
                return
            
            # Close selection window
            self.selection_window.destroy()
            self.selection_window = None
            self.selection_canvas = None
            
            # Show main window
            root_window = self.winfo_toplevel()
            root_window.deiconify()
            root_window.lift()
            root_window.focus_force()
            
            # Capture screenshot
            self.capture_screenshot_area(x, y, width, height)
    
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
            
            # Capture screenshot
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            self.current_screenshot = screenshot
            
            # Display preview
            self.display_screenshot_preview(screenshot)
            
            # Save screenshot to temporary file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            temp_path = os.path.join("temp", filename)
            
            # Create temp directory if it doesn't exist
            os.makedirs("temp", exist_ok=True)
            
            screenshot.save(temp_path)
            self.current_screenshot_path = temp_path
            
            self.status_label.config(text=f"Screenshot captured: ({x}, {y}) {width}x{height}")
            
        except Exception as e:
            self.log_error(f"Error capturing screenshot: {e}")
            messagebox.showerror("Error", f"Failed to capture screenshot: {str(e)}")
            self.status_label.config(text="Screenshot capture failed")
    
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
        """Process screenshot"""
        if hasattr(self, 'current_screenshot_path') and self.current_screenshot_path:
            # Add to processing queue
            self.processing_queue.put({
                'type': 'screenshot',
                'screenshot_path': self.current_screenshot_path,
                'callback': self.on_screenshot_processed
            })
            
            self.status_label.config(text="Processing screenshot...")
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
            messagebox.showinfo("Success", "Screenshot processed successfully")
        else:
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
        
        ttk.Button(button_frame, text="Refresh", command=self.refresh_file_list).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_selected).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Export Selected", command=self.export_selected).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Database Stats", command=self.show_stats).pack(side=tk.RIGHT)
    
    def create_document_list(self, parent):
        """Create document list"""
        list_frame = ttk.LabelFrame(parent, text="Documents")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Treeview for documents
        columns = ('Filename', 'Type', 'Size', 'Date', 'Status')
        self.doc_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            self.doc_tree.heading(col, text=col)
            self.doc_tree.column(col, width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.doc_tree.yview)
        self.doc_tree.configure(yscrollcommand=scrollbar.set)
        
        self.doc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # Bind selection event
        self.doc_tree.bind('<<TreeviewSelect>>', self.on_document_selected)
    
    def create_details_panel(self, parent):
        """Create details panel"""
        details_frame = ttk.LabelFrame(parent, text="Document Details")
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Details text area
        self.details_text = scrolledtext.ScrolledText(details_frame, height=10, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def refresh_file_list(self):
        """Refresh the document list"""
        try:
            # Clear existing items
            for item in self.doc_tree.get_children():
                self.doc_tree.delete(item)
            
            # Get documents from database
            documents = self.db_manager.get_documents()
            
            # Add to treeview
            for doc in documents:
                size_mb = doc.get('file_size', 0) / (1024 * 1024)
                self.doc_tree.insert('', tk.END, values=(
                    doc.get('filename', 'Unknown'),
                    doc.get('file_type', 'Unknown'),
                    f"{size_mb:.2f} MB",
                    doc.get('created_at', 'Unknown'),
                    doc.get('status', 'Unknown')
                ), tags=(doc.get('document_id', ''),))
            
            self.log_info(f"Loaded {len(documents)} documents")
            
        except Exception as e:
            self.log_error(f"Error refreshing file list: {e}")
            messagebox.showerror("Error", f"Failed to refresh file list: {str(e)}")
    
    def on_document_selected(self, event):
        """Handle document selection"""
        selection = self.doc_tree.selection()
        if not selection:
            return
        
        # Get document ID from tags
        item = self.doc_tree.item(selection[0])
        document_id = item['tags'][0] if item['tags'] else None
        
        if document_id:
            self.show_document_details(document_id)
    
    def show_document_details(self, document_id):
        """Show document details"""
        try:
            document = self.db_manager.get_document_by_id(document_id)
            if document:
                details = f"""Document ID: {document.get('document_id', 'N/A')}
Filename: {document.get('filename', 'N/A')}
File Type: {document.get('file_type', 'N/A')}
File Size: {document.get('file_size', 0)} bytes
Created: {document.get('created_at', 'N/A')}
Status: {document.get('status', 'N/A')}

Content Preview:
{document.get('content', 'No content')[:1000]}..."""
                
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details)
            else:
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, "Document not found")
                
        except Exception as e:
            self.log_error(f"Error showing document details: {e}")
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, f"Error loading details: {str(e)}")
    
    def delete_selected(self):
        """Delete selected documents"""
        selection = self.doc_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select documents to delete")
            return
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Delete {len(selection)} selected document(s)?"):
            return
        
        # Delete documents
        deleted_count = 0
        for item in selection:
            document_id = self.doc_tree.item(item)['tags'][0] if self.doc_tree.item(item)['tags'] else None
            if document_id:
                if self.db_manager.delete_document(document_id):
                    deleted_count += 1
        
        # Refresh list
        self.refresh_file_list()
        messagebox.showinfo("Delete Complete", f"Deleted {deleted_count} document(s)")
    
    def export_selected(self):
        """Export selected documents"""
        selection = self.doc_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select documents to export")
            return
        
        # Choose export directory
        export_dir = filedialog.askdirectory(title="Choose export directory")
        if not export_dir:
            return
        
        # Export documents
        exported_count = 0
        for item in selection:
            document_id = self.doc_tree.item(item)['tags'][0] if self.doc_tree.item(item)['tags'] else None
            if document_id:
                document = self.db_manager.get_document_by_id(document_id)
                if document:
                    try:
                        export_path = os.path.join(export_dir, f"{document['filename']}.txt")
                        with open(export_path, 'w', encoding='utf-8') as f:
                            f.write(document.get('content', ''))
                        exported_count += 1
                    except Exception as e:
                        self.log_error(f"Error exporting document {document_id}: {e}")
        
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
        """Create chat display area"""
        chat_frame = ttk.LabelFrame(parent, text="Conversation")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Chat text area
        self.chat_text = scrolledtext.ScrolledText(chat_frame, height=20, wrap=tk.WORD)
        self.chat_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Make chat area read-only
        self.chat_text.config(state=tk.DISABLED)
    
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
            # This would integrate with the chatbot manager
            # For now, show a placeholder response
            response = f"WMS Chatbot response to: {message}\n\nThis is a placeholder response. The actual chatbot integration will be implemented."
            self.add_message("WMS Chatbot", response)
            
        except Exception as e:
            self.log_error(f"Error getting chatbot response: {e}")
            self.add_message("System", f"Error: {str(e)}")
    
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
            self.add_message("User", f"Uploaded image: {os.path.basename(file_path)}")
            # Process image with chatbot
            self.get_chatbot_response(f"Analyze this image: {file_path}") 