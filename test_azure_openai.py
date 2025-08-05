import os
import requests
import json
from datetime import datetime

def test_azure_openai_key():
    """Test Azure OpenAI key functionality"""
    
    # Azure OpenAI Configuration
    # You need to set these environment variables or replace with your actual values
    AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY', 'your-azure-openai-key-here')
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://your-resource.openai.azure.com/')
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'your-deployment-name')
    
    print("🔍 Testing Azure OpenAI Key...")
    print(f"Endpoint: {AZURE_OPENAI_ENDPOINT}")
    print(f"API Version: {AZURE_OPENAI_API_VERSION}")
    print(f"Deployment: {AZURE_OPENAI_DEPLOYMENT_NAME}")
    print("-" * 50)
    
    # Test 1: Simple Chat Completion
    def test_chat_completion():
        """Test basic chat completion"""
        print("📝 Test 1: Chat Completion")
        
        url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY
        }
        
        data = {
            "messages": [
                {"role": "user", "content": "Hello! Please respond with 'Azure OpenAI is working!' if you can see this message."}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                params={"api-version": AZURE_OPENAI_API_VERSION},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Chat Completion: SUCCESS")
                print(f"Response: {result['choices'][0]['message']['content']}")
                return True
            else:
                print(f"❌ Chat Completion: FAILED")
                print(f"Status Code: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Chat Completion: ERROR")
            print(f"Exception: {str(e)}")
            return False
    
    # Test 2: Text Generation
    def test_text_generation():
        """Test text generation"""
        print("\n📝 Test 2: Text Generation")
        
        url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}/completions"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY
        }
        
        data = {
            "prompt": "Write a short poem about technology:",
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                params={"api-version": AZURE_OPENAI_API_VERSION},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Text Generation: SUCCESS")
                print(f"Response: {result['choices'][0]['text']}")
                return True
            else:
                print(f"❌ Text Generation: FAILED")
                print(f"Status Code: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Text Generation: ERROR")
            print(f"Exception: {str(e)}")
            return False
    
    # Test 3: Embeddings
    def test_embeddings():
        """Test embeddings generation"""
        print("\n📝 Test 3: Embeddings")
        
        url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}/embeddings"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY
        }
        
        data = {
            "input": "This is a test sentence for embeddings."
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                params={"api-version": AZURE_OPENAI_API_VERSION},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Embeddings: SUCCESS")
                print(f"Embedding dimensions: {len(result['data'][0]['embedding'])}")
                return True
            else:
                print(f"❌ Embeddings: FAILED")
                print(f"Status Code: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Embeddings: ERROR")
            print(f"Exception: {str(e)}")
            return False
    
    # Test 4: Model Information
    def test_model_info():
        """Test getting model information"""
        print("\n📝 Test 4: Model Information")
        
        url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}"
        
        headers = {
            "api-key": AZURE_OPENAI_KEY
        }
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"api-version": AZURE_OPENAI_API_VERSION},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Model Info: SUCCESS")
                print(f"Model: {result.get('model', 'Unknown')}")
                print(f"Status: {result.get('status', 'Unknown')}")
                return True
            else:
                print(f"❌ Model Info: FAILED")
                print(f"Status Code: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Model Info: ERROR")
            print(f"Exception: {str(e)}")
            return False
    
    # Test 5: Image Analysis (if using GPT-4 Vision)
    def test_image_analysis():
        """Test image analysis with GPT-4 Vision"""
        print("\n📝 Test 5: Image Analysis (GPT-4 Vision)")
        
        url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY
        }
        
        # Simple test without actual image
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe what you see in this image:"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 100
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                params={"api-version": AZURE_OPENAI_API_VERSION},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Image Analysis: SUCCESS")
                print(f"Response: {result['choices'][0]['message']['content']}")
                return True
            else:
                print(f"❌ Image Analysis: FAILED")
                print(f"Status Code: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Image Analysis: ERROR")
            print(f"Exception: {str(e)}")
            return False
    
    # Run all tests
    tests = [
        test_chat_completion,
        test_text_generation,
        test_embeddings,
        test_model_info,
        test_image_analysis
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            results.append(False)
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    successful_tests = sum(results)
    total_tests = len(results)
    
    print(f"Total Tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    
    if successful_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Your Azure OpenAI key is working perfectly!")
    elif successful_tests > 0:
        print("⚠️  PARTIAL SUCCESS! Some tests passed, but there might be configuration issues.")
    else:
        print("❌ ALL TESTS FAILED! Please check your Azure OpenAI configuration.")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return successful_tests > 0

def setup_environment():
    """Setup environment variables for testing"""
    print("🔧 Setting up environment variables...")
    
    # You can set these environment variables or modify the values here
    env_vars = {
        'AZURE_OPENAI_KEY': 'your-azure-openai-key-here',
        'AZURE_OPENAI_ENDPOINT': 'https://your-resource.openai.azure.com/',
        'AZURE_OPENAI_API_VERSION': '2024-02-15-preview',
        'AZURE_OPENAI_DEPLOYMENT_NAME': 'your-deployment-name'
    }
    
    print("Please set the following environment variables:")
    for key, value in env_vars.items():
        print(f"  {key} = {value}")
    
    print("\nOr modify the values directly in the test_azure_openai_key() function.")
    print("="*50)

if __name__ == "__main__":
    setup_environment()
    
    # Check if key is set
    if os.getenv('AZURE_OPENAI_KEY') == 'your-azure-openai-key-here':
        print("\n⚠️  Please set your Azure OpenAI key before running tests!")
        print("You can:")
        print("1. Set environment variables")
        print("2. Modify the values in the test_azure_openai_key() function")
        print("3. Create a .env file with your credentials")
    else:
        print("\n🚀 Running Azure OpenAI tests...")
        test_azure_openai_key() 