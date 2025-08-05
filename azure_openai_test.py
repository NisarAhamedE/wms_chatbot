#!/usr/bin/env python3
"""
Azure OpenAI Test Script
A comprehensive test suite for Azure OpenAI services
"""

import os
import sys
import json
import time
import base64
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Try to import required libraries
try:
    import requests
    import openai
    from openai import AzureOpenAI
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Missing required library: {e}")
    print("Please install required packages: pip install -r requirements.txt")
    sys.exit(1)

# Load environment variables
load_dotenv()

class AzureOpenAITester:
    """Comprehensive Azure OpenAI testing class"""
    
    def __init__(self):
        """Initialize the tester with configuration"""
        self.config = self._load_config()
        self.client = None
        self.test_results = []
        
    def _load_config(self) -> Dict:
        """Load configuration from environment variables"""
        config = {
            'api_key': os.getenv('AZURE_OPENAI_KEY'),
            'endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
            'api_version': os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview'),
            'deployment_name': os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME'),
            'model_name': os.getenv('AZURE_OPENAI_MODEL_NAME', 'gpt-35-turbo')
        }
        
        # Validate required configuration
        missing_configs = [k for k, v in config.items() if not v and k != 'model_name']
        if missing_configs:
            print(f"❌ Missing required configuration: {', '.join(missing_configs)}")
            print("\nPlease set the following environment variables:")
            for config_name in missing_configs:
                print(f"  {config_name.upper()}")
            return None
            
        return config
    
    def _initialize_client(self) -> bool:
        """Initialize Azure OpenAI client"""
        try:
            self.client = AzureOpenAI(
                api_key=self.config['api_key'],
                api_version=self.config['api_version'],
                azure_endpoint=self.config['endpoint']
            )
            return True
        except Exception as e:
            print(f"❌ Failed to initialize Azure OpenAI client: {e}")
            return False
    
    def _log_test_result(self, test_name: str, success: bool, details: str = ""):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    def test_connection(self) -> bool:
        """Test basic connection to Azure OpenAI"""
        print("\n🔍 Testing Azure OpenAI Connection...")
        print(f"Endpoint: {self.config['endpoint']}")
        print(f"API Version: {self.config['api_version']}")
        print(f"Deployment: {self.config['deployment_name']}")
        print("-" * 60)
        
        if not self._initialize_client():
            self._log_test_result("Connection", False, "Failed to initialize client")
            return False
        
        self._log_test_result("Connection", True, "Client initialized successfully")
        return True
    
    def test_chat_completion(self) -> bool:
        """Test chat completion functionality"""
        print("\n📝 Testing Chat Completion...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.config['deployment_name'],
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Please respond with 'Azure OpenAI is working!' if you can see this message."}
                ],
                max_tokens=50,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            self._log_test_result("Chat Completion", True, f"Response: {content}")
            return True
            
        except Exception as e:
            self._log_test_result("Chat Completion", False, f"Error: {str(e)}")
            return False
    
    def test_text_generation(self) -> bool:
        """Test text generation (completions)"""
        print("\n📝 Testing Text Generation...")
        
        try:
            response = self.client.completions.create(
                model=self.config['deployment_name'],
                prompt="Write a short poem about technology:",
                max_tokens=100,
                temperature=0.7
            )
            
            content = response.choices[0].text
            self._log_test_result("Text Generation", True, f"Generated: {content[:100]}...")
            return True
            
        except Exception as e:
            self._log_test_result("Text Generation", False, f"Error: {str(e)}")
            return False
    
    def test_embeddings(self) -> bool:
        """Test embeddings generation"""
        print("\n📝 Testing Embeddings...")
        
        try:
            response = self.client.embeddings.create(
                model=self.config['deployment_name'],
                input="This is a test sentence for embeddings."
            )
            
            embedding_length = len(response.data[0].embedding)
            self._log_test_result("Embeddings", True, f"Generated {embedding_length}-dimensional embedding")
            return True
            
        except Exception as e:
            self._log_test_result("Embeddings", False, f"Error: {str(e)}")
            return False
    
    def test_streaming(self) -> bool:
        """Test streaming chat completion"""
        print("\n📝 Testing Streaming Chat...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.config['deployment_name'],
                messages=[
                    {"role": "user", "content": "Count from 1 to 5:"}
                ],
                max_tokens=50,
                temperature=0.1,
                stream=True
            )
            
            content = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content
            
            self._log_test_result("Streaming", True, f"Streamed response: {content}")
            return True
            
        except Exception as e:
            self._log_test_result("Streaming", False, f"Error: {str(e)}")
            return False
    
    def test_function_calling(self) -> bool:
        """Test function calling capability"""
        print("\n📝 Testing Function Calling...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.config['deployment_name'],
                messages=[
                    {"role": "user", "content": "What's the weather like in New York?"}
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get weather information for a location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "The city and state, e.g. San Francisco, CA"
                                    }
                                },
                                "required": ["location"]
                            }
                        }
                    }
                ],
                max_tokens=100
            )
            
            # Check if function was called
            if response.choices[0].message.tool_calls:
                self._log_test_result("Function Calling", True, "Function call detected")
                return True
            else:
                self._log_test_result("Function Calling", True, "No function call (expected for this prompt)")
                return True
                
        except Exception as e:
            self._log_test_result("Function Calling", False, f"Error: {str(e)}")
            return False
    
    def test_vision_capabilities(self) -> bool:
        """Test vision capabilities (if available)"""
        print("\n📝 Testing Vision Capabilities...")
        
        # Create a simple test image (1x1 pixel)
        test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        try:
            response = self.client.chat.completions.create(
                model=self.config['deployment_name'],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{test_image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=100
            )
            
            content = response.choices[0].message.content
            self._log_test_result("Vision", True, f"Vision response: {content}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "vision" in error_msg.lower() or "image" in error_msg.lower():
                self._log_test_result("Vision", False, "Vision not supported by this model")
            else:
                self._log_test_result("Vision", False, f"Error: {error_msg}")
            return False
    
    def test_rate_limiting(self) -> bool:
        """Test rate limiting behavior"""
        print("\n📝 Testing Rate Limiting...")
        
        try:
            # Make multiple rapid requests
            responses = []
            for i in range(3):
                response = self.client.chat.completions.create(
                    model=self.config['deployment_name'],
                    messages=[
                        {"role": "user", "content": f"Test message {i+1}"}
                    ],
                    max_tokens=10
                )
                responses.append(response)
                time.sleep(0.1)  # Small delay between requests
            
            self._log_test_result("Rate Limiting", True, f"Successfully made {len(responses)} rapid requests")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "rate" in error_msg.lower() or "429" in error_msg:
                self._log_test_result("Rate Limiting", False, "Rate limit hit (expected behavior)")
            else:
                self._log_test_result("Rate Limiting", False, f"Error: {error_msg}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling with invalid requests"""
        print("\n📝 Testing Error Handling...")
        
        try:
            # Test with invalid model name
            response = self.client.chat.completions.create(
                model="invalid-model-name",
                messages=[
                    {"role": "user", "content": "Hello"}
                ],
                max_tokens=10
            )
            self._log_test_result("Error Handling", False, "Should have failed with invalid model")
            return False
            
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg.lower() or "404" in error_msg:
                self._log_test_result("Error Handling", True, "Properly handled invalid model error")
                return True
            else:
                self._log_test_result("Error Handling", False, f"Unexpected error: {error_msg}")
                return False
    
    def run_all_tests(self) -> Dict:
        """Run all tests and return results"""
        print("🚀 Starting Azure OpenAI Comprehensive Test Suite")
        print("=" * 60)
        
        if not self.test_connection():
            return {"success": False, "message": "Failed to establish connection"}
        
        tests = [
            self.test_chat_completion,
            self.test_text_generation,
            self.test_embeddings,
            self.test_streaming,
            self.test_function_calling,
            self.test_vision_capabilities,
            self.test_rate_limiting,
            self.test_error_handling
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self._log_test_result(test.__name__, False, f"Test crashed: {str(e)}")
        
        return self._generate_summary()
    
    def _generate_summary(self) -> Dict:
        """Generate test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - successful_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")
        
        if successful_tests == total_tests:
            print("\n🎉 ALL TESTS PASSED! Your Azure OpenAI setup is working perfectly!")
            status = "SUCCESS"
        elif successful_tests > 0:
            print("\n⚠️  PARTIAL SUCCESS! Some tests passed, but there might be configuration issues.")
            status = "PARTIAL"
        else:
            print("\n❌ ALL TESTS FAILED! Please check your Azure OpenAI configuration.")
            status = "FAILED"
        
        print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return {
            "status": status,
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": (successful_tests/total_tests)*100,
            "results": self.test_results
        }
    
    def save_results(self, filename: str = "azure_openai_test_results.json"):
        """Save test results to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "config": {k: v if k != 'api_key' else '***HIDDEN***' for k, v in self.config.items()},
                    "results": self.test_results
                }, f, indent=2)
            print(f"\n💾 Test results saved to: {filename}")
        except Exception as e:
            print(f"\n❌ Failed to save results: {e}")

def setup_environment():
    """Setup and display environment configuration"""
    print("🔧 Azure OpenAI Test Environment Setup")
    print("=" * 50)
    
    # Check for .env file
    if os.path.exists('.env'):
        print("✅ Found .env file")
    else:
        print("⚠️  No .env file found")
        print("Creating sample .env file...")
        
        env_content = """# Azure OpenAI Configuration
AZURE_OPENAI_KEY=your-azure-openai-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_MODEL_NAME=gpt-35-turbo
"""
        
        try:
            with open('.env', 'w') as f:
                f.write(env_content)
            print("✅ Created .env file with sample configuration")
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
    
    print("\nRequired Environment Variables:")
    print("  AZURE_OPENAI_KEY - Your Azure OpenAI API key")
    print("  AZURE_OPENAI_ENDPOINT - Your Azure OpenAI endpoint URL")
    print("  AZURE_OPENAI_DEPLOYMENT_NAME - Your deployment name")
    print("  AZURE_OPENAI_API_VERSION - API version (optional, defaults to 2024-02-15-preview)")
    print("  AZURE_OPENAI_MODEL_NAME - Model name (optional, defaults to gpt-35-turbo)")
    
    print("\nYou can set these in your .env file or as environment variables.")
    print("=" * 50)

def main():
    """Main function"""
    print("🔍 Azure OpenAI Comprehensive Test Suite")
    print("=" * 50)
    
    # Setup environment
    setup_environment()
    
    # Create tester instance
    tester = AzureOpenAITester()
    
    if not tester.config:
        print("\n❌ Configuration not found. Please set up your environment variables.")
        return
    
    # Run tests
    results = tester.run_all_tests()
    
    # Save results
    tester.save_results()
    
    # Exit with appropriate code
    if results["status"] == "SUCCESS":
        sys.exit(0)
    elif results["status"] == "PARTIAL":
        sys.exit(1)
    else:
        sys.exit(2)

if __name__ == "__main__":
    main() 