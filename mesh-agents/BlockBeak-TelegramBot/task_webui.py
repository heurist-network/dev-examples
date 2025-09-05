#!/usr/bin/env python3
"""
Launcher script for Tasks WebUI.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

def main():
    """Start the Tasks WebUI with default settings."""
    
    # Set default environment variables if not already set
    if "TASKS_WEBUI_ENABLED" not in os.environ:
        os.environ["TASKS_WEBUI_ENABLED"] = "true"
    
    # You can customize these defaults as needed
    if "TASKS_WEBUI_HOST" not in os.environ:
        os.environ["TASKS_WEBUI_HOST"] = "127.0.0.1"
    
    if "TASKS_WEBUI_PORT" not in os.environ:
        os.environ["TASKS_WEBUI_PORT"] = "8789"
    
    # Optional: Set admin token for full access (uncomment and set your token)
    # if "TASKS_WEBUI_ADMIN_TOKEN" not in os.environ:
    #     os.environ["TASKS_WEBUI_ADMIN_TOKEN"] = "your-secret-token-here"
    
    # Import and run the app
    from src.tasks.webui.app import main as run_webui
    
    print("\n" + "="*60)
    print("Starting BlockBeak Tasks WebUI")
    print("="*60)
    
    if not os.environ.get("TASKS_WEBUI_ADMIN_TOKEN"):
        print("⚠️  Running in READ-ONLY mode")
        print("   To enable admin actions, set TASKS_WEBUI_ADMIN_TOKEN")
    else:
        print("✓ Admin mode enabled")
    
    print("="*60 + "\n")
    
    run_webui()

if __name__ == "__main__":
    main()
