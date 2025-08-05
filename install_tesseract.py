import os
import sys
import subprocess
import webbrowser
from pathlib import Path

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

def install_tesseract_windows():
    """Guide user through Tesseract installation on Windows"""
    print("=" * 60)
    print("🔧 TESSERACT OCR INSTALLATION GUIDE")
    print("=" * 60)
    print()
    print("Tesseract OCR engine is not installed on your system.")
    print("Follow these steps to install it:")
    print()
    print("📥 STEP 1: Download Tesseract")
    print("   • Go to: https://github.com/UB-Mannheim/tesseract/wiki")
    print("   • Download the latest Windows installer")
    print("   • Choose the 64-bit version (tesseract-ocr-w64-setup-xxx.exe)")
    print()
    
    # Ask user if they want to open the download page
    try:
        response = input("Would you like to open the download page now? (y/n): ").lower()
        if response in ['y', 'yes']:
            webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")
            print("✅ Download page opened in your browser!")
    except:
        print("Please manually visit: https://github.com/UB-Mannheim/tesseract/wiki")
    
    print()
    print("📦 STEP 2: Install Tesseract")
    print("   • Run the downloaded installer")
    print("   • IMPORTANT: Check 'Add to PATH' during installation")
    print("   • Choose default installation path (C:\\Program Files\\Tesseract-OCR)")
    print()
    print("🔄 STEP 3: Restart Your System")
    print("   • Restart your computer to ensure PATH is updated")
    print()
    print("✅ STEP 4: Test Installation")
    print("   • Run this script again after installation")
    print("   • Or run: python -c \"import pytesseract; print(pytesseract.get_tesseract_version())\"")
    print()
    print("=" * 60)

def main():
    print("🔍 Checking Tesseract OCR installation...")
    print()
    
    if check_tesseract():
        print()
        print("🎉 Tesseract is working perfectly!")
        print("Your screenshot app should now be able to extract text from images.")
        return
    
    print()
    install_tesseract_windows()

if __name__ == "__main__":
    main() 