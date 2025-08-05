@echo off
echo ========================================
echo Azure OpenAI Test Suite Runner
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if requirements are installed
echo 🔍 Checking dependencies...
pip show openai >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install requirements
        pause
        exit /b 1
    )
)

echo.
echo 🚀 Available test options:
echo 1. Comprehensive Test Suite (azure_openai_test.py)
echo 2. Simple Examples (azure_openai_example.py)
echo 3. Original Test Script (test_azure_openai.py)
echo 4. All Tests
echo.

set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo 🧪 Running Comprehensive Test Suite...
    python azure_openai_test.py
) else if "%choice%"=="2" (
    echo.
    echo 📝 Running Simple Examples...
    python azure_openai_example.py
) else if "%choice%"=="3" (
    echo.
    echo 🔧 Running Original Test Script...
    python test_azure_openai.py
) else if "%choice%"=="4" (
    echo.
    echo 🧪 Running Comprehensive Test Suite...
    python azure_openai_test.py
    echo.
    echo 📝 Running Simple Examples...
    python azure_openai_example.py
    echo.
    echo 🔧 Running Original Test Script...
    python test_azure_openai.py
) else (
    echo ❌ Invalid choice. Please run the script again.
    pause
    exit /b 1
)

echo.
echo ✅ Test execution completed!
pause 