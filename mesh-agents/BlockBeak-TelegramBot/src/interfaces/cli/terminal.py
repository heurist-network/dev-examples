#!/usr/bin/env python3

import os
import asyncio
from src.core.agent import AgentManager
from src.config.settings import Settings

class TerminalInterface:
    """Terminal interface for interacting with the agent."""
    
    def __init__(self, streaming=True, **agent_kwargs):
        """
        Initialize the terminal interface.
        
        Args:
            streaming: Whether to stream responses
            agent_kwargs: Additional kwargs to pass to AgentManager
        """
        self.streaming = streaming
        self.settings = Settings()
        self.agent_config = self.settings.get_agent_config()
        
        # Override any settings with provided kwargs
        if agent_kwargs:
            self.agent_config.update(agent_kwargs)
        
        self.agent_manager = AgentManager(**self.agent_config)
        
        # Show current configuration
        self._print_config()
    
    def _print_config(self):
        """Print the current configuration."""
        print("\n=== Agent Configuration ===")
        print(f"Model: {self.agent_config['model']}")
        print(f"Temperature: {self.agent_config['temperature']}")
        print(f"Max Tokens: {self.agent_config['max_tokens']}")
        print(f"MCP URL: {self.agent_config['mcp_proxy_url']}")
        print("==========================\n")
    
    async def _get_streaming_response(self, message):
        """Get a streaming response from the agent."""
        try:
            # Reload environment variables before each request
            self.settings = Settings.reload()
            
            # Reinitialize agent manager with fresh settings
            self.agent_config = self.settings.get_agent_config()
            self.agent_manager = AgentManager(**self.agent_config)
            
            print("\nProcessing your request...\n")
            
            # Get streaming response
            stream = await self.agent_manager.process_message_robust(
                message=message,
                streaming=True
            )
            
            print("Response:")
            print("---")
            async for chunk in stream:
                print(chunk, end="", flush=True)
            print("\n---")
        except Exception as e:
            error_details = getattr(e, 'details', None)
            if error_details:
                print(f"\nError: {error_details.get('type', 'Unknown')}")
                print(f"Message: {error_details.get('message', str(e))}")
                if 'request_id' in error_details:
                    print(f"Request ID: {error_details.get('request_id')}")
            else:
                print(f"\nError: {str(e)}")
    
    async def _get_nonstreaming_response(self, message):
        """Get a non-streaming response from the agent."""
        try:
            # Reload environment variables before each request
            self.settings = Settings.reload()
            
            # Reinitialize agent manager with fresh settings
            self.agent_config = self.settings.get_agent_config()
            self.agent_manager = AgentManager(**self.agent_config)
            
            print("\nProcessing your request...\n")
            
            # Get non-streaming response
            response = await self.agent_manager.process_message_robust(
                message=message,
                streaming=False
            )
            
            print("Response:")
            print("---")
            print(response)
            print("---")
        except Exception as e:
            error_details = getattr(e, 'details', None)
            if error_details:
                print(f"\nError: {error_details.get('type', 'Unknown')}")
                print(f"Message: {error_details.get('message', str(e))}")
                if 'request_id' in error_details:
                    print(f"Request ID: {error_details.get('request_id')}")
            else:
                print(f"\nError: {str(e)}")
    
    async def run(self):
        """Run the terminal interface."""
        print("OpenAI Agent Terminal Interface")
        print("Type 'exit' or 'quit' to end the session")
        
        while True:
            message = input("\nYou: ")
            
            # Exit condition
            if message.lower() in ('exit', 'quit'):
                print("Goodbye!")
                break
            
            if self.streaming:
                await self._get_streaming_response(message)
            else:
                await self._get_nonstreaming_response(message)

def main(streaming=True, **agent_kwargs):
    """
    Main entry point for the CLI interface.
    
    Args:
        streaming: Whether to stream responses
        agent_kwargs: Additional kwargs to pass to AgentManager
    """
    terminal = TerminalInterface(streaming=streaming, **agent_kwargs)
    asyncio.run(terminal.run())

if __name__ == "__main__":
    main() 