#!/usr/bin/env python3
"""
Launcher script for Tasks WebUI.
"""

import os
import sys

# Set environment variables for testing
os.environ["TASKS_WEBUI_ENABLED"] = "true"

# Optional: Set admin token for testing (remove in production)
if not os.environ.get("TASKS_WEBUI_ADMIN_TOKEN"):
    os.environ["TASKS_WEBUI_ADMIN_TOKEN"] = "test-admin-token"
    print("⚠️  Using test admin token. Set TASKS_WEBUI_ADMIN_TOKEN for production.")

# Import and run the WebUI
from src.tasks.webui.app import main

if __name__ == "__main__":
    main()
