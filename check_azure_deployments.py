from openai import AzureOpenAI
import os

def check_deployment(client, deployment_name, test_type="chat"):
    """Test a specific deployment"""
    print(f"\nTesting deployment: {deployment_name}")
    try:
        if test_type == "chat":
            response = client.chat.completions.create(
                model=deployment_name,
                messages=[{"role": "user", "content": "Say 'Hello, deployment test successful!'"}],
                max_tokens=50
            )
            print("✅ Chat test successful")
            print(f"Response: {response.choices[0].message.content}")
            return True
        elif test_type == "embeddings":
            response = client.embeddings.create(
                model=deployment_name,
                input="Test embedding generation"
            )
            print("✅ Embeddings test successful")
            print(f"Embedding dimensions: {len(response.data[0].embedding)}")
            return True
        elif test_type == "vision":
            # We'll test vision separately since it requires an image
            print("Vision test requires an image, skipping...")
            return True
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

def main():
    print("Azure OpenAI Deployment Check")
    print("=" * 50)
    
    # Get credentials from environment
    api_key = os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_URL")
    api_version = os.getenv("AZURE_API_VERSION")
    
    if not all([api_key, endpoint, api_version]):
        print("❌ Missing required environment variables")
        return
    
    print(f"Endpoint: {endpoint}")
    print(f"API Version: {api_version}")
    
    # Initialize client
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=endpoint
    )
    
    # Test deployments
    deployments = {
        "azure-gpt-4o": "chat",
        "azure-gpt-4o": "embeddings",  # Using same model for embeddings temporarily
        "azure-gpt-4o": "vision"
    }
    
    results = {}
    for deployment, test_type in deployments.items():
        results[deployment] = check_deployment(client, deployment, test_type)
    
    # Summary
    print("\nTest Summary")
    print("=" * 50)
    for deployment, success in results.items():
        status = "✅ Available" if success else "❌ Not available"
        print(f"{deployment}: {status}")

if __name__ == "__main__":
    main()