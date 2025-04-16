import asyncio
import re
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from mcp.client.stdio import StdioServerParameters
from dotenv import load_dotenv
import json
import datetime
import ast
import os

# load environment variables
load_dotenv(override=True)

# --- Configuration ---
APP_NAME = "crypto_data_pipeline"
USER_ID = "user_123"
SESSION_ID = "session_123"
GEMINI_MODEL = "gemini-2.5-pro-preview-03-25"
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")  # Get from environment variable
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")  # Get from environment variable
SHEET_RANGE = "Sheet1!A1"  # Adjust as needed

# --- Function to Write Data to Google Sheets ---
def write_to_sheet(crypto_data):
    """
    Writes cryptocurrency data to a Google Sheet.
    
    This function takes cryptocurrency data and writes it to the configured 
    Google Spreadsheet using the Google Sheets API.
    
    Args:
        crypto_data (list): A list of data rows to write to the spreadsheet.
                          Each row should be a list of values.
    
    Returns:
        dict: A dictionary containing the status and details of the operation.
              - status: 'success' or 'error'
              - message: Description of the result
              - rows_written: Number of rows written (if successful)
    """
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        body = {'values': crypto_data}
        result = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_RANGE,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        return {
            "status": "success",
            "message": f"Data successfully written to Google Sheet",
            "rows_written": len(crypto_data)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to write data: {str(e)}"
        }

# --- Helper function to parse agent response ---
def parse_crypto_response(text, token_name="Bitcoin"):
    """
    Parse the agent's response text into a single row for Google Sheets.
    
    Args:
        text (str): The agent's response text
        token_name (str): The name of the token (default: Bitcoin)
        
    Returns:
        list: A single row with [token_name, timestamp, price, market_cap, volume, change]
    """
    # Create a single row with token name as first column
    row = [token_name]
    
    # Add timestamp
    row.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Extract price - Updated pattern to handle decimals better
    price = "N/A"
    price_match = re.search(r"price.*?[\$£€]?\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if price_match:
        # Clean up the price and ensure proper decimal handling
        price = price_match.group(1).replace(',', '')
        # Convert to float and back to string to ensure consistent decimal places
        try:
            price = str(float(price))
        except ValueError:
            price = "N/A"
    row.append(price)
    
    # Extract market cap
    market_cap = "N/A"
    market_cap_match = re.search(r"market cap.*?[\$£€]?\s*([\d,.]+[KMBTkmbt]?)", text, re.IGNORECASE)
    if market_cap_match:
        market_cap = market_cap_match.group(1)
    row.append(market_cap)
    
    # Extract volume
    volume = "N/A"
    volume_match = re.search(r"(24h |trading |)volume.*?[\$£€]?\s*([\d,.]+[KMBTkmbt]?)", text, re.IGNORECASE)
    if volume_match:
        volume = volume_match.group(2)
    row.append(volume)
    
    # Extract price change
    change = "N/A"
    change_match = re.search(r"(24h |price |)change.*?([+-]?\s*[\d,.]+%?)", text, re.IGNORECASE)
    if change_match:
        change = change_match.group(2)
    row.append(change)
    
    print(f"Extracted price value: {price}")  # Debug print
    
    # Return as a list containing one row
    return [row]

# --- Function to check if sheet has headers ---
def check_sheet_has_headers(spreadsheet_id, range_name):
    """
    Check if the Google Sheet already has header rows.
    
    Args:
        spreadsheet_id (str): The ID of the spreadsheet
        range_name (str): The range to check (e.g., "Sheet1!A1:F1")
        
    Returns:
        bool: True if headers exist, False otherwise
    """
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # Read the first row
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        # Check if the first row contains headers (non-empty and has our expected headers)
        if values and len(values) > 0:
            headers = values[0]
            expected_headers = ["Token", "Timestamp", "Price", "Market Cap", "24h Volume", "24h Change"]
            
            # If at least 3 of our expected headers are present, consider headers exist
            matches = sum(1 for h in headers if any(eh.lower() in h.lower() for eh in expected_headers))
            return matches >= 3
            
        return False
    except Exception as e:
        print(f"Error checking headers: {e}")
        return False  # Assume no headers on error

# --- Step 1: Import Tools from MCP Server ---
async def get_tools_async():
    """Gets tools from the CoinGecko MCP Server."""
    print("Attempting to connect to MCP CoinGecko server...")
    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command='mcp-proxy',
            args=['https://sequencer-v2.heurist.xyz/tool71e228e5/sse']
        )
    )
    print("MCP Toolset created successfully.")
    print(f"Fetched {len(tools)} tools from MCP server.")
    return tools, exit_stack

# --- Step 2: Agent Definition ---
async def get_agent_async():
    """Creates an ADK Agent equipped with tools from the MCP Server."""
    tools, exit_stack = await get_tools_async()
    crypto_agent = LlmAgent(
        model=GEMINI_MODEL,
        name='crypto_data_assistant',
        instruction="""
        You are a cryptocurrency data agent. When asked about Bitcoin:
        1. Use the coingeckotokeninfoagent_get_token_info tool with coingecko_id="bitcoin"
        2. Format the response into a clear, readable summary with the current price,
           market cap, 24h volume, and 24h change percentage.
        3. Present the information in a clean, structured format that's easy to read.
        """,
        tools=tools
    )
    return crypto_agent, exit_stack

# --- Function to get token data for a specific cryptocurrency ---
async def get_token_data(session_service, session_id, user_id, crypto_agent, token_name, token_id):
    """
    Get data for a specific cryptocurrency using the agent.
    
    Args:
        session_service: Session service object
        session_id: Session ID
        user_id: User ID
        crypto_agent: The LLM agent
        token_name: Display name of the token (e.g., "Bitcoin")
        token_id: CoinGecko ID of the token (e.g., "bitcoin")
        
    Returns:
        str: The token data text from the agent, or None if an error occurred
    """
    query = f"What is the current price and market data for {token_name}? Use coingecko_id={token_id}"
    print(f"\nUser Query for {token_name}: '{query}'")
    
    content = types.Content(role='user', parts=[types.Part(text=query)])
    
    runner = Runner(
        app_name=APP_NAME,
        agent=crypto_agent,
        session_service=session_service,
    )
    
    print(f"Running agent for {token_name}...")
    events_async = runner.run_async(
        session_id=session_id, user_id=user_id, new_message=content
    )
    
    token_data = None
    try:
        async for event in events_async:
            if event.is_final_response() and hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        token_data = part.text
                        print(f"\nFinal result for {token_name}:\n{token_data}")
                        break
    except Exception as e:
        print(f"Error in event processing for {token_name}: {e}")
    
    return token_data

# --- Modified Main Execution Logic for dynamic token list ---
async def async_main():
    session_service = InMemorySessionService()
    session = session_service.create_session(
        state={}, app_name=APP_NAME, user_id=USER_ID
    )
    
    # Get tools and agent
    tools, exit_stack = await get_tools_async()
    crypto_agent = LlmAgent(
        model=GEMINI_MODEL,
        name='crypto_data_assistant',
        instruction="""
        You are a cryptocurrency data agent. When asked about a specific cryptocurrency:
        1. Use the coingeckotokeninfoagent_get_token_info tool with the provided coingecko_id
        2. Format the response into a clear, readable summary with the current price,
           market cap, 24h volume, and 24h change percentage.
        3. Present the information in a clean, structured format that's easy to read.
        """,
        tools=tools
    )
    
    try:
        # Fixed list of tokens to track
        tokens = [
            {"name": "Bitcoin", "id": "bitcoin"},
            {"name": "Ethereum", "id": "ethereum"},
            {"name": "Solana", "id": "solana"},
            {"name": "XRP", "id": "ripple"},
            {"name": "Cardano", "id": "cardano"},
            {"name": "Polkadot", "id": "polkadot"},
            {"name": "Chainlink", "id": "chainlink"}
        ]
        
        # Check if headers exist and add them if needed (only once)
        has_headers = check_sheet_has_headers(SPREADSHEET_ID, "Sheet1!A1:F1")
        if not has_headers:
            print("Adding header row to sheet...")
            headers = [["Token", "Timestamp", "Price", "Market Cap", "24h Volume", "24h Change"]]
            write_to_sheet(headers)
            print("Headers added successfully.")
        
        # Process each token
        for token in tokens:
            print(f"\n{'='*50}")
            print(f"Processing {token['name']}...")
            
            # Get data for this token
            token_data = await get_token_data(
                session_service,
                session.id, 
                session.user_id, 
                crypto_agent, 
                token['name'], 
                token['id']
            )
            
            # Process and write the data to sheets
            if token_data:
                print(f"\nParsing data for {token['name']}...")
                formatted_data = parse_crypto_response(token_data, token['name'])
                
                print(f"Formatted {token['name']} data:")
                for row in formatted_data:
                    print(f"  {row}")
                
                print(f"\nWriting {token['name']} data to Google Sheets...")
                result = write_to_sheet(formatted_data)
                print(f"Sheet write result for {token['name']}: {result}")
            else:
                print(f"No data received for {token['name']}")
    
    except Exception as e:
        print(f"\nError in main execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Crucial Cleanup
        print("\nCleaning up resources...")
        await exit_stack.aclose()
        print("Cleanup complete.")

if __name__ == '__main__':
    try:
        print("Starting cryptocurrency data pipeline...")
        asyncio.run(async_main())
    except Exception as e:
        print(f"An error occurred: {e}")