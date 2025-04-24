import asyncio
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams, StdioServerParameters
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService # Optional
from google.adk.runners import Runner
from google.genai import types
from dotenv import load_dotenv
import json
import datetime
import os
import logging
import httpx
from contextlib import AsyncExitStack
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# load environment variables
load_dotenv(override=True)

# --- Configuration ---
APP_NAME = "adk_agent_heurist_mcp_data_pipeline"
USER_ID = "user_123"
SESSION_ID = "session_123"
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17" # "gemini-2.5-flash-preview-04-17" # "gemini-2.5-pro-preview-03-25"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
# Skip second MCP server if it causes problems
SKIP_SECOND_MCP = False  # Set to False to attempt connecting to the second MCP server

INSTRUCTION = """
## 1. High-level role

**You are a data-ops assistant.**  
Your job is to:

1. Understand the user's request for external data (e.g., crypto prices, API responses, on-chain stats).  
2. Fetch or compute that data with whatever non-Sheets tools are available to you.  
3. Persist the results into the correct Google Spreadsheet, creating sheets/columns when needed, while preserving headers and existing rows.

*Keep every step deterministic, idempotent, and fully traceable inside the spreadsheet.*

---

## 2. General workflow you must follow

1. **Identify the target spreadsheet & sheet**  
   - If the user gives a link, extract the `spreadsheet_id`.  
   - If they give only a title, call `list_spreadsheets` and match on *title* (case-insensitive). If none exists, call `create_spreadsheet`.  
   - If the required sheet tab is missing, call `create_sheet`.

2. **Inspect existing layout**  
   - Call `get_sheet_data` on the header row (`range: '1:1'`) to learn the column order.  
   - If you need to append rows, call `get_sheet_data` *without* a range to count existing rows.

3. **Fetch / compute the new data**  
   - Use the domain-specific tools or external APIs that satisfy the user's query.  
   - Sanitise values: strings only, no formulas, booleans as `TRUE/FALSE`, dates in ISO‑8601.

4. **Write the data**  
   - **Appending rows:**  
     1. Determine the next empty row number **N**.  
     2. Call `update_cells` with `range: 'A$$N:...'` and a 2-D array of the new rows.  
   - **Updating specific cells or many ranges:**  
     - Build a *ranges → values* map and call `batch_update_cells`.  
   - **Adding structure:**  
     - If you need new columns, call `add_columns`; then write headers first, data second.

5. **Post-write verification** *(optional but recommended)*  
   - Read back the same range with `get_sheet_data`; compare in-memory vs. expected.  
   - Log any mismatch to the user.

6. **Share if required**  
   - When the user asks to give others access, call `share_spreadsheet` with the correct e-mails and roles.

---

## 3.Style & safety rules

- Never overwrite headers (row 1) unless explicitly instructed.  
- Do not expose credentials or raw JSON key content.  
- Gracefully handle `PERMISSION_DENIED` or `NOT_FOUND` errors: explain and stop.  
- Use `batch_update_cells` when touching ≥ 2 non-contiguous ranges; otherwise use `update_cells`.  
- All tool calls **must** be wrapped in explicit JSON blocks per ADK format.  
- Echo a short natural-language summary to the user after successful writes (e.g., "Added 3 rows of BTC price data to *prices* sheet in **crypto-tracker** spreadsheet.").
"""

# --- Step 1: Import Tools from MCP Server ---
async def get_tools_async():
    """Gets tools from multiple MCP Servers."""
    # Create a combined exit stack
    exit_stack = AsyncExitStack()
    all_tools = []
    
    try:
        # First MCP server
        logger.info("Connecting to first MCP server...")
        tools1, stack1 = await MCPToolset.from_server(
            connection_params=SseServerParams(
                url=os.environ.get('HEURIST_MESH_MCP_URL')
            )
        )
        exit_stack.push_async_exit(lambda *args, **kwargs: stack1.aclose())
        all_tools.extend(tools1)
        logger.info(f"Successfully connected to first MCP server. Got {len(tools1)} tools.")
        
        # Second MCP server with timeout - changed approach
        if not SKIP_SECOND_MCP:
            logger.info("Connecting to second MCP server...")
            try:
                # Add a timeout context for the second server connection
                async with asyncio.timeout(30):  # 30 second timeout
                    # Ensure we have all required environment variables
                    uvx_path = os.environ.get('UVX_PATH')
                    service_account_path = os.environ.get('SERVICE_ACCOUNT_PATH')
                    drive_folder_id = os.environ.get('DRIVE_FOLDER_ID')
                    
                    logger.info(f"Using UVX_PATH: {uvx_path}")
                    logger.info(f"Using SERVICE_ACCOUNT_PATH: {service_account_path}")
                    logger.info(f"Using DRIVE_FOLDER_ID: {drive_folder_id}")
                    
                    if not all([uvx_path, service_account_path, drive_folder_id]):
                        raise ValueError("Missing required environment variables for second MCP server")
                    
                    # More specific command and arguments
                    tools2, stack2 = await MCPToolset.from_server(
                        connection_params=StdioServerParameters(
                            command=uvx_path,
                            args=["run", "/Users/frankhe/miniconda3/bin/mcp-google-sheets"],
                            env={
                                "SERVICE_ACCOUNT_PATH": service_account_path,
                                "DRIVE_FOLDER_ID": drive_folder_id
                            }
                        )
                    )
                    
                    exit_stack.push_async_exit(lambda *args, **kwargs: stack2.aclose())
                    all_tools.extend(tools2)
                    logger.info(f"Successfully connected to second MCP server. Got {len(tools2)} tools.")
            except asyncio.TimeoutError:
                logger.error("Timeout connecting to second MCP server. Continuing with only first server tools.")
            except Exception as e:
                logger.error(f"Error connecting to second MCP server: {e}")
                logger.error("Continuing with only first server tools.")
        else:
            logger.info("Skipping second MCP server as configured.")
    except Exception as e:
        logger.error(f"Error connecting to MCP servers: {e}")
        # Make sure to clean up any resources that were successfully acquired
        await exit_stack.aclose()
        raise
    
    logger.info(f"Fetched {len(all_tools)} tools from all MCP servers.")
    return all_tools, exit_stack

# --- Step 2: Agent Definition ---
async def get_agent_async():
    """Creates an ADK Agent equipped with tools from the MCP Server."""
    tools, exit_stack = await get_tools_async()
    # crypto_agent = LlmAgent(
    #     model=GEMINI_MODEL,
    #     name='adk_agent_heurist_mcp_data_pipeline',
    #     instruction=INSTRUCTION,
    #     tools=tools,
    #     generate_content_config=types.GenerateContentConfig(maxOutputTokens=500000) # https://ai.google.dev/api/generate-content#v1beta.GenerationConfig
    # )
    crypto_agent = LlmAgent(
        model=LiteLlm(
            model="openai/gpt-4.1",
            api_key=os.environ.get('OPENROUTER_API_KEY'),
            api_base=os.environ.get('OPENROUTER_API_BASE'),
        ),
        name='adk_agent_heurist_mcp_data_pipeline',
        instruction=INSTRUCTION,
        tools=tools,
        generate_content_config=types.GenerateContentConfig(maxOutputTokens=500000) # https://ai.google.dev/api/generate-content#v1beta.GenerationConfig
    )
    return crypto_agent, exit_stack

@retry(
    retry=retry_if_exception_type((httpx.ConnectError, ConnectionError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def process_user_query_with_retry(runner, session, user_query):
    """Process user query with retry logic for network errors."""
    content = types.Content(role='user', parts=[types.Part(text=user_query)])
    logger.info("Processing user query with retries if needed")
    return runner.run_async(
        session_id=session.id, 
        user_id=session.user_id, 
        new_message=content
    )

async def async_main():
    try:
        session_service = InMemorySessionService()
        artifacts_service = InMemoryArtifactService()
        
        # Get tools and agent
        logger.info("Initializing agent with MCP tools")
        root_agent, exit_stack = await get_agent_async()
        
        # Create a logs directory if it doesn't exist
        logs_dir = os.path.join(os.getcwd(), "conversation_logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Generate a unique filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_path = os.path.join(logs_dir, f"conversation_{timestamp}.txt")
        
        # Use with statement to ensure proper cleanup
        async with exit_stack:
            session = session_service.create_session(
                state={}, app_name=APP_NAME, user_id=USER_ID
            )
            
            runner = Runner(
                app_name=APP_NAME,
                agent=root_agent,
                artifact_service=artifacts_service,
                session_service=session_service,
            )
            
            print("\n===== Interactive Data Assistant =====")
            print("Type 'exit' or 'quit' to end the conversation.\n")
            print(f"Conversation will be saved to: {log_file_path}")
            
            # Initialize conversation log
            conversation_log = ["\n===== Interactive Data Assistant =====\n"]
            conversation_log.append(f"Session started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            while True:
                # Get user input
                user_query = input("You: ")
                conversation_log.append(f"You: {user_query}\n")
                
                # Check if user wants to exit
                if user_query.lower() in ['exit', 'quit']:
                    print("Ending conversation. Goodbye!")
                    conversation_log.append("Assistant: Ending conversation. Goodbye!\n")
                    # Save the conversation log to file before exiting
                    with open(log_file_path, "w") as f:
                        f.writelines(conversation_log)
                    print(f"Conversation saved to: {log_file_path}")
                    break
                
                # Process the user query with retry logic
                print("\nAssistant: Processing your request...")
                conversation_log.append("\nAssistant: Processing your request...\n")
                
                try:
                    events_async = await process_user_query_with_retry(runner, session, user_query)
                    
                    # Process events, including function calls and responses
                    async for event in events_async:
                        # Skip empty content
                        if not hasattr(event, 'content') or not event.content:
                            continue
                        
                        author = event.author
                        
                        # Process function calls
                        function_calls = [
                            e.function_call for e in event.content.parts if hasattr(e, 'function_call') and e.function_call
                        ]
                        
                        # Process function responses
                        function_responses = [
                            e.function_response for e in event.content.parts if hasattr(e, 'function_response') and e.function_response
                        ]
                        
                        # Process text responses
                        if event.content.parts and hasattr(event.content.parts[0], 'text') and event.content.parts[0].text:
                            text_response = event.content.parts[0].text
                            print(f"\n[{author}]: {text_response}")
                            conversation_log.append(f"\n[{author}]: {text_response}\n")
                        
                        # Display function calls
                        if function_calls:
                            for function_call in function_calls:
                                function_output = f"\n[{author}]: {function_call.name}( {json.dumps(function_call.args)} )"
                                print(function_output)
                                conversation_log.append(f"{function_output}\n")
                        
                        # Display function responses
                        elif function_responses:
                            for function_response in function_responses:
                                function_name = function_response.name
                                application_payload = function_response.response
                                
                                function_response_output = f"\n[{author}]: {function_name} responds -> {application_payload}"
                                print(function_response_output)
                                conversation_log.append(f"{function_response_output}\n")
                    
                    divider = "-" * 50
                    print(divider)
                    conversation_log.append(f"{divider}\n")
                
                except httpx.ConnectError as e:
                    error_msg = f"Network connection error: {e}"
                    logger.error(error_msg)
                    response = "\nAssistant: I'm having trouble connecting to the server. This might be due to network issues or a temporary service outage. Please try again in a moment or try a simpler query that processes less data.\n"
                    print(response)
                    conversation_log.append(response)
                    print("-" * 50)
                    conversation_log.append(f"{'-' * 50}\n")
                
                except Exception as e:
                    error_msg = f"Error processing query: {e}"
                    logger.error(error_msg)
                    response = f"\nAssistant: I encountered an error while processing your request: {str(e)}. Please try again or modify your query.\n"
                    print(response)
                    conversation_log.append(response)
                    print("-" * 50)
                    conversation_log.append(f"{'-' * 50}\n")
                    
                # Save the conversation log after each interaction
                with open(log_file_path, "w") as f:
                    f.writelines(conversation_log)
                    
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    try:
        asyncio.run(async_main())
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")

