import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get credentials from environment variables
api_key = os.getenv('AZURE_OPENAI_KEY')
endpoint = os.getenv('AZURE_OPENAI_URL')
deployment = os.getenv('AZURE_DEPLOYMENT')

# Check if credentials are set
if not all([api_key, endpoint, deployment]):
    print("❌ Missing credentials! Set AZURE_OPENAI_KEY, AZURE_OPENAI_URL, AZURE_DEPLOYMENT")
    exit(1)

# Create client and test
try:
    client = AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version="2024-12-01-preview")
    response = client.chat.completions.create(model=deployment, messages=[{"role": "user", "content": "Say 'Hello World'"}], max_tokens=10)
    print("✅ Azure OpenAI is working!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Error: {e}") 