#!/usr/bin/env python3
import sys
import argparse
import logging
from src.config.settings import Settings  # Import Settings instead of dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to stdout for easier debugging
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the application."""
    logger.info("Starting BlockBeak Telegram Bot application")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="OpenAI Agent with MCP Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.info("Debug logging enabled")
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize settings singleton (loads environment variables)
    logger.info("Initializing settings")
    try:
        settings = Settings()
        logger.info(f"Settings initialized with MCP proxy URL: {settings.mcp_proxy_url}")
    except Exception as e:
        logger.error(f"Error initializing settings: {str(e)}", exc_info=True)
        sys.exit(1)
    
    # Always start the Telegram bot interface
    logger.info("Starting Telegram bot interface")
    try:
        from src.interfaces.telegram.bot import main as telegram_main
        telegram_main()
    except Exception as e:
        logger.error(f"Error starting Telegram bot: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {str(e)}", exc_info=True)
        sys.exit(1) 