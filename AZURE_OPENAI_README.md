# Azure OpenAI Testing Suite

This repository contains comprehensive testing and example scripts for Azure OpenAI services.

## 📁 Files Overview

- `azure_openai_test.py` - Comprehensive test suite for Azure OpenAI
- `azure_openai_example.py` - Simple usage examples
- `test_azure_openai.py` - Original test script (legacy)
- `requirements.txt` - Python dependencies

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root with your Azure OpenAI credentials:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_KEY=your-azure-openai-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_MODEL_NAME=gpt-35-turbo
```

### 3. Run Tests

```bash
# Run comprehensive test suite
python azure_openai_test.py

# Run simple examples
python azure_openai_example.py

# Run original test script
python test_azure_openai.py
```

## 🔧 Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_KEY` | Your Azure OpenAI API key | `sk-1234567890abcdef...` |
| `AZURE_OPENAI_ENDPOINT` | Your Azure OpenAI endpoint URL | `https://myresource.openai.azure.com` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Your deployment name | `gpt-35-turbo-deployment` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_API_VERSION` | API version to use | `2024-02-15-preview` |
| `AZURE_OPENAI_MODEL_NAME` | Model name | `gpt-35-turbo` |

## 📊 Test Coverage

The comprehensive test suite (`azure_openai_test.py`) covers:

### ✅ Core Functionality
- **Connection Test** - Basic client initialization
- **Chat Completion** - Standard chat API
- **Text Generation** - Legacy completions API
- **Embeddings** - Text embedding generation

### ✅ Advanced Features
- **Streaming** - Real-time response streaming
- **Function Calling** - Tool/function calling capabilities
- **Vision** - Image analysis (if supported)
- **Rate Limiting** - API rate limit behavior
- **Error Handling** - Invalid request handling

## 📝 Usage Examples

### Basic Chat Completion

```python
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="your-key",
    api_version="2024-02-15-preview",
    azure_endpoint="https://your-resource.openai.azure.com"
)

response = client.chat.completions.create(
    model="your-deployment-name",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)
```

### Streaming Responses

```python
response = client.chat.completions.create(
    model="your-deployment-name",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Function Calling

```python
response = client.chat.completions.create(
    model="your-deployment-name",
    messages=[{"role": "user", "content": "What's the weather?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    }]
)
```

## 🐛 Troubleshooting

### Common Issues

1. **Missing API Key**
   ```
   ❌ Missing required configuration: api_key
   ```
   - Ensure `AZURE_OPENAI_KEY` is set in your `.env` file

2. **Invalid Endpoint**
   ```
   ❌ Failed to initialize Azure OpenAI client
   ```
   - Check that `AZURE_OPENAI_ENDPOINT` is correct
   - Ensure no trailing slash in the URL

3. **Invalid Deployment Name**
   ```
   ❌ Model not found
   ```
   - Verify `AZURE_OPENAI_DEPLOYMENT_NAME` matches your deployment
   - Check Azure portal for correct deployment name

4. **API Version Issues**
   ```
   ❌ API version not supported
   ```
   - Try updating `AZURE_OPENAI_API_VERSION` to a supported version
   - Common versions: `2024-02-15-preview`, `2023-12-01-preview`

### Getting Your Azure OpenAI Credentials

1. **Create Azure OpenAI Resource**
   - Go to Azure Portal
   - Create a new "Azure OpenAI" resource
   - Note the endpoint URL

2. **Get API Key**
   - In your Azure OpenAI resource
   - Go to "Keys and Endpoint"
   - Copy Key 1 or Key 2

3. **Create Deployment**
   - Go to "Model deployments"
   - Create a new deployment
   - Choose your model (e.g., GPT-35-Turbo)
   - Note the deployment name

## 📈 Test Results

The test suite generates detailed results including:

- Individual test pass/fail status
- Error messages and details
- Success rate percentage
- JSON results file for analysis

Example output:
```
📊 TEST SUMMARY
============================================================
Total Tests: 8
Successful: 7
Failed: 1
Success Rate: 87.5%

❌ Failed Tests:
  - Vision: Vision not supported by this model
```

## 🔒 Security Notes

- Never commit your `.env` file to version control
- The test scripts automatically hide API keys in output
- Use environment variables for production deployments
- Consider using Azure Key Vault for enterprise applications

## 📚 Additional Resources

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Azure OpenAI Quickstart](https://learn.microsoft.com/en-us/azure/ai-services/openai/quickstart)

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📄 License

This project is provided as-is for testing and educational purposes. 