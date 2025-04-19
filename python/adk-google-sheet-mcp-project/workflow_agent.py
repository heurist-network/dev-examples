import asyncio
import re
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService # Optional
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
from contextlib import AsyncExitStack

# load environment variables
load_dotenv(override=True)

# --- Configuration ---
APP_NAME = "crypto_data_pipeline"
USER_ID = "user_123"
SESSION_ID = "session_123"
GEMINI_MODEL = "gemini-2.5-pro-preview-03-25"

# --- Step 1: Import Tools from MCP Server ---
async def get_tools_async():
    """Gets tools from multiple MCP Servers."""
    # Create a combined exit stack
    exit_stack = AsyncExitStack()
    all_tools = []
    
    # First MCP server
    print("Connecting to first MCP server...")
    tools1, stack1 = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command='mcp-proxy',
            args=[os.environ.get('HEURIST_MESH_MCP_URL')]
        )
    )
    exit_stack.push_async_exit(lambda *args, **kwargs: stack1.aclose())
    all_tools.extend(tools1)
    
    # Second MCP server
    print("Connecting to second MCP server...")
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
    
    # Add more servers as needed...
    
    print(f"Fetched {len(all_tools)} tools from all MCP servers.")
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
        """,
        tools=tools
    )
    return crypto_agent, exit_stack

async def async_main():
  try:
    session_service = InMemorySessionService()
    artifacts_service = InMemoryArtifactService()
    
    # Get tools and agent
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
        
        print("\n===== Interactive Crypto Data Assistant =====")
        print("Type 'exit' or 'quit' to end the conversation.\n")
        
        while True:
            # Get user input
            user_query = input("You: ")
            
            # Check if user wants to exit
            if user_query.lower() in ['exit', 'quit']:
                print("Ending conversation. Goodbye!")
                break
            
            # Process the user query
            content = types.Content(role='user', parts=[types.Part(text=user_query)])
            
            print("\nAssistant: Processing your request...")
            events_async = runner.run_async(
                session_id=session.id, user_id=session.user_id, new_message=content
            )
            
            # Print assistant responses
            response_text = ""
            async for event in events_async:
                if hasattr(event, 'message') and event.message and hasattr(event.message, 'parts'):
                    for part in event.message.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
                print(f"Event: {event}")
            
            if response_text:
                print(f"\nAssistant: {response_text}\n")
            print("-" * 50)
  except Exception as e:
    print(f"Error during execution: {e}")
    import traceback
    traceback.print_exc()

if __name__ == '__main__':
  try:
    asyncio.run(async_main())
  except Exception as e:
    print(f"An error occurred: {e}")

