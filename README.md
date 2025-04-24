# Heurist Integration Examples

This repository contains reference implementations to help developers integrate with Heurist AI services, including LLM, embedding, image generation, and using Heurist Mesh Agents.

## Getting Started with Heurist API

### Obtaining Your API Key
**All examples in this repository require a Heurist API key.**

1. Create an API key by purchasing credits with crypto at [Credits and API Management Portal](https://heurist.ai/credits)
2. You can also apply for free trial credits using the [form](https://dev-api-form.heurist.ai/)
3. Use this key in all examples by setting it as an environment variable or directly in the code

### Prerequisites
- Node.js (for JavaScript examples)
- Python 3.8+ (for Python examples)
- Heurist API Key (from steps above)

### Installation

#### For JavaScript Examples
```bash
# Install dependencies for all JavaScript examples
npm install
```

#### For Python Examples
```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies for basic examples
pip install -r requirements.txt

# For specific advanced examples, install their additional dependencies:
# TokenIntel-TelegramBot
pip install -r mesh-agents/TokenIntel-TelegramBot/requirements.txt

# Google Sheets Data Pipeline
pip install -r mesh-agents/sheets-pipeline/requirements.txt
```

## Repository Structure

This repository is organized by functionality:

```
dev-examples/
├── basic/              # Basic integration examples
│   ├── llm/            # LLM examples (both JS and Python)
│   ├── embeddings/     # Embedding examples (both JS and Python)
│   └── image/          # Image generation examples (both JS and Python)
│
├── mesh-agents/        # Advanced Mesh Agent examples
│   ├── BlockBeak-TelegramBot/   # AI-powered Smart Telegram bot
│   ├── TokenIntel-TelegramBot/   # Crypto and web3 intelligence Telegram bot
│   └── sheets-pipeline/ # Google Sheets data pipeline
```

## Basic Generative AI Integration Examples

### LLM Integration
[`basic/llm/`](basic/llm/) - Access Large Language Models through Heurist's LLM Gateway.

Examples in both JavaScript and Python for:
- OpenAI SDK integration
- REST API integration
- Tool/function calling with Hermes Llama-3.1

[LLM Gateway Documentation](https://docs.heurist.ai/dev-guide/llm-gateway/introduction)

### Embedding Generation
[`basic/embeddings/`](basic/embeddings/) - Generate embeddings for semantic search and text analysis.

Examples in both JavaScript and Python for:
- OpenAI-compatible embeddings generation

### Image Generation
[`basic/image/`](basic/image/) - Generate images using Stable Diffusion models.

Examples in both JavaScript and Python for:
- REST API integration
- Heurist SDK integration (JavaScript)
- SmartGen for enhanced generation

[Image Generation Documentation](https://docs.heurist.ai/dev-guide/image-generation/introduction)

## Heurist Mesh Agents

[`mesh-agents/`](mesh-agents/) - Specialized AI agents that provide domain-specific capabilities through API and MCP (Model Context Protocol).

### TokenIntel-TelegramBot
[`mesh-agents/TokenIntel-TelegramBot/`](mesh-agents/TokenIntel-TelegramBot/) - Integrates multiple specialized agents into a Telegram bot for crypto and web3 intelligence:

- ExaSearchAgent (web search)
- ElfaTwitterIntelligenceAgent (Twitter analysis)
- FirecrawlSearchAgent (advanced web search)
- SolWalletAgent (blockchain wallet analysis)

### Google Sheets Data Pipeline
[`mesh-agents/sheets-pipeline/`](mesh-agents/sheets-pipeline/) - Data pipeline that:

- Fetches cryptocurrency and financial data
- Uses Google's Agent Development Kit (ADK)
- Connects to multiple MCP servers
- Automatically populates Google Sheets

### BlockBeak-TelegramBot
[`mesh-agents/BlockBeak-TelegramBot/`](mesh-agents/BlockBeak-TelegramBot/) - AI-powered bird identification Telegram bot that:

- Interfaces with specialized Heurist Mesh agents
- Supports both CLI and Telegram interfaces
- Uses MCP (Model Control Protocol) for agent connectivity
- Provides bird identification and information services

## Creating Your Own Mesh Agent Applications

To build with Heurist Mesh Agents:

1. Get a Heurist API Key from [the developer portal](https://dev-api-form.heurist.ai/)
2. Visit the [Heurist Mesh MCP platform](https://mcp.heurist.ai/)
3. Select your desired specialized agents
4. Create your dedicated MCP server
5. Use the MCP server URL in your application
6. Follow the examples in this repository

## Resources

- [Heurist Official Documentation](https://docs.heurist.ai/introduction)
- [Supported Models](https://docs.heurist.ai/dev-guide/supported-models)
- [Mesh MCP Server Repository](https://github.com/heurist-network/heurist-mesh-mcp-server)
- [Mesh Agents Repository](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh)
- [Create Your Own MCP Server](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh)