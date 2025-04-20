# Heurist Dev Examples - Development Guide

## Build & Run Commands
- **JS Examples**: `npm install && node basic/[category]/[file].js`
- **Python Examples**: 
  - Setup: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
  - Run: `python basic/[category]/[file].py`
- **TokenIntel-TelegramBot**: `pip install -r mesh-agents/TokenIntel-TelegramBot/requirements.txt && python mesh-agents/TokenIntel-TelegramBot/main.py`
- **Sheets Pipeline**: `pip install -r mesh-agents/sheets-pipeline/requirements.txt && python mesh-agents/sheets-pipeline/workflow_agent.py`

## Code Style Guidelines
- **JS**: ES modules, async/await for API calls, proper error handling with try/catch
- **Python**: 
  - Version: 3.8+
  - Imports: Standard lib first, third-party second, local modules last
  - Types: Use type hints for function parameters and return values
  - Error handling: Use try/except blocks with specific exceptions
  - Environment vars: Load from .env files with python-dotenv
- **API Keys**: Never hardcode, use environment variables
- **Naming**: snake_case for Python, camelCase for JavaScript
- **Documentation**: Include comments for non-obvious code, docstrings for functions