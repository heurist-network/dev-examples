#!/usr/bin/env python3

"""
Main entry point for running the XMTP API server.

This script starts the FastAPI server that provides the /inbox endpoint
for processing XMTP messages through the BlockBeak agent.
"""

import os
import sys
import logging
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.interfaces.xmtp.api import run_api

def main():
    """Main entry point for the XMTP API server."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
        level=logging.INFO
    )
    
    # Get configuration from environment variables
    host = os.getenv("XMTP_API_HOST", "127.0.0.1")
    port = int(os.getenv("XMTP_API_PORT", "8000"))
    reload = os.getenv("XMTP_API_RELOAD", "false").lower() == "true"
    
    print(f"Starting XMTP API server on {host}:{port}")
    print("Press Ctrl+C to stop the server")
    
    try:
        run_api(host=host, port=port, reload=reload)
    except KeyboardInterrupt:
        print("\nShutting down XMTP API server...")
    except Exception as e:
        print(f"Error starting XMTP API server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()