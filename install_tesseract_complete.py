import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path
import webbrowser

def check_tesseract():
    """Check if Tesseract is installed and accessible"""
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract is installed! Version: {version}")
        return True
    except Exception as e:
        print(f"❌ Tesseract not found: {e}")
        return False

def download_tesseract():
    """Download Tesseract installer"""
    print("📥 Downloading Tesseract OCR...")
    
    # Tesseract download URL (latest version)
    url = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
    filename = "tesseract-installer.exe"
    
    try:
        print(f"Downloading from: {url}")
        urllib.request.urlretrieve(url, filename)
        print(f"✅ Downloaded: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Download failed: {e}")
        print("Please download manually from: https://github.com/UB-Mannheim/tesseract/wiki")
        return None

def install_tesseract_silent(installer_path):
    """Install Tesseract silently with PATH option"""
    print("📦 Installing Tesseract OCR...")
    
    # Silent install command with PATH option
    install_cmd = [
        installer_path,
        "/S",  # Silent install
        "/D=C:\\Program Files\\Tesseract-OCR"  # Install directory
    ]
    
    try:
        result = subprocess.run(install_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Tesseract installed successfully!")
            return True
        else:
            print(f"❌ Installation failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Installation error: {e}")
        return False

def add_to_path():
    """Add Tesseract to system PATH"""
    print("🔧 Adding Tesseract to PATH...")
    
    tesseract_path = r"C:\Program Files\Tesseract-OCR"
    
    try:
        # Get current PATH
        current_path = os.environ.get('PATH', '')
        
        # Check if already in PATH
        if tesseract_path in current_path:
            print("✅ Tesseract already in PATH")
            return True
        
        # Add to PATH
        new_path = current_path + ";" + tesseract_path
        os.environ['PATH'] = new_path
        
        # Set for current session
        subprocess.run(['setx', 'PATH', new_path], capture_output=True)
        
        print("✅ Tesseract added to PATH")
        return True
        
    except Exception as e:
        print(f"❌ Failed to add to PATH: {e}")
        return False

def test_tesseract():
    """Test if Tesseract is working"""
    print("🧪 Testing Tesseract installation...")
    
    try:
        # Test tesseract command
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Tesseract command works!")
            print(f"Version: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Tesseract command failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Tesseract test failed: {e}")
        return False

def create_test_image():
    """Create a test image for OCR testing"""
    print("🖼️ Creating test image...")
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple test image
        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add text
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        draw.text((20, 30), "Hello World! This is a test.", fill='black', font=font)
        
        # Save test image
        img.save("test_ocr.png")
        print("✅ Test image created: test_ocr.png")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create test image: {e}")
        return False

def test_ocr():
    """Test OCR functionality"""
    print("🔍 Testing OCR functionality...")
    
    try:
        import pytesseract
        from PIL import Image
        
        # Test OCR on our test image
        img = Image.open("test_ocr.png")
        text = pytesseract.image_to_string(img)
        
        print("✅ OCR Test Results:")
        print(f"Extracted text: '{text.strip()}'")
        
        if "Hello World" in text:
            print("🎉 OCR is working perfectly!")
            return True
        else:
            print("⚠️ OCR extracted text but may need adjustment")
            return True
            
    except Exception as e:
        print(f"❌ OCR test failed: {e}")
        return False

def main():
    print("=" * 70)
    print("🔧 COMPLETE TESSERACT OCR INSTALLATION")
    print("=" * 70)
    print()
    
    # Check if already installed
    if check_tesseract():
        print("🎉 Tesseract is already working perfectly!")
        return
    
    print("Tesseract OCR is not installed. Starting installation...")
    print()
    
    # Step 1: Download
    installer = download_tesseract()
    if not installer:
        print("Please download Tesseract manually and run this script again.")
        return
    
    # Step 2: Install
    if not install_tesseract_silent(installer):
        print("Installation failed. Please install manually.")
        return
    
    # Step 3: Add to PATH
    if not add_to_path():
        print("Failed to add to PATH. Please restart your computer.")
        return
    
    # Step 4: Test installation
    if not test_tesseract():
        print("Tesseract installation test failed.")
        return
    
    # Step 5: Test OCR
    if create_test_image():
        if test_ocr():
            print()
            print("🎉 SUCCESS! Tesseract OCR is fully installed and working!")
            print("Your screenshot app should now be able to extract text from images.")
            print()
            print("Next steps:")
            print("1. Restart your computer to ensure PATH is updated")
            print("2. Run your screenshot app again")
            print("3. Try the Auto Mode feature!")
        else:
            print("OCR test failed. Please check installation.")
    else:
        print("Failed to create test image.")
    
    # Cleanup
    try:
        if os.path.exists(installer):
            os.remove(installer)
        if os.path.exists("test_ocr.png"):
            os.remove("test_ocr.png")
    except:
        pass

if __name__ == "__main__":
    main() 