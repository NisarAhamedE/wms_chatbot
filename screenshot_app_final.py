import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pyautogui
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageEnhance
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
import base64
import io

# Try to import Azure OpenAI
try:
    from openai import AzureOpenAI
    from dotenv import load_dotenv
    load_dotenv()
    AZURE_OPENAI_AVAILABLE = True
    print("✓ Azure OpenAI is available")
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    print("⚠ Azure OpenAI not available - LLM features disabled")

# Try to import pytesseract, but handle if not available
try:
    import pytesseract
    # Set the correct Tesseract path for user installation
    tesseract_path = r"C:\Users\NisarAhamed\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        TESSERACT_AVAILABLE = True
        print("✓ Tesseract OCR is available and configured")
    else:
        TESSERACT_AVAILABLE = False
        print("⚠ Tesseract executable not found at expected path")
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠ Tesseract OCR not available - OCR features disabled")

class ScreenshotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screenshot App")
        self.root.geometry("400x500")
        self.root.configure(bg='#f0f0f0')
        
        # Variables
        self.width_var = tk.IntVar(value=800)
        self.height_var = tk.IntVar(value=600)
        self.x_var = tk.IntVar(value=0)
        self.y_var = tk.IntVar(value=0)
        self.output_dir = tk.StringVar(value="screenshots")
        self.current_screenshot = None
        self.screenshot_count = 0
        self.extracted_text = ""
        self.auto_mode = False
        self.selection_window = None
        self.selection_canvas = None
        self.selection_start = None
        self.selection_rect = None
        self.text_extraction_method = tk.StringVar(value="none")  # "none", "ocr", "llm"
        self.azure_client = None
        
        # Create output directory
        if not os.path.exists(self.output_dir.get()):
            os.makedirs(self.output_dir.get())
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Screenshot App", 
                               font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # OCR and LLM Status
        status_text = ""
        status_color = "black"
        
        if TESSERACT_AVAILABLE:
            status_text += "✓ OCR (Tesseract) "
            status_color = "green"
        else:
            status_text += "⚠️ OCR (Tesseract) not available "
            status_color = "orange"
            
        if AZURE_OPENAI_AVAILABLE:
            status_text += "✓ Azure OpenAI "
            if status_color == "green":
                status_color = "green"
            else:
                status_color = "blue"
        else:
            status_text += "⚠️ Azure OpenAI not available "
            if status_color == "orange":
                status_color = "red"
            else:
                status_color = "orange"
        
        ocr_status = ttk.Label(main_frame, text=status_text, 
                               font=('Arial', 8), foreground=status_color)
        ocr_status.grid(row=1, column=0, columnspan=2, pady=(0, 5))
        
        # Text Extraction Method Frame
        extraction_frame = ttk.LabelFrame(main_frame, text="Text Extraction", padding="5")
        extraction_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # OCR Radio Button
        self.ocr_radio = ttk.Radiobutton(extraction_frame, text="📷 OCR", 
                                           variable=self.text_extraction_method, 
                                           value="ocr",
                                           command=self.on_extraction_method_change)
        self.ocr_radio.grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        
        # LLM Radio Button
        self.llm_radio = ttk.Radiobutton(extraction_frame, text="🤖 LLM", 
                                           variable=self.text_extraction_method, 
                                           value="llm",
                                           command=self.on_extraction_method_change)
        self.llm_radio.grid(row=0, column=1, sticky=tk.W)
        
        # Extraction Status
        self.extraction_status = ttk.Label(extraction_frame, text="No method selected", 
                                    font=('Arial', 8), foreground='gray')
        self.extraction_status.grid(row=1, column=0, columnspan=2, pady=(2, 0), sticky=tk.W)
        
        # Auto Mode Frame
        auto_frame = ttk.LabelFrame(main_frame, text="Auto Mode", padding="5")
        auto_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Auto Mode Button
        self.auto_btn = ttk.Button(auto_frame, text="🚀 Auto Mode", 
                                   command=self.toggle_auto_mode, style='Accent.TButton')
        self.auto_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Auto Mode Status
        self.auto_status = ttk.Label(auto_frame, text="Disabled", 
                                     font=('Arial', 8), foreground='gray')
        self.auto_status.grid(row=0, column=1, padx=(10, 0))
        
        # Dimensions frame
        dim_frame = ttk.LabelFrame(main_frame, text="Manual Settings", padding="5")
        dim_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Width
        ttk.Label(dim_frame, text="Width:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        width_entry = ttk.Entry(dim_frame, textvariable=self.width_var, width=10)
        width_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Height
        ttk.Label(dim_frame, text="Height:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        height_entry = ttk.Entry(dim_frame, textvariable=self.height_var, width=10)
        height_entry.grid(row=0, column=3, sticky=tk.W)
        
        # Position frame
        pos_frame = ttk.LabelFrame(main_frame, text="Position (X, Y)", padding="5")
        pos_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # X coordinate
        ttk.Label(pos_frame, text="X:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        x_entry = ttk.Entry(pos_frame, textvariable=self.x_var, width=10)
        x_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Y coordinate
        ttk.Label(pos_frame, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        y_entry = ttk.Entry(pos_frame, textvariable=self.y_var, width=10)
        y_entry.grid(row=0, column=3, sticky=tk.W)
        
        # Center position button
        ttk.Button(pos_frame, text="Center", command=self.center_position).grid(row=0, column=4, padx=(20, 0))
        
        # Output directory frame
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="5")
        output_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Entry(output_frame, textvariable=self.output_dir, width=30).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(output_frame, text="Browse", command=self.browse_output_dir).grid(row=0, column=1)
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=7, column=0, columnspan=2, pady=(0, 10))
        
                        # Capture button
        self.capture_btn = ttk.Button(control_frame, text="📷 Capture", 
                                      command=self.capture_screenshot, style='Accent.TButton')
        self.capture_btn.grid(row=0, column=0, padx=(0, 5))
        
        # Save to markdown button
        self.save_btn = ttk.Button(control_frame, text="💾 Save", 
                                   command=self.save_to_markdown, state='disabled')
        self.save_btn.grid(row=0, column=1, padx=(0, 5))
        
        # Read markdown button
        self.read_btn = ttk.Button(control_frame, text="📖 Read", 
                                   command=self.read_and_save_content, state='disabled')
        self.read_btn.grid(row=0, column=2, padx=(0, 5))
        
        # Clear button
        ttk.Button(control_frame, text="🗑️ Clear", command=self.clear_screenshot).grid(row=0, column=3)
        
        # Text content frame
        text_frame = ttk.LabelFrame(main_frame, text="Extracted Text", padding="5")
        text_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Text area for extracted content
        self.text_area = tk.Text(text_frame, height=4, width=45, wrap=tk.WORD, font=('Consolas', 8))
        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=text_scrollbar.set)
        
        self.text_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="5")
        preview_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Canvas for preview
        self.canvas = tk.Canvas(preview_frame, width=250, height=150, bg='white', relief='sunken', bd=1)
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=10, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="Ready", 
                                     font=('Arial', 8))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(8, weight=1)
        main_frame.rowconfigure(9, weight=1)
        output_frame.columnconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        auto_frame.columnconfigure(1, weight=1)
        extraction_frame.columnconfigure(1, weight=1)
        
    def on_extraction_method_change(self):
        """Handle text extraction method change"""
        method = self.text_extraction_method.get()
        
        if method == "ocr":
            if not TESSERACT_AVAILABLE:
                self.text_extraction_method.set("none")
                return
                
            self.extraction_status.config(text="OCR enabled", foreground='green')
            self.status_label.config(text="OCR ready")
            
        elif method == "llm":
            if not AZURE_OPENAI_AVAILABLE:
                self.text_extraction_method.set("none")
                return
                
            # Initialize Azure OpenAI client
            if not self.initialize_azure_client():
                self.text_extraction_method.set("none")
                return
                
            self.extraction_status.config(text="LLM enabled", foreground='green')
            self.status_label.config(text="LLM ready")
            
        else:  # "none"
            self.extraction_status.config(text="No method selected", foreground='gray')
            self.status_label.config(text="Ready")
    
    def initialize_azure_client(self):
        """Initialize Azure OpenAI client"""
        try:
            api_key = os.getenv('AZURE_OPENAI_KEY')
            endpoint = os.getenv('AZURE_OPENAI_URL')
            deployment = os.getenv('AZURE_DEPLOYMENT')
            api_version = os.getenv('AZURE_API_VERSION', '2024-12-01-preview')
            
            if not all([api_key, endpoint, deployment]):
                return False
            
            self.azure_client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version
            )
            
            # Test the connection
            test_response = self.azure_client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            
            return True
            
        except Exception as e:
            return False
    
    def extract_text_with_azure_openai(self, image):
        """Extract exact text from image using Azure OpenAI Vision"""
        try:
            # Convert PIL image to base64
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            # Create the prompt for exact text extraction
            prompt = """Extract ALL the text from this image exactly as it appears. 
            
IMPORTANT INSTRUCTIONS:
- Extract ONLY the text that is visible in the image
- Do NOT add any interpretations, explanations, or additional words
- Do NOT summarize or rephrase the text
- Do NOT add any commentary about the image
- Preserve the exact spelling, punctuation, and formatting
- If there are multiple lines, preserve the line breaks
- If there are tables, preserve the table structure
- If there are numbers, extract them exactly as shown
- Return ONLY the raw text content, nothing else

Just extract the text exactly as it appears in the image:"""
            
            # Make the API call
            response = self.azure_client.chat.completions.create(
                model=os.getenv('AZURE_DEPLOYMENT'),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.0  # Use 0 temperature for exact extraction
            )
            
            extracted_text = response.choices[0].message.content.strip()
            
            # Clean up any potential LLM artifacts
            if extracted_text.startswith("Here's the text from the image:"):
                extracted_text = extracted_text.replace("Here's the text from the image:", "").strip()
            if extracted_text.startswith("The text in the image is:"):
                extracted_text = extracted_text.replace("The text in the image is:", "").strip()
            if extracted_text.startswith("Text extracted:"):
                extracted_text = extracted_text.replace("Text extracted:", "").strip()
            
            return extracted_text if extracted_text else "No text could be extracted from the image."
            
        except Exception as e:
            return f"Error extracting text with Azure OpenAI: {str(e)}"
        
    def toggle_auto_mode(self):
        """Toggle Auto Mode on/off"""
        self.auto_mode = not self.auto_mode
        
        if self.auto_mode:
            self.auto_btn.config(text="⏹️ Disable")
            self.auto_status.config(text="Enabled", foreground='green')
            self.status_label.config(text="Select area")
            
            # Start area selection immediately
            self.start_auto_selection()
        else:
            self.auto_btn.config(text="🚀 Auto Mode")
            self.auto_status.config(text="Disabled", foreground='gray')
            self.status_label.config(text="Ready")
            
            # Cancel any ongoing selection
            if self.selection_window:
                self.cancel_selection()
    
    def start_auto_selection(self):
        """Start automatic area selection for Auto Mode"""
        try:
            self.root.withdraw()  # Hide main window
            self.status_label.config(text="Auto Mode: Select area with mouse...")
            
            # Create selection window
            self.create_selection_window()
            
        except Exception as e:
            self.root.deiconify()
    
    def create_selection_window(self):
        """Create a fullscreen transparent window for area selection"""
        try:
            # Get screen dimensions
            screen_width, screen_height = pyautogui.size()
            
            # Create selection window
            self.selection_window = tk.Toplevel()
            self.selection_window.title("Select Area")
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
            if self.auto_mode:
                instruction_text = "AUTO MODE: Click and drag to select area → Auto capture and save → Auto disable"
            else:
                instruction_text = "Click and drag to select area. Press ESC to cancel."
            
            self.selection_canvas.create_text(screen_width//2, 50, 
                                            text=instruction_text,
                                            fill='white', font=('Arial', 16, 'bold'))
            
        except Exception as e:
            self.root.deiconify()
    
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
        """Handle selection end"""
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
            
            # Update variables
            self.x_var.set(x)
            self.y_var.set(y)
            self.width_var.set(width)
            self.height_var.set(height)
            
            # Close selection window
            self.selection_window.destroy()
            self.selection_window = None
            self.selection_canvas = None
            
            # Show main window
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            
            if self.auto_mode:
                # Auto Mode: Automatically capture, read, and save
                self.auto_capture_and_save()
            else:
                # Manual Mode: Just update status
                self.status_label.config(text=f"Area: ({x}, {y}) {width}x{height}")
    
    def auto_capture_and_save(self):
        """Automatically capture, read text, and save in Auto Mode"""
        try:
            self.status_label.config(text="Capturing...")
            
            # Capture screenshot
            width = self.width_var.get()
            height = self.height_var.get()
            x = self.x_var.get()
            y = self.y_var.get()
            
            # Validate dimensions
            if width <= 0 or height <= 0:
                return
            
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            self.current_screenshot = screenshot
            
            # Display preview
            self.display_preview(screenshot)
            
            # Extract text based on selected method
            method = self.text_extraction_method.get()
            
            if method == "llm" and self.azure_client:
                extracted_text = self.extract_text_with_azure_openai(screenshot)
                self.extracted_text = extracted_text
                
                # Display extracted text
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(1.0, extracted_text)
                
                # Auto save with content
                self.save_to_individual_markdown(extracted_text)
                self.status_label.config(text="LLM saved")
                
                # Auto disable after successful capture and save
                self.root.after(1000, self.auto_disable_after_success)
            elif method == "ocr" and TESSERACT_AVAILABLE:
                extracted_text = self.extract_text_from_image(screenshot)
                self.extracted_text = extracted_text
                
                # Display extracted text
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(1.0, extracted_text)
                
                # Auto save with content
                self.save_to_individual_markdown(extracted_text)
                self.status_label.config(text="OCR saved")
                
                # Auto disable after successful capture and save
                self.root.after(1000, self.auto_disable_after_success)
            else:
                # Save without text extraction
                self.save_to_markdown()
                self.status_label.config(text="Saved")
                # Auto disable after successful capture and save
                self.root.after(1000, self.auto_disable_after_success)
            
        except Exception as e:
            self.status_label.config(text="Error")
    
    def auto_disable_after_success(self):
        """Auto disable Auto Mode after successful capture and save"""
        if self.auto_mode:
            self.auto_mode = False
            self.auto_btn.config(text="🚀 Auto Mode")
            self.auto_status.config(text="Disabled", foreground='gray')
            self.status_label.config(text="Ready")
    
    def cancel_selection(self, event=None):
        """Cancel area selection"""
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
            self.selection_canvas = None
        
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        
        if self.auto_mode:
            self.status_label.config(text="Selection cancelled")
            # Restart selection after a short delay
            self.root.after(1000, self.start_auto_selection)
        else:
            self.status_label.config(text="Cancelled")
        
    def center_position(self):
        """Calculate center position based on current dimensions"""
        try:
            screen_width, screen_height = pyautogui.size()
            width = self.width_var.get()
            height = self.height_var.get()
            
            # Validate dimensions
            if width <= 0 or height <= 0:
                return
            
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            self.x_var.set(max(0, x))
            self.y_var.set(max(0, y))
            
            self.status_label.config(text=f"Centered: ({x}, {y})")
        except Exception as e:
            pass
        
    def browse_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)
            if not os.path.exists(directory):
                os.makedirs(directory)
                
    def capture_screenshot(self):
        try:
            self.status_label.config(text="Capturing...")
            self.capture_btn.config(state='disabled')
            
            # Get capture parameters
            width = self.width_var.get()
            height = self.height_var.get()
            x = self.x_var.get()
            y = self.y_var.get()
            
            if width <= 0 or height <= 0:
                return
            
            if x < 0 or y < 0:
                return
                
            # Get screen size
            screen_width, screen_height = pyautogui.size()
            
            # Check if coordinates are within screen bounds
            if x + width > screen_width or y + height > screen_height:
                pass
            
            # Capture screenshot
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            self.current_screenshot = screenshot
            
            # Display preview
            self.display_preview(screenshot)
            
            # Clear previous text
            self.text_area.delete(1.0, tk.END)
            self.extracted_text = ""
            
            self.save_btn.config(state='normal')
            method = self.text_extraction_method.get()
            if (method == "ocr" and TESSERACT_AVAILABLE) or (method == "llm" and self.azure_client):
                self.read_btn.config(state='normal')
            else:
                self.read_btn.config(state='disabled')
            self.status_label.config(text=f"Captured: ({x}, {y}) {width}x{height}")
            
        except Exception as e:
            self.status_label.config(text="Capture failed")
        finally:
            self.capture_btn.config(state='normal')
    
    def extract_text_from_image(self, image):
        """Extract text from image using advanced preprocessing and multiple OCR methods for maximum accuracy"""
        if not TESSERACT_AVAILABLE:
            return "OCR not available. Please install Tesseract OCR for text extraction.\n\nTo install Tesseract:\n1. Download from: https://github.com/UB-Mannheim/tesseract/wiki\n2. Install and add to PATH\n3. Restart the app"
        
        try:
            # Create a temporary directory in user's home directory
            user_temp_dir = os.path.expanduser('~\\AppData\\Local\\Temp\\tesseract_ocr')
            if not os.path.exists(user_temp_dir):
                os.makedirs(user_temp_dir)
            
            # Convert PIL image to OpenCV for preprocessing
            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Try multiple preprocessing approaches
            results = []
            
            # Method 1: Enhanced image with PIL
            enhancer = ImageEnhance.Contrast(image)
            enhanced = enhancer.enhance(3.0)  # High contrast
            enhancer = ImageEnhance.Sharpness(enhanced)
            sharpened = enhancer.enhance(3.0)  # High sharpness
            enhancer = ImageEnhance.Brightness(sharpened)
            brightened = enhancer.enhance(1.3)  # Slightly brighter
            
            # Save enhanced image
            temp_image_path = os.path.join(user_temp_dir, 'enhanced_image.png')
            brightened.save(temp_image_path)
            
            # Set environment variables for Tesseract
            env = os.environ.copy()
            env['TMP'] = user_temp_dir
            env['TEMP'] = user_temp_dir
            env['TMPDIR'] = user_temp_dir
            
            # Try multiple OCR configurations
            configs = [
                ['--psm', '6', '--dpi', '300', '--oem', '3'],
                ['--psm', '3', '--dpi', '300', '--oem', '3'],
                ['--psm', '0', '--dpi', '300', '--oem', '3'],
                ['--psm', '6', '--dpi', '300', '--oem', '1'],
                ['--psm', '6', '--dpi', '300', '--oem', '3', '-c', 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:()[]{}"\'-_/\\| '],
                ['--psm', '6', '--dpi', '300', '--oem', '3', '-c', 'tessedit_pageseg_mode=6'],
                ['--psm', '6', '--dpi', '300', '--oem', '3', '-c', 'tessedit_do_invert=0'],
                ['--psm', '6', '--dpi', '300', '--oem', '3', '-c', 'textord_heavy_nr=1'],
                ['--psm', '6', '--dpi', '300', '--oem', '3', '-c', 'textord_min_linesize=2'],
                ['--psm', '6', '--dpi', '300', '--oem', '3', '-c', 'tessedit_ocr_engine_mode=3']
            ]
            
            for config in configs:
                try:
                    cmd = [tesseract_path, temp_image_path, 'stdout'] + config
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        results.append(result.stdout.strip())
                except:
                    continue
            
            # Method 2: Grayscale with Otsu thresholding
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pil_thresh = Image.fromarray(thresh)
            temp_thresh_path = os.path.join(user_temp_dir, 'thresh_image.png')
            pil_thresh.save(temp_thresh_path)
            
            for config in configs[:5]:  # Try first 5 configs
                try:
                    cmd = [tesseract_path, temp_thresh_path, 'stdout'] + config
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        results.append(result.stdout.strip())
                except:
                    continue
            
            # Method 3: Adaptive thresholding
            adaptive_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            pil_adaptive = Image.fromarray(adaptive_thresh)
            temp_adaptive_path = os.path.join(user_temp_dir, 'adaptive_image.png')
            pil_adaptive.save(temp_adaptive_path)
            
            for config in configs[:5]:
                try:
                    cmd = [tesseract_path, temp_adaptive_path, 'stdout'] + config
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        results.append(result.stdout.strip())
                except:
                    continue
            
            # Method 4: Enhanced contrast with OpenCV
            enhanced_cv = cv2.convertScaleAbs(gray, alpha=2.5, beta=20)
            _, enhanced_thresh = cv2.threshold(enhanced_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pil_enhanced = Image.fromarray(enhanced_thresh)
            temp_enhanced_path = os.path.join(user_temp_dir, 'enhanced_cv_image.png')
            pil_enhanced.save(temp_enhanced_path)
            
            for config in configs[:5]:
                try:
                    cmd = [tesseract_path, temp_enhanced_path, 'stdout'] + config
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        results.append(result.stdout.strip())
                except:
                    continue
            
            # Method 5: Resized images for better OCR
            width, height = image.size
            scales = [2.0, 3.0, 4.0]
            for scale in scales:
                resized = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
                temp_resized_path = os.path.join(user_temp_dir, f'resized_{scale}x.png')
                resized.save(temp_resized_path)
                
                for config in configs[:3]:
                    try:
                        cmd = [tesseract_path, temp_resized_path, 'stdout'] + config
                        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                        if result.returncode == 0 and result.stdout.strip():
                            results.append(result.stdout.strip())
                    except:
                        continue
            
            # Method 6: Noise reduction
            denoised = cv2.bilateralFilter(gray, 9, 75, 75)
            _, denoised_thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pil_denoised = Image.fromarray(denoised_thresh)
            temp_denoised_path = os.path.join(user_temp_dir, 'denoised_image.png')
            pil_denoised.save(temp_denoised_path)
            
            for config in configs[:5]:
                try:
                    cmd = [tesseract_path, temp_denoised_path, 'stdout'] + config
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        results.append(result.stdout.strip())
                except:
                    continue
            
            # Method 7: Morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            pil_cleaned = Image.fromarray(cleaned)
            temp_cleaned_path = os.path.join(user_temp_dir, 'cleaned_image.png')
            pil_cleaned.save(temp_cleaned_path)
            
            for config in configs[:5]:
                try:
                    cmd = [tesseract_path, temp_cleaned_path, 'stdout'] + config
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        results.append(result.stdout.strip())
                except:
                    continue
            
            # Clean up temporary files
            try:
                for file in os.listdir(user_temp_dir):
                    os.remove(os.path.join(user_temp_dir, file))
                shutil.rmtree(user_temp_dir, ignore_errors=True)
            except:
                pass
            
            # Filter and combine results
            non_empty_results = [result for result in results if result.strip()]
            
            if non_empty_results:
                # Find the result with the most content
                best_result = max(non_empty_results, key=len)
                
                # If we have multiple good results, try to combine them
                if len(non_empty_results) > 1:
                    # Combine all results, removing duplicates and fixing common OCR errors
                    combined_text = ""
                    seen_lines = set()
                    
                    for result in non_empty_results:
                        lines = result.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line and line not in seen_lines and len(line) > 2:
                                # Fix common OCR errors
                                line = self.fix_ocr_errors(line)
                                combined_text += line + '\n'
                                seen_lines.add(line)
                    
                    # If combined text is longer, use it
                    if len(combined_text.strip()) > len(best_result):
                        best_result = combined_text.strip()
                
                return best_result
            else:
                return "No text could be extracted from the image."
            
        except subprocess.TimeoutExpired:
            return "OCR processing timed out. Please try with a smaller image."
        except Exception as e:
            return f"Error extracting text: {str(e)}\n\nMake sure Tesseract is properly installed and in your PATH."
    
    def fix_ocr_errors(self, text):
        """Fix common OCR errors in extracted text"""
        # Common OCR error corrections
        corrections = {
            'Inttoduetlon': 'Introduction',
            'OVE eee': 'Overview',
            'Puta eee': 'Putaway',
            'Management een': 'Management',
            'Cy COUN': 'Cycle Count',
            'Wave Management o-oo': 'Wave Management',
            'A200 one TOM': 'Advanced TOM',
            'Replenehmnt enn': 'Replenishment',
            'Pe ene t@A': 'Performance',
            'Shing and Carrer': 'Shipping and Carrier',
            'Yard Management ono tA': 'Yard Management',
            'Ap pNGKA': 'Appendix',
            'WOT O10 ee': 'Work Order',
            'SEALE': 'Scale',
            'ible of Cots': 'Table of Contents',
            'ves Werkosk': 'Workbook',
            'eaten sete he': 'Educational Services'
        }
        
        for error, correction in corrections.items():
            text = text.replace(error, correction)
        
        return text
    
    def read_and_save_content(self):
        """Read text content from screenshot and save to individual markdown file"""
        if self.current_screenshot is None:
            messagebox.showwarning("Warning", "No screenshot to read")
            return
            
        # Check if a text extraction method is selected and available
        method = self.text_extraction_method.get()
        if method == "none":
            return
        elif method == "ocr" and not TESSERACT_AVAILABLE:
            return
        elif method == "llm" and not self.azure_client:
            return
            
        try:
            self.status_label.config(text="Extracting...")
            self.read_btn.config(state='disabled')
            
            # Extract text based on selected method
            if method == "llm" and self.azure_client:
                extracted_text = self.extract_text_with_azure_openai(self.current_screenshot)
                self.status_label.config(text="LLM done")
            elif method == "ocr" and TESSERACT_AVAILABLE:
                extracted_text = self.extract_text_from_image(self.current_screenshot)
                self.status_label.config(text="OCR done")
            else:
                return
                
            self.extracted_text = extracted_text
            
            # Display extracted text
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(1.0, extracted_text)
            
            # Save to individual markdown file with content
            self.save_to_individual_markdown(extracted_text)
            
            self.status_label.config(text="Saved")
            
        except Exception as e:
            self.status_label.config(text="Failed")
        finally:
            self.read_btn.config(state='normal')
            
    def save_to_individual_markdown(self, text_content):
        """Save screenshot with extracted text to individual markdown file"""
        try:
            # Create output directory if it doesn't exist
            output_path = self.output_dir.get()
            if not os.path.exists(output_path):
                os.makedirs(output_path)
                
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.screenshot_count += 1
            filename = f"screenshot_{timestamp}_{self.screenshot_count:03d}.png"
            filepath = os.path.join(output_path, filename)
            
            # Save screenshot
            self.current_screenshot.save(filepath)
            
            # Create individual markdown file with same name
            md_filename = filename.replace('.png', '.md')
            md_filepath = os.path.join(output_path, md_filename)
            
            # Prepare markdown content with text
            md_content = self.generate_individual_markdown_content(filepath, filename, text_content)
            
            # Write to individual markdown file
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
        except Exception as e:
            pass
            
    def generate_individual_markdown_content(self, image_path, filename, text_content):
        """Generate individual markdown content with screenshot and extracted text"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        width = self.width_var.get()
        height = self.height_var.get()
        x = self.x_var.get()
        y = self.y_var.get()
        
        # Get relative path for markdown
        rel_path = os.path.relpath(image_path, self.output_dir.get())
        
        # Create screenshot name from filename (remove extension and underscores)
        screenshot_name = filename.replace('.png', '').replace('_', ' ').title()
        
        content = f"""# {screenshot_name}

**Captured:** {timestamp}  
**Position:** ({x}, {y})  
**Dimensions:** {width} x {height} pixels  
**File:** {filename}

![{screenshot_name}]({rel_path})

## Extracted Text Content

```
{text_content}
```

---
*Generated by Screenshot Capture App*
"""
        return content
            
    def display_preview(self, screenshot):
        # Clear canvas
        self.canvas.delete("all")
        
        # Resize image for preview (maintain aspect ratio)
        preview_width = 240
        preview_height = 140
        
        # Calculate scaling factor
        img_width, img_height = screenshot.size
        scale_x = preview_width / img_width
        scale_y = preview_height / img_height
        scale = min(scale_x, scale_y)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        # Resize image
        preview_img = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to PhotoImage
        self.preview_photo = ImageTk.PhotoImage(preview_img)
        
        # Display on canvas
        self.canvas.create_image(10, 10, anchor=tk.NW, image=self.preview_photo)
        
    def save_to_markdown(self):
        if self.current_screenshot is None:
            messagebox.showwarning("Warning", "No screenshot to save")
            return
            
        try:
            # Create output directory if it doesn't exist
            output_path = self.output_dir.get()
            if not os.path.exists(output_path):
                os.makedirs(output_path)
                
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.screenshot_count += 1
            filename = f"screenshot_{timestamp}_{self.screenshot_count:03d}.png"
            filepath = os.path.join(output_path, filename)
            
            # Save screenshot
            self.current_screenshot.save(filepath)
            
            # Create individual markdown file with same name
            md_filename = filename.replace('.png', '.md')
            md_filepath = os.path.join(output_path, md_filename)
            
            # Prepare markdown content (image only)
            md_content = self.generate_individual_markdown_content_image_only(filepath, filename)
            
            # Write to individual markdown file
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
            self.status_label.config(text=f"Saved: {filename}")
            
        except Exception as e:
            self.status_label.config(text="Save failed")
    
    def generate_individual_markdown_content_image_only(self, image_path, filename):
        """Generate individual markdown content with screenshot only (no text)"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        width = self.width_var.get()
        height = self.height_var.get()
        x = self.x_var.get()
        y = self.y_var.get()
        
        # Get relative path for markdown
        rel_path = os.path.relpath(image_path, self.output_dir.get())
        
        # Create screenshot name from filename (remove extension and underscores)
        screenshot_name = filename.replace('.png', '').replace('_', ' ').title()
        
        content = f"""# {screenshot_name}

**Captured:** {timestamp}  
**Position:** ({x}, {y})  
**Dimensions:** {width} x {height} pixels  
**File:** {filename}

![{screenshot_name}]({rel_path})

---
*Generated by Screenshot Capture App*
"""
        return content
        
    def clear_screenshot(self):
        self.current_screenshot = None
        self.canvas.delete("all")
        self.text_area.delete(1.0, tk.END)
        self.extracted_text = ""
        self.save_btn.config(state='disabled')
        self.read_btn.config(state='disabled')
        self.status_label.config(text="Ready")

def main():
    root = tk.Tk()
    
    # Configure style
    style = ttk.Style()
    style.theme_use('clam')
    
    # Create accent button style
    style.configure('Accent.TButton', background='#0078d4', foreground='white')
    
    app = ScreenshotApp(root)
    
    # Center window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    print("Starting Screenshot App...")
    print("Look for the GUI window on your screen!")
    
    root.mainloop()

if __name__ == "__main__":
    main() 