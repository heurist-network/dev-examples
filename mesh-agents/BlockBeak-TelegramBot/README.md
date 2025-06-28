# BlockBeak Telegram Bot - Multi-Provider AI Agent

A sophisticated AI agent built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) that provides a Telegram bot interface with support for multiple LLM providers through LiteLLM integration.

BlockBeak specializes in **cryptocurrency Q&A and analysis** while serving as a **generalist assistant**. The agent features dynamic personality adaptation, autonomous exploration capabilities, and seamless integration with the Heurist Mesh network.

## 🚀 Key Features

- **Multi-Provider LLM Support**: Use OpenAI, Anthropic, OpenRouter, XAI, or Heurist models
- **Dynamic Personality System**: Adapts communication style based on query context (Analyst, Pragmatic Pro, The Pulse)
- **Advanced Crypto Analysis**: Comprehensive token research, market data, social sentiment, and on-chain analysis
- **Heurist Mesh Integration**: Access specialized AI agents through MCP (Model Control Protocol)
- **Autonomous Tool Usage**: Intelligent tool selection and iterative refinement
- **Telegram Bot Interface**: Easy-to-use chat interface with command support
- **Robust Error Handling**: Retry mechanisms and comprehensive logging
- **Configurable Architecture**: Flexible settings for model parameters and behavior

## 🔗 Heurist Mesh Integration

This project integrates with [Heurist Mesh](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh), a network of modular and purpose-built AI agents. Each Mesh agent is a specialized unit designed to excel at specific tasks such as:

- Processing data from external APIs
- Analyzing on-chain data
- Fetching crypto market information
- Analyzing social media sentiment
- Web content extraction and analysis

The BlockBeak-TelegramBot connects to these specialized agents through MCP (Model Control Protocol), allowing it to access a rich ecosystem of AI capabilities. This connection is handled through the MCP proxy, which must be configured with the appropriate endpoint in your environment variables.

Learn more about MCP at [mcp.heurist.ai](https://mcp.heurist.ai/).

## 🛠️ Installation & Setup with `uv`

This project uses `uv` for fast Python package management and virtual environments, leveraging its native project management features.

### 1. Install `uv`

If you don't have `uv` installed, follow the official installation guide: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)

**Using pipx:**
```bash
pipx install uv
```

**On macOS with Homebrew:**
```bash
brew install uv
```

### 2. Create and Activate Virtual Environment

Navigate to the project root directory and run:
```bash
uv venv
```

Activate the virtual environment:
```bash
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

Synchronize your environment with the project's locked dependencies:
```bash
uv sync
```

This command uses the `uv.lock` file to ensure a reproducible environment.

### 4. Set up Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Required: Choose your LLM provider and configure accordingly
MODEL_PROVIDER=openai  # Options: openai, anthropic, openrouter, xai, heurist
API_KEY=your_api_key_here
MODEL=gpt-4o-mini  # Model name for your chosen provider

# Required: MCP SSE URL for Heurist Mesh integration
MCP_SSE_URL=https://your-mcp-sse-endpoint.com

# Required: Telegram Bot configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Optional: Restrict bot access to specific chat IDs
TELEGRAM_CHAT_ID=123456789,987654321

# Optional: Agent behavior settings
TEMPERATURE=0.1
MAX_TOKENS=500000
```

### Provider-Specific Configuration

#### OpenAI
```bash
MODEL_PROVIDER=openai
API_KEY=sk-...
MODEL=gpt-4o-mini
```

#### Anthropic
```bash
MODEL_PROVIDER=anthropic
API_KEY=sk-ant-...
MODEL=claude-3-5-sonnet-20241022
```

#### OpenRouter
```bash
MODEL_PROVIDER=openrouter
API_KEY=sk-or-...
MODEL=anthropic/claude-3-5-sonnet
```

#### XAI
```bash
MODEL_PROVIDER=xai
API_KEY=your-xai-api-key
MODEL=x-1
```

#### Heurist
```bash
MODEL_PROVIDER=heurist
API_KEY=your-heurist-api-key
MODEL=gpt-4o-mini
```

## 🚀 Usage

### Starting the Telegram Bot

After setting up your environment variables, run the bot:

```bash
uv run python main.py
```

Or with debug logging:
```bash
uv run python main.py --debug
```

### Bot Commands

The Telegram bot supports the following commands:

- `/help` - Show available commands and usage information
- `/model` - Display current model settings and provider
- `/ask [question]` - Ask a question to the AI assistant

**Example interactions:**
```
/ask What's the current price of Bitcoin?
/ask Tell me about the Heurist AI token
/ask Why did PEPE pump today?
/ask What's the weather like in New York?
```

## 🏗️ Project Structure

```
BlockBeak-TelegramBot/
├── main.py                      # Main entry point
├── pyproject.toml              # Project configuration and dependencies
├── uv.lock                     # Locked dependency versions
├── README.md                   # Project documentation
└── src/                        # Source code
    ├── __init__.py             # Package initialization
    ├── core/                   # Core functionality
    │   ├── __init__.py         # Package initialization
    │   └── agent.py            # Agent implementation with multi-provider support
    ├── config/                 # Configuration
    │   ├── __init__.py         # Package initialization
    │   ├── settings.py         # Settings manager with provider configuration
    │   └── agent_instructions.yaml  # Agent behavior and personality definitions
    └── interfaces/             # User interfaces
        ├── __init__.py         # Package initialization
        └── telegram/           # Telegram interface
            ├── __init__.py     # Package initialization
            └── bot.py          # Telegram bot implementation
```

## 🔧 Configuration

### Agent Behavior Customization

The agent's behavior is defined in `src/config/agent_instructions.yaml`. Key features include:

- **Dynamic Personality System**: Adapts between Analyst, Pragmatic Pro, and The Pulse modes
- **Crypto Analysis Capabilities**: Comprehensive token research and market analysis
- **Autonomous Tool Usage**: Intelligent tool selection and iterative refinement
- **Heurist AI Token Knowledge**: Built-in knowledge about the Heurist project

### Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `MODEL_PROVIDER` | Yes | LLM provider to use | `openai`, `anthropic`, `openrouter`, `xai`, `heurist` |
| `API_KEY` | Yes | API key for the chosen provider | `sk-...` |
| `MODEL` | Yes | Model name for the provider | `gpt-4o-mini`, `claude-3-5-sonnet` |
| `MCP_SSE_URL` | Yes | MCP SSE endpoint for Heurist Mesh | `https://mcp.heurist.ai/...` |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from @BotFather | `1234567890:ABC...` |
| `TELEGRAM_CHAT_ID` | No | Comma-separated list of allowed chat IDs | `123456789,987654321` |
| `TEMPERATURE` | No | Model temperature (0.0-1.0) | `0.1` |
| `MAX_TOKENS` | No | Maximum tokens for responses | `500000` |

## 🛠️ Development

### Managing Dependencies

**Adding a new dependency:**
```bash
uv add <package-name>
```

**Updating all dependencies:**
```bash
uv lock --upgrade
uv sync
```

**Updating a specific dependency:**
```bash
uv add <package-name>@latest
```

### Key Dependencies

- `openai-agents[litellm]==0.0.14` - Core agent framework with LiteLLM support
- `pyTelegramBotAPI>=4.14.0` - Telegram bot interface
- `python-dotenv==1.0.0` - Environment variable management
- `pyyaml>=6.0.1` - YAML configuration parsing

## 🔍 Agent Capabilities

### Crypto Analysis Features

- **Token Identification**: Cross-chain token and address resolution
- **Market Data**: Price, volume, liquidity analysis via Dexscreener
- **Social Sentiment**: Twitter/X analysis with full URL citations
- **On-Chain Analysis**: Holder data, transaction patterns, wallet tracking
- **Background Research**: Project origins, team information, news analysis

### General Assistant Features

- **Web Content Extraction**: Using firecrawl for URL content analysis
- **Multi-language Support**: Responds in the user's query language
- **Dynamic Personality**: Adapts communication style based on context
- **Autonomous Planning**: Self-directed tool usage and iterative refinement

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is developed by the Heurist team. For more information, visit [heurist.xyz](https://heurist.xyz).

## 🔗 Links

- [Heurist Mesh](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh)
- [MCP Documentation](https://mcp.heurist.ai/)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [LiteLLM Documentation](https://docs.litellm.ai/)