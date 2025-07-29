# BlockBeak - AI-Powered Crypto Research Bot

**The entire project runs on just ~200 lines of Python code**, leveraging the OpenAI Agents SDK and Heurist Mesh's Model Context Protocol (MCP). BlockBeak proves that with the right building blocks—an LLM, a clear system prompt, and MCP-enabled agents—you can deliver a full-featured crypto research bot with minimal code.

BlockBeak is a **prompt-driven AI agent** that specializes in **cryptocurrency Q&A and analysis** through Telegram. Rather than complex architectures and extensive engineering, BlockBeak's behavior is entirely driven by its system prompt, which defines agent capabilities, tool usage patterns, and response formats.

## 🎯 The Core Concept

Most AI implementations involve complex architectures and extensive engineering. BlockBeak demonstrates that with the right building blocks, you can create a powerful crypto research tool with remarkable simplicity:

- **~200 lines of core Python logic** in `src/core/agent.py:73-248`
- **System prompt-driven behavior** defined in `src/config/agent_instructions.yaml:1-67`
- **MCP-powered tool ecosystem** through Heurist Mesh integration
- **Multi-provider LLM support** via LiteLLM integration

## 🚀 Key Features

- **Minimal Codebase**: Complete functionality in ~200 lines of Python
- **Prompt-Driven Customization**: Change behavior via prompts, not code refactors
- **Dynamic Personality System**: Adapts communication style (Analyst, Pragmatic Pro, The Pulse)
- **Comprehensive Crypto Analysis**: Token research, market data, social sentiment, on-chain analysis
- **Tool Composability**: Mix & match specialized agents from Heurist Mesh ecosystem
- **Multi-Provider LLM Support**: OpenAI, Anthropic, OpenRouter, XAI, or Heurist models
- **Seamless Integration**: Works out-of-the-box with OpenAI Agents SDK
- **Telegram Bot Interface**: Easy-to-use chat interface with command support

## 🔗 Heurist Mesh Agents in Action

BlockBeak taps into a diverse ecosystem of specialized agents through [Heurist Mesh](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh):

**Market & Trading Data:**
- Bitquery Solana Token Info Agent
- CoinGecko Token Info Agent  
- DexScreener Token Info Agent
- Funding Rate Agent
- PumpFun Token Agent

**Social Intelligence:**
- MindAI KOL Agent
- Moni Twitter Insight Agent
- Truth Social Agent
- Twitter Info Agent

**On-Chain & Wallet Analysis:**
- Solana Wallet Agent
- Zerion Wallet Analysis Agent

**Research & Discovery:**
- Cookie Project Info Agent
- Exa Search Agent
- Firecrawl Search Agent

Each brings domain-specific data—on-chain metrics, social sentiment, funding rates, portfolio analysis—to power comprehensive crypto insights. The connection is handled through MCP (Model Control Protocol), configured via the `MCP_SSE_URL` environment variable.

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
/ask Do a deep dive on EIPs related to intent
/ask Analyze HEU token
```

## 🏗️ How BlockBeak Works

The core logic fits in about 200 lines of Python in `src/core/agent.py:59-248`:

### 1. Establish MCP Connection
```python
self.mcp_server = MCPServerSse(
    name="MCP SSE Server",
    params={"url": self.mcp_sse_url},
    client_session_timeout_seconds=60
)
```

### 2. Instantiate the Agent  
```python
agent = OpenAIAgent(
    name="Assistant",
    instructions=self.instructions,
    mcp_servers=[self.mcp_server],
    model=self._get_model_instance(),
    model_settings=model_settings
)
```

### 3. Process Messages
```python
async with self.mcp_server:
    result = await self._execute_with_retry(
        Runner.run,
        starting_agent=agent,
        input=message,
        context=self.context,
    )
```

Under the hood, retry logic and OOP patterns ensure reliability—but the essence remains refreshingly straightforward.

## 🎨 The Power of System Prompts

BlockBeak's behavior is entirely driven by its system prompt in `src/config/agent_instructions.yaml:1-67`, which defines:

- **Agent capabilities and limits**: Cryptocurrency analysis focus with generalist support
- **When and how to invoke each tool**: Strategic tool selection for comprehensive research  
- **Desired response formats**: Markdown formatting rules, source citations, language matching
- **Dynamic personality adaptation**: Analyst, Pragmatic Pro, and The Pulse modes

**Tweak the prompt and you can transform BlockBeak's personality and scope without touching any Python code.**

## 🏗️ Project Structure

```
BlockBeak-TelegramBot/
├── main.py                      # Main entry point (~50 lines)
├── pyproject.toml              # Project configuration and dependencies
├── uv.lock                     # Locked dependency versions
├── README.md                   # Project documentation
└── src/                        # Source code
    ├── core/                   # Core functionality  
    │   └── agent.py            # Agent implementation (~200 lines core logic)
    ├── config/                 # Configuration
    │   ├── settings.py         # Settings manager with provider configuration
    │   └── agent_instructions.yaml  # System prompt defining agent behavior
    └── interfaces/             # User interfaces
        └── telegram/           # Telegram interface
            └── bot.py          # Telegram bot implementation
```

## 🎯 BlockBeak in Action

Let's look at some examples of what BlockBeak can do when tapping into the Heurist Mesh agent ecosystem:

### Example 1: Deep Research on EIPs
Ask **"Do a deep dive on EIPs related to intent"** and BlockBeak returns structured details on EIP-7521, ERC-4337, relevant links, and governance discussions.

### Example 2: Token Analysis  
Ask **"Analyze HEU token"** and receive cross-validated market data, liquidity insights, social media sentiment, and official references—all aggregated by multiple agents.

### Example 3: Market Context
Ask **"Why did PEPE pump today?"** and get comprehensive analysis combining price data, social sentiment, whale activity, and breaking news.

## 🚀 Why This Matters

- **Development Simplicity**: Build powerful AI tools with ~200 lines of code
- **Seamless Integration**: Heurist Mesh works out-of-the-box with OpenAI Agents SDK  
- **Tool Composability**: Mix & match agents to cover any crypto research need
- **Prompt-Driven Customization**: Change behavior via prompts, not code refactors

## 🔧 Configuration

## 🔄 Try It Yourself

1. **Clone the repo**: `git clone [repository-url]`
2. **Configure your MCP server**: Set `MCP_SSE_URL=https://mcp.heurist.ai/your-endpoint`
3. **Customize the system prompt**: Edit `src/config/agent_instructions.yaml` for your use case
4. **Deploy to your Telegram group**: Set `TELEGRAM_BOT_TOKEN` and run `uv run python main.py`

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