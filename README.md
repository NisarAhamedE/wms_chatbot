# Screenshot Capture App

A Python desktop application that allows you to capture screenshots with specified dimensions and automatically save them to markdown files with metadata.

## Features

- **Custom Dimensions**: Specify exact width and height for screenshots
- **Exact Positioning**: Set X,Y coordinates for precise capture location
- **Mouse Area Selection**: Visually select screen areas by clicking and dragging
- **Live Preview**: See a preview of captured screenshots before saving
- **Markdown Integration**: Automatically generates markdown files with screenshot metadata
- **Organized Output**: Screenshots are saved with timestamps and organized in folders
- **User-Friendly GUI**: Clean, intuitive interface built with tkinter

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python screenshot_app.py
   ```

## Usage

### Basic Workflow

1. **Set Dimensions**: Enter the desired width and height for your screenshots
2. **Set Position**: Enter X,Y coordinates or use the "Center" button
3. **Select Area** (Optional): Use "Select Area with Mouse" for visual selection
4. **Choose Output Directory**: Select where to save screenshots and markdown files
5. **Capture Screenshot**: Click "Capture Screenshot" to take a screenshot
6. **Preview**: Review the captured screenshot in the preview area
7. **Save to Markdown**: Click "Save to Markdown" to save the screenshot and add it to the markdown file

### Features Explained

#### Screenshot Dimensions
- **Width**: Horizontal size in pixels
- **Height**: Vertical size in pixels

#### Capture Position
- **X Coordinate**: Horizontal position from left edge of screen
- **Y Coordinate**: Vertical position from top edge of screen
- **Center Button**: Automatically calculates center position based on dimensions

#### Mouse Area Selection
- **Select Area with Mouse**: Click this button to start visual selection
- **Selection Process**:
  1. Main window hides and semi-transparent overlay appears
  2. Click and drag to select the desired area
  3. Release mouse to confirm selection
  4. Press ESC to cancel selection
- **Automatic Updates**: Selected area automatically updates X,Y coordinates and dimensions

#### Output Organization
- Screenshots are saved as PNG files with timestamps
- A `screenshots.md` file is created/updated with metadata
- Each screenshot entry includes:
  - Capture timestamp
  - Position coordinates
  - Dimensions
  - Filename
  - Embedded image

#### Markdown Output Format
```markdown
## Screenshot 1

**Captured:** 2024-01-15 14:30:25  
**Position:** (100, 200)  
**Dimensions:** 800 x 600 pixels  
**File:** screenshot_20240115_143025_001.png

![Screenshot 1](screenshot_20240115_143025_001.png)

---
```

## File Structure

```
scale_docs/
├── screenshot_app.py      # Main application
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── screenshots/          # Output directory (created automatically)
    ├── screenshots.md    # Generated markdown file
    ├── screenshot_20240115_143025_001.png
    ├── screenshot_20240115_143030_002.png
    └── ...
```

## Requirements

- Python 3.7 or higher
- Windows, macOS, or Linux
- Required packages (see requirements.txt):
  - Pillow (PIL) - Image processing
  - pyautogui - Screenshot capture
  - opencv-python - Image operations
  - numpy - Numerical operations
  - tkinter (usually included with Python)

## Troubleshooting

### Common Issues

1. **"No module named 'tkinter'"**
   - Install tkinter: `sudo apt-get install python3-tk` (Ubuntu/Debian)
   - Or use: `brew install python-tk` (macOS with Homebrew)

2. **Screenshot capture fails**
   - Ensure you have proper permissions
   - Try running as administrator (Windows)
   - Check if any security software is blocking screen capture

3. **Mouse selection not working**
   - Ensure the app has focus when starting selection
   - Check if any other applications are blocking the overlay
   - Try running as administrator if on Windows

4. **GUI not displaying properly**
   - Update your Python installation
   - Ensure all dependencies are installed correctly

### Performance Tips

- For large screenshots, the preview may take a moment to load
- The app automatically scales previews to fit the display area
- Screenshots are captured in real-time, so ensure your screen is ready
- Mouse selection works best when other applications are minimized

## Customization

### Modifying Default Values
Edit the `__init__` method in `screenshot_app.py`:
```python
self.width_var = tk.IntVar(value=800)    # Default width
self.height_var = tk.IntVar(value=600)   # Default height
self.x_var = tk.IntVar(value=0)          # Default X coordinate
self.y_var = tk.IntVar(value=0)          # Default Y coordinate
self.output_dir = tk.StringVar(value="screenshots")  # Default output directory
```

### Changing Markdown Format
Modify the `generate_markdown_content` method to customize the markdown output format.

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve this application. 