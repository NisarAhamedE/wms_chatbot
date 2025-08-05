import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pyautogui
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageEnhance, ImageFilter
import os
import tempfile
from datetime import datetime

# Try to import pytesseract, but handle if not available
try:
    import pytesseract
    # Set the correct Tesseract path for user installation
    tesseract_path = r"C:\Users\NisarAhamed\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        # Set temp directory to user's temp folder
        os.environ['TMP'] = os.path.expanduser('~\\AppData\\Local\\Temp')
        os.environ['TEMP'] = os.path.expanduser('~\\AppData\\Local\\Temp')
        TESSERACT_AVAILABLE = True
        print("✓ Tesseract OCR is available and configured")
    else:
        TESSERACT_AVAILABLE = False
        print("⚠ Tesseract executable not found at expected path")
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠ Tesseract OCR not available - OCR features disabled")

class SimpleScreenshotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Screenshot Capture App - FIXED")
        self.root.geometry("600x750")
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
        
        # Create output directory
        if not os.path.exists(self.output_dir.get()):
            os.makedirs(self.output_dir.get())
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Simple Screenshot Capture App - FIXED", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # OCR Status
        if not TESSERACT_AVAILABLE:
            ocr_status = ttk.Label(main_frame, text="⚠️ OCR (Text Extraction) not available - Install Tesseract for full functionality", 
                                  font=('Arial', 10), foreground='orange')
            ocr_status.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        else:
            ocr_status = ttk.Label(main_frame, text="✓ OCR (Text Extraction) is available and working!", 
                                  font=('Arial', 10), foreground='green')
            ocr_status.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        
        # Auto Mode Frame
        auto_frame = ttk.LabelFrame(main_frame, text="Auto Mode", padding="10")
        auto_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # Auto Mode Button
        self.auto_btn = ttk.Button(auto_frame, text="🚀 Enable Auto Mode", 
                                  command=self.toggle_auto_mode, style='Accent.TButton')
        self.auto_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Auto Mode Status
        self.auto_status = ttk.Label(auto_frame, text="Auto Mode: Disabled - Click to enable automatic capture and save", 
                                    font=('Arial', 9), foreground='gray')
        self.auto_status.grid(row=0, column=1, padx=(10, 0))
        
        # Instructions for Auto Mode
        auto_instructions = ttk.Label(auto_frame, text="When enabled: Select area with mouse → Auto capture → Auto read text → Auto save to MD → Auto disable", 
                                     font=('Arial', 8, 'italic'), foreground='blue')
        auto_instructions.grid(row=1, column=0, columnspan=2, pady=(5, 0))
        
        # Dimensions frame
        dim_frame = ttk.LabelFrame(main_frame, text="Manual Mode Settings", padding="10")
        dim_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # Width
        ttk.Label(dim_frame, text="Width:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        width_entry = ttk.Entry(dim_frame, textvariable=self.width_var, width=10)
        width_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Height
        ttk.Label(dim_frame, text="Height:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        height_entry = ttk.Entry(dim_frame, textvariable=self.height_var, width=10)
        height_entry.grid(row=0, column=3, sticky=tk.W)
        
        # Position frame
        pos_frame = ttk.LabelFrame(main_frame, text="Capture Position (X, Y)", padding="10")
        pos_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
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
        output_frame = ttk.LabelFrame(main_frame, text="Output Directory", padding="10")
        output_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        ttk.Entry(output_frame, textvariable=self.output_dir, width=50).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(output_frame, text="Browse", command=self.browse_output_dir).grid(row=0, column=1)
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=6, column=0, columnspan=2, pady=(0, 20))
        
        # Capture button
        self.capture_btn = ttk.Button(control_frame, text="Capture Screenshot", 
                                     command=self.capture_screenshot, style='Accent.TButton')
        self.capture_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Save to markdown button
        self.save_btn = ttk.Button(control_frame, text="Save Image Only", 
                                  command=self.save_to_markdown, state='disabled')
        self.save_btn.grid(row=0, column=1, padx=(0, 10))
        
        # Read markdown button
        self.read_btn = ttk.Button(control_frame, text="Read & Save Content", 
                                  command=self.read_and_save_content, state='disabled')
        self.read_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Clear button
        ttk.Button(control_frame, text="Clear", command=self.clear_screenshot).grid(row=0, column=3)
        
        # Text content frame
        text_frame = ttk.LabelFrame(main_frame, text="Extracted Text Content", padding="10")
        text_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        
        # Text area for extracted content
        self.text_area = tk.Text(text_frame, height=6, width=70, wrap=tk.WORD, font=('Consolas', 9))
        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=text_scrollbar.set)
        
        self.text_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Screenshot Preview", padding="10")
        preview_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        
        # Canvas for preview
        self.canvas = tk.Canvas(preview_frame, width=400, height=300, bg='white', relief='sunken', bd=1)
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="Ready to capture screenshots", 
                                     font=('Arial', 9))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1)
        main_frame.rowconfigure(8, weight=1)
        output_frame.columnconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        auto_frame.columnconfigure(1, weight=1)
        
    def toggle_auto_mode(self):
        """Toggle Auto Mode on/off"""
        self.auto_mode = not self.auto_mode
        
        if self.auto_mode:
            self.auto_btn.config(text="⏹️ Disable Auto Mode")
            self.auto_status.config(text="Auto Mode: ENABLED - Click and drag to select area", foreground='green')
            self.status_label.config(text="Auto Mode enabled - Select area with mouse to capture automatically")
            
            # Start area selection immediately
            self.start_auto_selection()
        else:
            self.auto_btn.config(text="🚀 Enable Auto Mode")
            self.auto_status.config(text="Auto Mode: Disabled - Click to enable automatic capture and save", foreground='gray')
            self.status_label.config(text="Auto Mode disabled")
            
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
            messagebox.showerror("Error", f"Failed to start auto selection: {str(e)}")
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
            messagebox.showerror("Error", f"Failed to create selection window: {str(e)}")
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
                messagebox.showwarning("Warning", "Selection too small. Please select a larger area.")
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
                self.status_label.config(text=f"Area selected: ({x}, {y}) {width}x{height}")
    
    def auto_capture_and_save(self):
        """Automatically capture, read text, and save in Auto Mode"""
        try:
            self.status_label.config(text="Auto Mode: Capturing and processing...")
            
            # Capture screenshot
            width = self.width_var.get()
            height = self.height_var.get()
            x = self.x_var.get()
            y = self.y_var.get()
            
            # Validate dimensions
            if width <= 0 or height <= 0:
                messagebox.showerror("Error", "Invalid dimensions. Please select a valid area.")
                return
            
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            self.current_screenshot = screenshot
            
            # Display preview
            self.display_preview(screenshot)
            
            # Extract text if OCR is available
            if TESSERACT_AVAILABLE:
                extracted_text = self.extract_text_from_image(screenshot)
                self.extracted_text = extracted_text
                
                # Display extracted text
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(1.0, extracted_text)
                
                # Auto save with content
                self.save_to_individual_markdown(extracted_text)
                self.status_label.config(text="Auto Mode: Captured, read text, and saved successfully!")
                
                # Auto disable after successful capture and save
                self.root.after(1000, self.auto_disable_after_success)
            else:
                # Save without text extraction
                self.save_to_markdown()
                self.status_label.config(text="Auto Mode: Captured and saved (OCR not available)")
                # Auto disable after successful capture and save
                self.root.after(1000, self.auto_disable_after_success)
            
        except Exception as e:
            messagebox.showerror("Auto Mode Error", f"Failed to auto capture: {str(e)}")
            self.status_label.config(text="Auto Mode: Error occurred")
    
    def auto_disable_after_success(self):
        """Auto disable Auto Mode after successful capture and save"""
        if self.auto_mode:
            self.auto_mode = False
            self.auto_btn.config(text="🚀 Enable Auto Mode")
            self.auto_status.config(text="Auto Mode: Disabled - Click to enable automatic capture and save", foreground='gray')
            self.status_label.config(text="Auto Mode disabled after successful capture and save")
            messagebox.showinfo("Auto Mode", "Capture completed successfully! Auto Mode has been disabled.")
    
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
            self.status_label.config(text="Auto Mode: Selection cancelled")
            # Restart selection after a short delay
            self.root.after(1000, self.start_auto_selection)
        else:
            self.status_label.config(text="Area selection cancelled")
        
    def center_position(self):
        """Calculate center position based on current dimensions"""
        try:
            screen_width, screen_height = pyautogui.size()
            width = self.width_var.get()
            height = self.height_var.get()
            
            # Validate dimensions
            if width <= 0 or height <= 0:
                messagebox.showerror("Error", "Please set valid width and height first")
                return
            
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            self.x_var.set(max(0, x))
            self.y_var.set(max(0, y))
            
            self.status_label.config(text=f"Position centered: ({x}, {y})")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to center position: {str(e)}")
        
    def browse_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)
            if not os.path.exists(directory):
                os.makedirs(directory)
                
    def capture_screenshot(self):
        try:
            self.status_label.config(text="Capturing screenshot...")
            self.capture_btn.config(state='disabled')
            
            # Get capture parameters
            width = self.width_var.get()
            height = self.height_var.get()
            x = self.x_var.get()
            y = self.y_var.get()
            
            if width <= 0 or height <= 0:
                messagebox.showerror("Error", "Width and height must be positive numbers")
                return
            
            if x < 0 or y < 0:
                messagebox.showerror("Error", "X and Y coordinates must be non-negative")
                return
                
            # Get screen size
            screen_width, screen_height = pyautogui.size()
            
            # Check if coordinates are within screen bounds
            if x + width > screen_width or y + height > screen_height:
                messagebox.showwarning("Warning", "Capture area extends beyond screen bounds")
            
            # Capture screenshot
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            self.current_screenshot = screenshot
            
            # Display preview
            self.display_preview(screenshot)
            
            # Clear previous text
            self.text_area.delete(1.0, tk.END)
            self.extracted_text = ""
            
            self.save_btn.config(state='normal')
            if TESSERACT_AVAILABLE:
                self.read_btn.config(state='normal')
            else:
                self.read_btn.config(state='disabled')
            self.status_label.config(text=f"Screenshot captured: ({x}, {y}) {width}x{height} pixels")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to capture screenshot: {str(e)}")
            self.status_label.config(text="Screenshot capture failed")
        finally:
            self.capture_btn.config(state='normal')
    
    def extract_text_from_image(self, image):
        """Extract text from image using OCR with enhanced preprocessing"""
        if not TESSERACT_AVAILABLE:
            return "OCR not available. Please install Tesseract OCR for text extraction.\n\nTo install Tesseract:\n1. Download from: https://github.com/UB-Mannheim/tesseract/wiki\n2. Install and add to PATH\n3. Restart the app"
        
        try:
            # Convert PIL image to OpenCV format
            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Try multiple preprocessing approaches for better OCR
            results = []
            
            # Method 1: Raw image without preprocessing (most reliable)
            text1 = pytesseract.image_to_string(image, config='--psm 6')
            results.append(text1.strip())
            
            # Method 2: Basic preprocessing
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pil_image = Image.fromarray(thresh)
            text2 = pytesseract.image_to_string(pil_image, config='--psm 6')
            results.append(text2.strip())
            
            # Method 3: Enhanced preprocessing with noise reduction
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            # Apply adaptive thresholding
            adaptive_thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            pil_image2 = Image.fromarray(adaptive_thresh)
            text3 = pytesseract.image_to_string(pil_image2, config='--psm 6')
            results.append(text3.strip())
            
            # Method 4: Morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            pil_image3 = Image.fromarray(cleaned)
            text4 = pytesseract.image_to_string(pil_image3, config='--psm 6')
            results.append(text4.strip())
            
            # Method 5: PIL enhancement
            enhancer = ImageEnhance.Contrast(image)
            enhanced = enhancer.enhance(2.0)  # Increase contrast
            enhancer = ImageEnhance.Sharpness(enhanced)
            sharpened = enhancer.enhance(2.0)  # Increase sharpness
            text5 = pytesseract.image_to_string(sharpened, config='--psm 6')
            results.append(text5.strip())
            
            # Method 6: Different PSM modes
            text6 = pytesseract.image_to_string(image, config='--psm 3')
            results.append(text6.strip())
            
            # Method 7: Auto PSM
            text7 = pytesseract.image_to_string(image, config='--psm 0')
            results.append(text7.strip())
            
            # Method 8: Single column text
            text8 = pytesseract.image_to_string(image, config='--psm 6 --oem 3')
            results.append(text8.strip())
            
            # Method 9: Sparse text
            text9 = pytesseract.image_to_string(image, config='--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:()[]{}"\'-_/\\| ')
            results.append(text9.strip())
            
            # Find the result with the most content
            best_result = max(results, key=len)
            
            # If all results are empty, try one more time with different config
            if not best_result.strip():
                best_result = pytesseract.image_to_string(image, config='--psm 6 --oem 1')
            
            return best_result.strip()
            
        except Exception as e:
            return f"Error extracting text: {str(e)}\n\nMake sure Tesseract is properly installed and in your PATH."
    
    def read_and_save_content(self):
        """Read text content from screenshot and save to individual markdown file"""
        if self.current_screenshot is None:
            messagebox.showwarning("Warning", "No screenshot to read")
            return
            
        if not TESSERACT_AVAILABLE:
            messagebox.showwarning("OCR Not Available", 
                                 "Tesseract OCR is not installed.\n\nTo install:\n1. Download from: https://github.com/UB-Mannheim/tesseract/wiki\n2. Install and add to PATH\n3. Restart the app")
            return
            
        try:
            self.status_label.config(text="Extracting text content...")
            self.read_btn.config(state='disabled')
            
            # Extract text from screenshot
            extracted_text = self.extract_text_from_image(self.current_screenshot)
            self.extracted_text = extracted_text
            
            # Display extracted text
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(1.0, extracted_text)
            
            # Save to individual markdown file with content
            self.save_to_individual_markdown(extracted_text)
            
            self.status_label.config(text="Text extracted and saved to individual markdown file")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract text: {str(e)}")
            self.status_label.config(text="Text extraction failed")
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
                
            messagebox.showinfo("Success", f"Screenshot saved: {filename}\nMarkdown file created: {md_filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save screenshot with content: {str(e)}")
            
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
        preview_width = 380
        preview_height = 280
        
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
                
            self.status_label.config(text=f"Screenshot saved: {filename}")
            messagebox.showinfo("Success", f"Screenshot saved: {filename}\nMarkdown file created: {md_filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save screenshot: {str(e)}")
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
        self.status_label.config(text="Ready to capture screenshots")

def main():
    root = tk.Tk()
    
    # Configure style
    style = ttk.Style()
    style.theme_use('clam')
    
    # Create accent button style
    style.configure('Accent.TButton', background='#0078d4', foreground='white')
    
    app = SimpleScreenshotApp(root)
    
    # Center window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    print("Starting Enhanced Screenshot Capture App with FIXED Tesseract Path...")
    print("Look for the GUI window on your screen!")
    
    root.mainloop()

if __name__ == "__main__":
    main()