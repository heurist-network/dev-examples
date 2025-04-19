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

1. **Heurist Mesh MCP Platform**: Connects to the [Heurist Mesh MCP platform](https://mcp.heurist.ai/) which provides access to multiple AI agents including:
   - CoinGecko (cryptocurrency data)
   - Elfa Twitter (Twitter data)
   - GoPlus (blockchain security)
   - DexScreener (DEX analytics)
   - Zerion (DeFi portfolio)
   - And many other social media and blockchain-related services

   The platform allows you to select which agents you want to include in your custom MCP server and provides a dedicated endpoint URL.

2. **Google Sheets MCP Server**: Integrates with [mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) to provide direct interaction with Google Sheets, enabling creation, reading, updating, and management of spreadsheets through the Google Sheets API.

## MCP Proxy

This project uses [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy), a tool that lets you switch between server transports. It supports two modes:

1. **stdio to SSE mode**: Connects to remote SSE servers (like Heurist Mesh MCP) even when not natively supported by clients. This mode is used to connect to the Heurist Mesh platform.

2. **SSE to stdio mode**: Exposes a local stdio server as an SSE server. This mode is used for the Google Sheets MCP server.

The proxy handles the transport layer communication, allowing the different components to work together seamlessly.

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

### Heurist Mesh MCP Setup

1. Visit [Heurist Mesh MCP platform](https://mcp.heurist.ai/)
2. Enter your Heurist API key (or register for a free key)
3. Select the agents you want to include (CoinGecko, GoPlus, etc.)
4. Create a dedicated MCP server
5. Copy the provided MCP server URL for use in your environment variables

### Google Cloud Setup (Required)

1. Create a Google Cloud Platform project
2. Enable the Google Sheets API and Google Drive API
3. Create a service account with appropriate permissions
4. Download the service account JSON key file
5. Create a dedicated folder in Google Drive to share with the service account
   - Note the folder's ID from its URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
   - Share it with the service account email address (found in the JSON file)
   - Give it "Editor" access

### Environment Variables

Create a `.env` file with the following variables:

```
# Google Gemini API settings
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_gemini_api_key_here

# Google Sheets settings
SERVICE_ACCOUNT_FILE=credentials.json
SPREADSHEET_ID=your_spreadsheet_id_here

# Google Sheets MCP Server settings
SERVICE_ACCOUNT_PATH=/path/to/service-account-key.json
DRIVE_FOLDER_ID=your_shared_folder_id_here

# Heurist Mesh MCP settings
HEURIST_MESH_MCP_URL=your_heurist_mesh_mcp_url

# Other settings
UVX_PATH=/path/to/uvx
```

## Project Structure

- `workflow_agent.py` - Main application code that sets up and runs the agent
- `.env` - Environment configuration

## Usage

Run the agent in interactive chat mode:

```
python workflow_agent.py
```

You can ask questions like:
- "What are the current trending tokens? Save the results to my Google new spreadsheet"
- "Get the 5 most recent Trump posts. And identify if they are positive or negative related to finanial markets. Save the results to my Google new spreadsheet"


## Google Sheets MCP Integration

This project leverages the [mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) server, which provides the following functionality:

### Available Tools

1. `get_sheet_data` - Get data from a specific sheet in a Google Spreadsheet
2. `update_cells` - Update cells in a Google Spreadsheet
3. `batch_update_cells` - Batch update multiple ranges in a Google Spreadsheet
4. `list_sheets` - List all sheets in a Google Spreadsheet
5. `list_spreadsheets` - List all spreadsheets in the configured Google Drive folder
6. `create_spreadsheet` - Create a new Google Spreadsheet
7. `create_sheet` - Create a new sheet tab in an existing Google Spreadsheet
8. Additional tools: `add_rows`, `add_columns`, `copy_sheet`, `rename_sheet`

## Heurist Mesh MCP Integration

The Heurist Mesh platform provides access to multiple specialized agents. Depending on which agents you selected when creating your MCP server, you'll have access to different tools. Common tools include:

1. **CoinGecko**: Get cryptocurrency price data, market information, and historical charts
2. **GoPlus**: Analyze smart contract security, check for scams, and verify token safety
3. **DexScreener**: Access DEX trading pair data, liquidity information, and trading volumes
4. **Zerion**: Track DeFi portfolios, token balances, and protocol interactions
5. **Space and Time**: Query blockchain data and analytics
6. And many more financial and blockchain-related services

## Troubleshooting

- **Authentication errors**: Ensure your service account JSON is correctly referenced and has sufficient permissions
- **MCP connection errors**: Verify that both `mcp-proxy` and `uvx` are installed correctly and accessible in your PATH
- **Google Sheets access issues**: Check that the service account has been properly shared with the Drive folder
- **Heurist Mesh access issues**: Verify your API key is valid and that you've created a dedicated MCP server on the platform
- **MCP proxy issues**: If Claude Desktop can't start the server (ENOENT code in logs), try using the full path to the binary. Find it with `where mcp-proxy` (macOS, Linux) or `where.exe mcp-proxy` (Windows)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Powered by Google's Agent Development Kit (ADK)
- Uses [mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) for Google Sheets integration
- [Heurist Mesh MCP platform](https://mcp.heurist.ai/) for blockchain and financial data services
- [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) for MCP server transport connectivity
- Model Context Protocol (MCP) for tool integration 