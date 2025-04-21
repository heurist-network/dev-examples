import asyncio
import re
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams, StdioServerParameters
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService # Optional
from google.adk.runners import Runner
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import json
import datetime
import ast
import os
import time
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
APP_NAME = "crypto_data_pipeline"
USER_ID = "user_123"
SESSION_ID = "session_123"
GEMINI_MODEL = "gemini-2.5-pro-preview-03-25"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds

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
        
        # Second MCP server
        logger.info("Connecting to second MCP server...")
        tools2, stack2 = await MCPToolset.from_server(
            connection_params=StdioServerParameters(
                command=os.environ.get('UVX_PATH'),
                args=["mcp-google-sheets"],
                env={
                    "SERVICE_ACCOUNT_PATH": os.environ.get('SERVICE_ACCOUNT_PATH'),
                    "DRIVE_FOLDER_ID": os.environ.get('DRIVE_FOLDER_ID')
                }
            )
        )
        exit_stack.push_async_exit(lambda *args, **kwargs: stack2.aclose())
        all_tools.extend(tools2)
        logger.info(f"Successfully connected to second MCP server. Got {len(tools2)} tools.")
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
    crypto_agent = LlmAgent(
        model=GEMINI_MODEL,
        name='crypto_data_assistant',
        instruction="""
You are a expert in tool use. You can finish the tasks using the tools provided and based on the user's request.
When dealing with large amounts of data, try to process it in smaller chunks to avoid hitting API limits.
If a network error occurs, provide a helpful message to the user suggesting they try again or use a simpler query.
        """,
        tools=tools,
        generate_content_config=types.GenerateContentConfig(maxOutputTokens=100000) # https://ai.google.dev/api/generate-content#v1beta.GenerationConfig
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
            
            while True:
                # Get user input
                user_query = input("You: ")
                
                # Check if user wants to exit
                if user_query.lower() in ['exit', 'quit']:
                    print("Ending conversation. Goodbye!")
                    break
                
                # Process the user query with retry logic
                print("\nAssistant: Processing your request...")
                try:
                    events_async = await process_user_query_with_retry(runner, session, user_query)
                    
                    # Print assistant responses
                    response_text = ""
                    async for event in events_async:
                        if hasattr(event, 'message') and event.message and hasattr(event.message, 'parts'):
                            for part in event.message.parts:
                                if hasattr(part, 'text') and part.text:
                                    response_text += part.text
                        logger.debug(f"Event: {event}")
                    
                    if response_text:
                        print(f"\nAssistant: {response_text}\n")
                    print("-" * 50)
                
                except httpx.ConnectError as e:
                    logger.error(f"Network connection error: {e}")
                    print("\nAssistant: I'm having trouble connecting to the server. This might be due to network issues or a temporary service outage. Please try again in a moment or try a simpler query that processes less data.\n")
                    print("-" * 50)
                
                except Exception as e:
                    logger.error(f"Error processing query: {e}")
                    print(f"\nAssistant: I encountered an error while processing your request: {str(e)}. Please try again or modify your query.\n")
                    print("-" * 50)
                    
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

