#!/usr/bin/env python3
"""
WMS Screenshot & Document Management System Launcher
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main launcher function"""
    try:
        print("Starting WMS Screenshot & Document Management System...")
        print("=" * 60)
        
        # Import and run the main application
        from wms_screenshot_app import main as app_main
        app_main()
        
    except ImportError as e:
        print(f"Error: Missing required module - {e}")
        print("Please install required dependencies:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 