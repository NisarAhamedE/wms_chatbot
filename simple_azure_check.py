import os
from openai import AzureOpenAI

def test_azure_connection():
    """Test Azure OpenAI connection"""
    try:
        # Initialize the client
        client = AzureOpenAI(
            api_key="db8dac9cea3148d48c348ed46e9bfb2d",
            api_version="2024-02-15-preview",
            azure_endpoint="https://bodeu-des-csv02.openai.azure.com/"
        )

        # Test with a simple completion
        response = client.chat.completions.create(
            model="azure-gpt-4o",  # deployment name
            messages=[
                {"role": "user", "content": "Say 'Hello, Azure OpenAI is working!' if you can see this message."}
            ],
            max_tokens=100
        )

        # Print the response
        print("✅ Connection Test Successful!")
        print(f"Response: {response.choices[0].message.content}")
        return True

    except Exception as e:
        print(f"❌ Connection Test Failed!")
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔍 Testing Azure OpenAI Connection...")
    test_azure_connection()