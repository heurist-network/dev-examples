# OpenAI Agent with MCP Server

A modular implementation of an OpenAI agent using the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) with support for a Telegram bot interface.

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
- **Telegram Bot Interface**: Interact with the agent via Telegram.
- **Configurable**: Customizable model, temperature, and other settings
- **Tracing**: Integrated with OpenAI's tracing system for debugging

## Installation & Setup with `uv`

This project uses `uv` for fast Python package management and virtual environments, leveraging its native project management features.

1.  **Install `uv`**:
    If you don't have `uv` installed, follow the official installation guide: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
    For example, using pipx:
    ```bash
    pipx install uv
    ```
    Or on macOS with Homebrew:
    ```bash
    brew install uv
    ```

2.  **Create and Activate Virtual Environment**:
    Navigate to the project root directory and run:
    ```bash
    uv venv
    ```
    This will create a `.venv` directory. Activate it:
    ```bash
    source .venv/bin/activate  # On macOS/Linux
    # .venv\Scripts\activate  # On Windows
    ```

3.  **Install Dependencies**:
    Synchronize your environment with the project's locked dependencies:
    ```bash
    uv sync
    ```
    This command uses the `uv.lock` file to ensure a reproducible environment. If `uv.lock` doesn't exist or is out of date with `pyproject.toml`, `uv` might prompt you or automatically run `uv lock`.

4.  **Set up Environment Variables**:
    Copy the example environment file and fill in your details:
    ```bash
    cp .env.example .env
    ```
    Edit the `.env` file to add your OpenAI API key, Telegram bot token, MCP proxy URL, and other necessary configuration.

### Managing Dependencies

-   **Adding a new dependency**:
    ```bash
    uv add <package-name>
    ```
-   **Updating all dependencies** (regenerates `uv.lock` based on `pyproject.toml` constraints):
    ```bash
    uv lock --upgrade
    uv sync
    ```
-   **Updating a specific dependency**:
    ```bash
    uv add <package-name>@latest  # Or <package-name>@"<version-specifier>"
    # This will update pyproject.toml and uv.lock, then run `uv sync` automatically or advise to run it.
    ```
    Alternatively, update `pyproject.toml` manually, then run:
    ```bash
    uv lock
    uv sync
    ```

**Important**: Commit both `pyproject.toml` and `uv.lock` to your version control system (e.g., Git).

## Usage

### Telegram Bot Interface

To use the Telegram interface, you need to:

1. Create a Telegram bot using [@BotFather](https://t.me/BotFather) and get your token
2. Add the token to your `.env` file as `TELEGRAM_BOT_TOKEN`
3. Optionally, add a comma-separated list of allowed chat IDs as `TELEGRAM_CHAT_ID`

Then, after activating your `uv` environment (`source .venv/bin/activate`), run:

```bash
uv run python main.py
```
Or, if you prefer not to activate the environment first, you can directly use:
```bash
uv run -- python main.py
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
OPENAI_DEFAULT_MODEL=gpt-4.1-mini
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=2000

# MCP SSE settings
MCP_SSE_URL=YOUR_MCP_SSE_URL_HERE # you can get one from https://mcp.heurist.ai/

# Telegram Bot settings
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=YOUR_CHAT_ID_1, YOUR_CHAT_ID_2, ... # Optional: Comma-separated list of allowed chat IDs
```

## Bot Commands

The Telegram bot supports the following commands:
- `/help` - Show available commands
- `/model` - Show current model settings
- `/ask [question]` - Ask a question to the AI assistant

The bot primarily responds to the `/ask` command, such as `/ask What's is Heurist Mesh MCP?`.

# OpenAI Agent with Telegram Bot

This project implements an AI assistant using the OpenAI API and provides a Telegram bot interface.

## Setup

(See the main "Installation & Setup with `uv`" section above for the most up-to-date instructions.)

## Running the Telegram Bot

To run the Telegram bot:
1. Ensure your environment is set up and activated (see "Installation & Setup with `uv`").
2. Use the command:
```bash
uv run python main.py
```

### Bot Commands

The bot supports the following commands:
- `/help` - Show available commands
- `/model` - Show current model settings
- `/ask [question] - Ask a question to the AI assistant

The bot only responds to explicit commands. The primary way to interact with the bot is using the `/ask` command, such as `/ask What's is Heurist Mesh MCP?`.

## Features

- Chat with OpenAI assistants via Telegram using commands
- Command-driven interface for precise control
- User authentication based on authorized chat IDs