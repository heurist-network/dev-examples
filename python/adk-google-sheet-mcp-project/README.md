# Crypto Data Pipeline

A cryptocurrency data assistant built with Google's Agent Development Kit (ADK) that integrates with MCP Servers to fetch real-time cryptocurrency price information and automatically save it to Google Sheets.

## Features

- Fetch real-time cryptocurrency data (price, market cap, volume, 24h change)
- Save data automatically to Google Sheets
- Interactive chat interface to query crypto prices
- Multiple MCP server integration for advanced tool capabilities
- Robust error handling and data extraction

## Prerequisites

- Python 3.9+
- Google Cloud account with Google Sheets API and Google Drive API enabled
- Service account with Google Sheets access
- MCP tools client (`mcp-proxy`)
- UV package manager for Python (`uvx`)

## MCP Server Integration

This project leverages two Model Context Protocol (MCP) servers:

1. **Crypto Data MCP Server**: Connects to a specialized MCP server that provides access to cryptocurrency data APIs. This server handles API authentication, rate limiting, and data formatting.

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

3. Install the MCP client:
   ```
   npm install -g mcp-proxy
   ```

4. Install UV package manager:
   ```
   curl -sSf https://install.ultraviolet.dev | sh
   ```

## Configuration

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

# MCP Server endpoints
MCP_PROXY_URL=your_crypto_mcp_server_url
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
- "What's the current price of Bitcoin?"
- "Show me Ethereum price information"
- "Get the latest price for Dogecoin"
- "Create a new spreadsheet with crypto market data"
- "Update my crypto tracking sheet with today's prices"

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

## Troubleshooting

- **Authentication errors**: Ensure your service account JSON is correctly referenced and has sufficient permissions
- **MCP connection errors**: Verify that both `mcp-proxy` and `uvx` are installed correctly and accessible in your PATH
- **Google Sheets access issues**: Check that the service account has been properly shared with the Drive folder

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Powered by Google's Agent Development Kit (ADK)
- Uses [mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) for Google Sheets integration
- Model Context Protocol (MCP) for tool integration 