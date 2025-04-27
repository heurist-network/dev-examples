#!/usr/bin/env python3

import os
import sys
import argparse
import asyncio
from src.config.settings import Settings  # Import Settings instead of dotenv

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="OpenAI Agent with MCP Server")
    parser.add_argument("--no-stream", action="store_true", help="Use non-streaming mode for CLI")
    parser.add_argument("--model", type=str, help="OpenAI model to use")
    parser.add_argument("--temperature", type=float, help="Model temperature")
    parser.add_argument("--max-tokens", type=int, help="Maximum tokens")
    parser.add_argument("--telegram", action="store_true", help="Run as a Telegram bot")
    args = parser.parse_args()
    
    # Initialize settings singleton (loads environment variables)
    settings = Settings()
    
    # Prepare agent kwargs from command line arguments
    agent_kwargs = {}
    if args.model:
        agent_kwargs['model'] = args.model
    if args.temperature is not None:
        agent_kwargs['temperature'] = args.temperature
    if args.max_tokens is not None:
        agent_kwargs['max_tokens'] = args.max_tokens
    
    # Choose interface based on arguments
    if args.telegram:
        from src.interfaces.telegram.bot import main as telegram_main
        telegram_main()
    else:
        from src.interfaces.cli.terminal import main as cli_main
        cli_main(streaming=not args.no_stream, **agent_kwargs)

if __name__ == "__main__":
    main() 