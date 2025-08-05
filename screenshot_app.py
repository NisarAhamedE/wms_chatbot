import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pyautogui
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
from datetime import datetime
import threading
import time

# Try to import pytesseract, but handle if not available
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("Warning: pytesseract not available. OCR features will be disabled.")

from PIL import Image, ImageEnhance, ImageFilter

class ScreenshotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screenshot Capture App")
        self.root.geometry("700x850")
        self.root.configure(bg='#f0f0f0')
        
        # Variables
        self.width_var = tk.IntVar(value=800)
        self.height_var = tk.IntVar(value=600)
        self.x_var = tk.IntVar(value=0)
        self.y_var = tk.IntVar(value=0)
        self.output_dir = tk.StringVar(value="screenshots")
        self.current_screenshot = None
        self.screenshot_count = 0
        self.selection_window = None
        self.selection_canvas = None
        self.selection_start = None
        self.selection_end = None
        self.extracted_text = ""
        
        # Create output directory
        if not os.path.exists(self.output_dir.get()):
            os.makedirs(self.output_dir.get())
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Screenshot Capture App", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # OCR Status
        if not TESSERACT_AVAILABLE:
            ocr_status = ttk.Label(main_frame, text="⚠️ OCR (Text Extraction) not available - Install Tesseract for full functionality", 
                                  font=('Arial', 10), foreground='orange')
            ocr_status.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        
        # Dimensions frame
        dim_frame = ttk.LabelFrame(main_frame, text="Screenshot Dimensions", padding="10")
        dim_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
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
        pos_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
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
        
        # Selection frame
        selection_frame = ttk.LabelFrame(main_frame, text="Area Selection", padding="10")
        selection_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # Mouse selection button
        self.select_btn = ttk.Button(selection_frame, text="Select Area with Mouse", 
                                    command=self.start_area_selection, style='Accent.TButton')
        self.select_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Instructions
        ttk.Label(selection_frame, text="Click and drag to select screen area", 
                 font=('Arial', 9, 'italic')).grid(row=0, column=1, padx=(10, 0))
        
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
        
        # Scrollbar for canvas
        v_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
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
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        selection_frame.columnconfigure(1, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Configure canvas scrolling
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        
    def on_canvas_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def center_position(self):
        """Calculate center position based on current dimensions"""
        try:
            screen_width, screen_height = pyautogui.size()
            width = self.width_var.get()
            height = self.height_var.get()
            
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            self.x_var.set(max(0, x))
            self.y_var.set(max(0, y))
            
            self.status_label.config(text=f"Position centered: ({x}, {y})")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to center position: {str(e)}")
        
    def start_area_selection(self):
        """Start the area selection process"""
        try:
            self.root.withdraw()  # Hide main window
            self.status_label.config(text="Selecting area... Click and drag to select")
            
            # Create selection window
            self.create_selection_window()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start area selection: {str(e)}")
            self.root.deiconify()  # Show main window again
    
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
            self.selection_canvas.create_text(screen_width//2, 50, 
                                            text="Click and drag to select area. Press ESC to cancel.",
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
            
            self.status_label.config(text=f"Area selected: ({x}, {y}) {width}x{height}")
    
    def cancel_selection(self, event=None):
        """Cancel area selection"""
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
            self.selection_canvas = None
        
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.status_label.config(text="Area selection cancelled")
        
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
        """Extract text from image using OCR"""
        if not TESSERACT_AVAILABLE:
            return "OCR not available. Please install Tesseract OCR for text extraction."
        
        try:
            # Convert PIL image to OpenCV format
            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Preprocess image for better OCR
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Apply thresholding to get black text on white background
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Apply morphological operations to clean up the image
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Convert back to PIL for tesseract
            pil_image = Image.fromarray(cleaned)
            
            # Extract text using pytesseract
            text = pytesseract.image_to_string(pil_image, config='--psm 6')
            
            return text.strip()
            
        except Exception as e:
            return f"Error extracting text: {str(e)}"
    
    def read_and_save_content(self):
        """Read text content from screenshot and save to individual markdown file"""
        if self.current_screenshot is None:
            messagebox.showwarning("Warning", "No screenshot to read")
            return
            
        if not TESSERACT_AVAILABLE:
            messagebox.showwarning("OCR Not Available", 
                                 "Tesseract OCR is not installed. Please install Tesseract for text extraction.")
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
        
        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
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
    
    app = ScreenshotApp(root)
    
    # Center window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main() 