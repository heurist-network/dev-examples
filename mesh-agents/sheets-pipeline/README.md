# Crypto Data Pipeline

A data assistant built with Google's Agent Development Kit (ADK) that integrates with MCP Servers to fetch real-time information from various sources including cryptocurrency data, social media, blockchain security, and financial analytics, and automatically save it to Google Sheets.

## Features

- Fetch real-time cryptocurrency and financial market data
- Access social media and blockchain security information
- Save data automatically to Google Sheets
- Interactive chat interface for data queries across multiple domains
- Multiple MCP server integration for advanced tool capabilities
- Robust error handling and data extraction

## Prerequisites

- Python 3.9+
- Google Cloud account with Google Sheets API and Google Drive API enabled
- Service account with Google Sheets access
- Heurist API key for accessing Heurist Mesh MCP platform
- MCP tools client ([mcp-proxy](https://github.com/sparfenyuk/mcp-proxy))
- UV package manager for Python (`uvx`)

## MCP Server Integration

This project leverages two Model Context Protocol (MCP) servers:

1. **Heurist Mesh MCP Platform**: Connects directly to the [Heurist Mesh MCP platform](https://mcp.heurist.ai/) using SSE (Server-Sent Events) protocol. The platform provides access to multiple AI agents including:
   - CoinGecko (cryptocurrency data)
   - Elfa Twitter (Twitter data)
   - GoPlus (blockchain security)
   - DexScreener (DEX analytics)
   - Zerion (DeFi portfolio)
   - And many other social media and blockchain-related services

   The platform allows you to create a custom MCP server with the specific agents you need by:
   - Visiting [mcp.heurist.ai](https://mcp.heurist.ai/)
   - Entering your Heurist API key (or registering for a free key)
   - Selecting the agents you want to include
   - Creating a dedicated MCP server
   - Copying the provided SSE endpoint URL for use in your environment variables (`HEURIST_MESH_MCP_URL`)

2. **Google Sheets MCP Server**: Integrates with [mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) to provide direct interaction with Google Sheets, enabling creation, reading, updating, and management of spreadsheets through the Google Sheets API.


## Installation

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install the MCP proxy client:
   ```
   # Option 1: With uv (recommended)
   uv tool install mcp-proxy

   # Option 2: With pipx (alternative)
   pipx install mcp-proxy

   # Option 3: Latest version from GitHub
   uv tool install git+https://github.com/sparfenyuk/mcp-proxy
   ```

4. Install UV package manager:
   ```
   curl -sSf https://install.ultraviolet.dev | sh
   ```

## Configuration

### Model Provider Configuration

This application supports multiple language model providers:

1. **Google Gemini** (default): Uses Google's Gemini models directly
2. **LiteLLM**: Provides access to various models including OpenAI/GPT, Anthropic, and others through OpenRouter or directly

Configure your preferred model provider in the `.env` file:

```
# Model Provider Settings
MODEL_PROVIDER=gemini  # Options: 'gemini' or 'litellm'
GEMINI_MODEL=gemini-2.5-flash-preview-04-17  # Used when MODEL_PROVIDER=gemini
LITELLM_MODEL=openai/gpt-4.1  # Used when MODEL_PROVIDER=litellm
OPENROUTER_API_KEY=your_openrouter_api_key  # Required for litellm with OpenRouter
OPENROUTER_API_BASE=https://openrouter.ai/api/v1  # Required for litellm with OpenRouter

# Google Sheets MCP Server settings
UVX_PATH=/path/to/uvx
SERVICE_ACCOUNT_PATH=/path/to/service-account-key.json
DRIVE_FOLDER_ID=your_shared_folder_id_here

# Heurist Mesh MCP settings
HEURIST_MESH_MCP_URL=your_heurist_mesh_mcp_url
```

### Heurist Mesh MCP Setup

1. Visit [Heurist Mesh MCP platform](https://mcp.heurist.ai/)
2. Enter your Heurist API key (or register for a free key)
3. Select the agents you want to include (CoinGecko, GoPlus, etc.)
4. Create a dedicated MCP server
5. Copy the provided SSE endpoint URL for use in your `HEURIST_MESH_MCP_URL` environment variable

### Google Cloud Setup (Required)

1. Create a Google Cloud Platform project
2. Enable the Google Sheets API and Google Drive API
3. Create a service account with appropriate permissions
4. Download the service account JSON key file
5. Create a dedicated folder in Google Drive to share with the service account
   - Note the folder's ID from its URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
   - Share it with the service account email address (found in the JSON file)
   - Give it "Editor" access

## Project Structure

- `workflow_agent.py` - Main application code that sets up and runs the agent
- `.env` - Environment configuration

## Usage

Run the agent in interactive chat mode:

```
python workflow_agent.py
```

You can ask questions like:
- "Find me the trending tokens on CoinGecko today. No need to confirm—just save their symbol, current price (USD) by create a new spreadsheet‘CoinGecko Dashboard’, sheet 'Trending', if the spreadsheet not exist."
- "Get every tweet posted by @elonmusk. No need to confirm—just create a new spreadsheet titled 'elonmusk‑tweets‑2025‑04‑21' with a sheet named 'elonmusk', and write these columns for each tweet: timestamp, text"

## Heurist Mesh MCP Integration

The Heurist Mesh platform provides access to multiple specialized agents through a direct SSE connection. Depending on which agents you selected when creating your MCP server, you'll have access to different tools. Common tools include:

1. **CoinGecko**: Get cryptocurrency price data, market information, and historical charts
2. **GoPlus**: Analyze smart contract security, check for scams, and verify token safety
3. **DexScreener**: Access DEX trading pair data, liquidity information, and trading volumes
4. **Zerion**: Track DeFi portfolios, token balances, and protocol interactions
5. **Space and Time**: Query blockchain data and analytics
6. And many more financial and blockchain-related services


## Google Sheets MCP Integration

This project leverages the [mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) server, which provides the following functionality:

### Available Tools

1. `get_sheet_data` - Get data from a specific sheet in a Google Spreadsheet
   - Input: spreadsheet_id, sheet, range (optional)
   - Returns: A 2D array of the sheet data

2. `update_cells` - Update cells in a Google Spreadsheet
   - Input: spreadsheet_id, sheet, range, data (2D array)
   - Returns: Result of the update operation

3. `batch_update_cells` - Batch update multiple ranges in a Google Spreadsheet
   - Input: spreadsheet_id, sheet, ranges (dictionary mapping range strings to 2D arrays)
   - Returns: Result of the batch update operation

4. `list_sheets` - List all sheets in a Google Spreadsheet
   - Input: spreadsheet_id
   - Returns: List of sheet names

5. `list_spreadsheets` - List all spreadsheets in the configured Google Drive folder
   - Returns: List of spreadsheets with their ID and title
   - Note: Lists spreadsheets in the shared folder when using service account authentication

6. `create_spreadsheet` - Create a new Google Spreadsheet
   - Input: title
   - Returns: Information about the newly created spreadsheet including its ID
   - Note: Created in the configured folder when using service account authentication

7. `create_sheet` - Create a new sheet tab in an existing Google Spreadsheet
   - Input: spreadsheet_id, title
   - Returns: Information about the newly created sheet

8. `get_multiple_sheet_data` - Get data from multiple specific ranges in Google Spreadsheets
   - Input: queries (array of objects with spreadsheet_id, sheet, and range)
   - Returns: List of objects containing query parameters and fetched data or error

9. `get_multiple_spreadsheet_summary` - Get a summary of multiple Google Spreadsheets
   - Input: spreadsheet_ids, rows_to_fetch (optional, default 5)
   - Returns: List of objects with spreadsheet title, sheet names, headers, and first few rows

10. `share_spreadsheet` - Share a Google Spreadsheet with multiple users
    - Input: spreadsheet_id, recipients (array with email_address and role), send_notification (optional)
    - Returns: Dictionary with lists of successes and failures

11. Additional tools: `add_rows`, `add_columns`, `copy_sheet`, `rename_sheet`



## Troubleshooting

- **Authentication errors**: Ensure your service account JSON is correctly referenced and has sufficient permissions
- **MCP connection errors**: Verify your Heurist Mesh MCP URL is correct and that your API key is valid
- **Google Sheets access issues**: Check that the service account has been properly shared with the Drive folder
- **Second MCP server connection issues**: If you encounter timeouts or errors with the Google Sheets MCP server, check the `UVX_PATH`, `SERVICE_ACCOUNT_PATH`, and `DRIVE_FOLDER_ID` environment variables. You can also set `SKIP_SECOND_MCP=True` in workflow_agent.py to bypass this server if needed.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Powered by Google's Agent Development Kit (ADK)
- Uses [mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) for Google Sheets integration
- [Heurist Mesh MCP platform](https://mcp.heurist.ai/) for blockchain and financial data services
- Model Context Protocol (MCP) for tool integration 