# OpenAI Agent with MCP Server

A modular implementation of an OpenAI agent using the OpenAI Agents SDK with support for multiple interfaces:
- Command-line interface
- Telegram bot interface

The agent can use multiple tools to answer questions and solve complex tasks, planning its approach by chaining together multiple tool calls before providing a final answer.

## Heurist Mesh Integration

This project integrates with [Heurist Mesh](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh), a network of modular and purpose-built AI agents. Each Mesh agent is a specialized unit designed to excel at specific tasks such as:

- Processing data from external APIs
- Analyzing on-chain data
- Fetching crypto market information
- Analyzing social media sentiment

The BlockBeak-TelegramBot connects to these specialized agents through MCP (Model Control Protocol), allowing it to access a rich ecosystem of AI capabilities. This connection is handled through the MCP proxy, which must be configured with the appropriate endpoint in your environment variables.

Learn more about MCP at [mcp.heurist.ai](https://mcp.heurist.ai/).

## Features

- **Modular Design**: Clean separation of concerns using OOD principles
- **Multiple Interfaces**: Choose between CLI and Telegram interfaces
- **Configurable**: Customizable model, temperature, and other settings
- **Tracing**: Integrated with OpenAI's tracing system for debugging

## Installation


1. Create a virtual environment and activate it:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install the required packages:
   ```
   pip install openai python-telegram-bot python-dotenv
   ```

3. Set up environment variables:
   ```
   cp .env.example .env
   ```
   Edit the `.env` file and add your OpenAI API key and other configuration options.

## Usage

### Command-Line Interface

Run the agent in the terminal:

```
python main.py [options]
```

Options:
- `--telegram`: Enable Telegram interface, otherwise the agent will run in CLI mode
- `--model MODEL`: Specify the OpenAI model to use (default: gpt-4o)
- `--temperature TEMP`: Set the model temperature (default: 0.1)
- `--max-tokens TOKENS`: Set the maximum number of tokens (default: 2000)

Once running, you can interact with the agent by typing messages. Type `exit` or `quit` to end the session.

### Telegram Bot Interface

To use the Telegram interface, you need to:

1. Create a Telegram bot using [@BotFather](https://t.me/BotFather) and get your token
2. Add the token to your `.env` file as `TELEGRAM_BOT_TOKEN`
3. Optionally, add a comma-separated list of allowed chat IDs as `TELEGRAM_CHAT_ID`

Then run:

```
python main.py --telegram
```

The bot will start and you can interact with it on Telegram.

## Project Structure

```
BlockBeak-TelegramBot/
├── .env.example             # Example environment variables
├── main.py                  # Main entry point
├── README.md                # Project documentation
└── src/                     # Source code
    ├── __init__.py          # Package initialization
    ├── core/                # Core functionality
    │   ├── __init__.py      # Package initialization
    │   └── agent.py         # Agent implementation
    ├── config/              # Configuration
    │   ├── __init__.py      # Package initialization
    │   └── settings.py      # Settings manager
    └── interfaces/          # User interfaces
        ├── __init__.py      # Package initialization
        ├── cli/             # Command-line interface
        │   ├── __init__.py  # Package initialization
        │   └── terminal.py  # Terminal UI
        └── telegram/        # Telegram interface
            ├── __init__.py  # Package initialization
            └── bot.py       # Telegram bot
```

### Customizing Agent Behavior

To customize how the agent operates:

1. Modify the agent implementation in `src/core/agent.py`
2. Update the instructions or model settings in `src/config/settings.py`

## Environment Variables

The following environment variables can be configured in your `.env` file:

```
# OpenAI API Key (required)
OPENAI_API_KEY=your_openai_api_key

# Agent settings
OPENAI_DEFAULT_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=2000

# MCP Proxy settings
MCP_PROXY_COMMAND=/path/to/mcp-proxy
MCP_PROXY_URL=YOUR_MCP_SSE_URL_HERE # you can get one from https://mcp.heurist.ai/

# Telegram Bot settings
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=YOUR_CHAT_ID_1, YOUR_CHAT_ID_2, ...
```

## Bot Commands

The Telegram bot supports the following commands:
- `/start` - Initialize the bot and get welcome message
- `/help` - Show available commands
- `/model` - Show current model settings
- `/stats` - Show conversation statistics
- `/ask [question]` - Ask a question to the AI assistant
- `/subscribe "query" [hours]` - Subscribe to a recurring query
- `/unsubscribe id` - Remove a subscription
- `/subscriptions` - List all your active subscriptions
- `/save_query name "query"` - Save a query for later use
- `/saved_queries` - List all your saved queries
- `/subscribe_saved name [hours]` - Subscribe to a previously saved query

The bot primarily responds to the `/ask` command, such as `/ask What's the weather like today?`. You can also set up recurring queries with the `/subscribe` command.

### Subscription Feature

The subscription feature allows you to schedule recurring queries that run automatically at specified intervals. For example:

- `/subscribe "analyze token 0x1234abcd" 12` - Analyzes the token every 12 hours
- `/subscribe "check @elonmusk recent tweets" 4` - Checks for new tweets every 4 hours
- `/subscribe "monitor ETH gas prices" 6` - Monitors gas prices every 6 hours

When a scheduled query runs, the bot will:
1. Send a notification that it's running your query
2. Process the query through the AI assistant
3. Send you the results
4. Schedule the next run based on your frequency setting

To manage your subscriptions:
- Use `/subscriptions` to see all your active subscriptions
- Use `/unsubscribe id` to remove a subscription (where `id` is the subscription ID)

### Saved Queries

You can save frequently used queries for easy reuse:

- `/save_query eth_price "check current ethereum price and market cap"`
- `/save_query btc_news "summarize the latest bitcoin news"`

To use your saved queries:
- View them with `/saved_queries`
- Subscribe to them with `/subscribe_saved eth_price 12`

# OpenAI Agent with Telegram Bot

This project implements an AI assistant using the OpenAI API and provides a Telegram bot interface.

## Setup

1. Create a Python virtual environment:
   ```
   python -m venv .venv
   ```

2. Activate the virtual environment:
   ```
   # On macOS/Linux
   source .venv/bin/activate
   
   # On Windows
   .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

## Running the Telegram Bot

To run the Telegram bot in non-streaming mode:

```
python main.py --telegram
```

### Bot Commands

The bot supports the following commands:
- `/start` - Initialize the bot and get welcome message
- `/help` - Show available commands
- `/model` - Show current model settings
- `/stats` - Show conversation statistics
- `/ask [question]` - Ask a question to the AI assistant

The bot only responds to explicit commands. The primary way to interact with the bot is using the `/ask` command, such as `/ask What's the current bitcoin price?`.

## Features

- Chat with OpenAI assistants via Telegram using commands
- Command-driven interface for precise control
- User authentication based on authorized chat IDs

## CLI Mode

To run the CLI version of the assistant:

```
python main.py
``` 