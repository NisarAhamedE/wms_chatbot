#!/bin/bash

echo "========================================"
echo "Azure OpenAI Test Suite Runner"
echo "========================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    echo "Please install Python 3 from https://python.org"
    exit 1
fi

# Check if requirements are installed
echo "🔍 Checking dependencies..."
if ! python3 -c "import openai" &> /dev/null; then
    echo "📦 Installing required packages..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install requirements"
        exit 1
    fi
fi

echo
echo "🚀 Available test options:"
echo "1. Comprehensive Test Suite (azure_openai_test.py)"
echo "2. Simple Examples (azure_openai_example.py)"
echo "3. Original Test Script (test_azure_openai.py)"
echo "4. All Tests"
echo

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo
        echo "🧪 Running Comprehensive Test Suite..."
        python3 azure_openai_test.py
        ;;
    2)
        echo
        echo "📝 Running Simple Examples..."
        python3 azure_openai_example.py
        ;;
    3)
        echo
        echo "🔧 Running Original Test Script..."
        python3 test_azure_openai.py
        ;;
    4)
        echo
        echo "🧪 Running Comprehensive Test Suite..."
        python3 azure_openai_test.py
        echo
        echo "📝 Running Simple Examples..."
        python3 azure_openai_example.py
        echo
        echo "🔧 Running Original Test Script..."
        python3 test_azure_openai.py
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo
echo "✅ Test execution completed!" 