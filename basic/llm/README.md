# LLM Integration Examples

This folder contains examples for integrating with Heurist's LLM Gateway using both the OpenAI-compatible SDK and direct REST API calls.

## Prerequisites
- Heurist API Key ([Get one here](https://dev-api-form.heurist.ai/))
- Node.js (for JavaScript examples)
- Python 3.8+ (for Python examples)

## Examples

### JavaScript
- `llm_openai_sdk.js` - OpenAI SDK integration for text generation
- `llm_rest_api.js` - REST API integration for text generation
- `tool_calling.js` - Tool/function calling with Hermes Llama-3.1 model

### Python
- `llm_openai_sdk.py` - OpenAI SDK integration with streaming and non-streaming
- `llm_rest_api.py` - REST API integration for text generation
- `tool-calling.py` - Tool/function calling with Hermes Llama-3.1 model

## Getting Started

### JavaScript
```bash
npm install openai
node llm_openai_sdk.js
```

### Python
```bash
pip install openai requests
python llm_openai_sdk.py
```

## Documentation
- [LLM Gateway Documentation](https://docs.heurist.ai/dev-guide/llm-gateway/introduction)
- [Supported Models](https://docs.heurist.ai/dev-guide/supported-models)