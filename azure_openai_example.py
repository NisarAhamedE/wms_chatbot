#!/usr/bin/env python3
"""
Azure OpenAI Example Script
Simple examples of Azure OpenAI usage
"""

import os
import sys
from datetime import datetime

# Try to import required libraries
try:
    from openai import AzureOpenAI
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Missing required library: {e}")
    print("Please install required packages: pip install -r requirements.txt")
    sys.exit(1)

# Load environment variables
load_dotenv()

def setup_client():
    """Setup Azure OpenAI client"""
    api_key = os.getenv('AZURE_OPENAI_KEY')
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
    deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    
    if not all([api_key, endpoint, deployment_name]):
        print("❌ Missing required environment variables!")
        print("Please set: AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME")
        return None
    
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        print("✅ Azure OpenAI client initialized successfully!")
        return client, deployment_name
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return None, None

def example_chat_completion(client, deployment_name):
    """Example: Basic chat completion"""
    print("\n📝 Example 1: Basic Chat Completion")
    print("-" * 40)
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello! Can you tell me a short joke?"}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        print(f"Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_text_generation(client, deployment_name):
    """Example: Text generation"""
    print("\n📝 Example 2: Text Generation")
    print("-" * 40)
    
    try:
        response = client.completions.create(
            model=deployment_name,
            prompt="Write a haiku about programming:",
            max_tokens=50,
            temperature=0.8
        )
        
        print(f"Generated text: {response.choices[0].text}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_embeddings(client, deployment_name):
    """Example: Generate embeddings"""
    print("\n📝 Example 3: Text Embeddings")
    print("-" * 40)
    
    try:
        response = client.embeddings.create(
            model=deployment_name,
            input="This is a sample text for embedding generation."
        )
        
        embedding = response.data[0].embedding
        print(f"Generated embedding with {len(embedding)} dimensions")
        print(f"First 5 values: {embedding[:5]}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_streaming(client, deployment_name):
    """Example: Streaming chat completion"""
    print("\n📝 Example 4: Streaming Chat")
    print("-" * 40)
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "user", "content": "Count from 1 to 10:"}
            ],
            max_tokens=50,
            temperature=0.1,
            stream=True
        )
        
        print("Streaming response: ", end="", flush=True)
        for chunk in response:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print()  # New line after streaming
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_conversation(client, deployment_name):
    """Example: Multi-turn conversation"""
    print("\n📝 Example 5: Multi-turn Conversation")
    print("-" * 40)
    
    try:
        # First message
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "What is Python?"}
        ]
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        assistant_response = response.choices[0].message.content
        print(f"User: What is Python?")
        print(f"Assistant: {assistant_response}")
        
        # Add assistant's response to conversation
        messages.append({"role": "assistant", "content": assistant_response})
        
        # Second message
        messages.append({"role": "user", "content": "What are its main features?"})
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        assistant_response2 = response.choices[0].message.content
        print(f"User: What are its main features?")
        print(f"Assistant: {assistant_response2}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_function_calling(client, deployment_name):
    """Example: Function calling"""
    print("\n📝 Example 6: Function Calling")
    print("-" * 40)
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "user", "content": "What's the weather like in San Francisco?"}
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
        
        message = response.choices[0].message
        
        if message.tool_calls:
            print("Function call detected:")
            for tool_call in message.tool_calls:
                print(f"  Function: {tool_call.function.name}")
                print(f"  Arguments: {tool_call.function.arguments}")
        else:
            print("No function call made (expected for this example)")
            print(f"Response: {message.content}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_error_handling(client, deployment_name):
    """Example: Error handling"""
    print("\n📝 Example 7: Error Handling")
    print("-" * 40)
    
    try:
        # Try with invalid model name
        response = client.chat.completions.create(
            model="invalid-model-name",
            messages=[
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=10
        )
        print("Unexpected: Request succeeded with invalid model")
        return False
    except Exception as e:
        print(f"Expected error caught: {type(e).__name__}: {e}")
        return True

def main():
    """Main function to run all examples"""
    print("🚀 Azure OpenAI Examples")
    print("=" * 50)
    
    # Setup client
    client, deployment_name = setup_client()
    if not client:
        return
    
    # Run examples
    examples = [
        ("Basic Chat", example_chat_completion),
        ("Text Generation", example_text_generation),
        ("Embeddings", example_embeddings),
        ("Streaming", example_streaming),
        ("Conversation", example_conversation),
        ("Function Calling", example_function_calling),
        ("Error Handling", example_error_handling)
    ]
    
    results = []
    for name, example_func in examples:
        print(f"\n🔄 Running: {name}")
        try:
            success = example_func(client, deployment_name)
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 EXAMPLE SUMMARY")
    print("=" * 50)
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"Total Examples: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {total - successful}")
    
    if successful == total:
        print("🎉 All examples completed successfully!")
    else:
        print("\nFailed examples:")
        for name, success in results:
            if not success:
                print(f"  - {name}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 