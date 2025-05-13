#!/usr/bin/env python3

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import logging
import yaml


class Settings:
    """
    Configuration settings manager for the application.
    Loads settings from environment variables and provides accessor methods.
    
    This is implemented as a singleton to ensure environment variables
    are loaded only once and consistently accessed throughout the application.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls, force_reload: bool = False):
        """
        Create a singleton instance of Settings.
        
        Args:
            force_reload: Whether to force reload environment variables
        """
        if cls._instance is None or force_reload:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._initialized = False
        return cls._instance
    
    def __init__(self, force_reload: bool = False):
        """
        Initialize settings by loading from environment variables.
        
        Args:
            force_reload: Whether to force reload environment variables
        """
        # Skip initialization if already initialized and not forcing reload
        if self._initialized and not force_reload:
            return
            
        logger = logging.getLogger(__name__)
        logger.info(f"Initializing Settings (force_reload={force_reload})")
            
        # Load environment from root .env file
        env_path = Path(__file__).resolve().parent.parent.parent / '.env'
        logger.info(f"Loading environment from {env_path}")
        load_dotenv(env_path, override=True)  # Always override to ensure latest values
            
        # Verify API key is set
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")
        
        # Agent settings
        self.default_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4.1-mini")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "500000"))
        
        if not os.getenv("MCP_SSE_URL"):
            raise ValueError("MCP_SSE_URL not found in environment variables. Please set it in .env file.")
        self.mcp_sse_url = os.getenv("MCP_SSE_URL")
        
        # Telegram Bot settings
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        
        # Parse chat IDs directly from os.environ to avoid any caching issues
        chat_id_str = os.environ.get("TELEGRAM_CHAT_ID", "")
        logger.info(f"Raw TELEGRAM_CHAT_ID from os.environ: '{chat_id_str}'")
        self.telegram_chat_id = self._parse_chat_id(chat_id_str)
        
        self.agent_instructions = self._load_agent_instructions()
        
        self._initialized = True
    
    @classmethod
    def reload(cls):
        """Force reload all environment variables."""
        return cls(force_reload=True)
    
    def _parse_chat_id(self, chat_id_str: str) -> Optional[list]:
        """Parse the Telegram chat ID from a string.
        
        Args:
            chat_id_str: String containing comma-separated chat IDs
            
        Returns:
            A list of authorized chat IDs, or None if not configured
        """
        logger = logging.getLogger(__name__)
        
        logger.info(f"Parsing chat IDs from: '{chat_id_str}'")
        
        if not chat_id_str:
            logger.warning("No chat IDs provided")
            return None
        
        try:
            # Split by comma and convert each to integer
            chat_ids = []
            for id_str in chat_id_str.split(','):
                id_str = id_str.strip()
                chat_id = int(id_str)
                logger.info(f"Parsed chat ID: {chat_id} (type: {type(chat_id)})")
                chat_ids.append(chat_id)
                
            if not chat_ids:
                logger.warning("No valid chat IDs found after parsing")
                return None
                
            logger.info(f"Final parsed chat IDs: {chat_ids}")
            return chat_ids
        except ValueError as e:
            error_msg = f"TELEGRAM_CHAT_ID must contain valid integers separated by commas: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _load_agent_instructions(self) -> str:
        """Load agent instructions from YAML file."""
        logger = logging.getLogger(__name__)
        try:
            config_dir = Path(__file__).parent
            yaml_path = config_dir / "agent_instructions.yaml"
            
            if not yaml_path.exists():
                logger.error(f"Agent instructions file not found at: {yaml_path}")
                raise FileNotFoundError(f"Missing agent instructions file: {yaml_path}")
                
            with open(yaml_path, 'r') as f:
                return yaml.safe_load(f)['instructions']
                
        except Exception as e:
            logger.error(f"Failed to load agent instructions: {str(e)}")
            raise
    
    def get_openai_config(self) -> Dict[str, Any]:
        """Get the OpenAI agent configuration settings."""
        return {
            "model": self.default_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "mcp_sse_url": self.mcp_sse_url
        }
    
    def get_telegram_config(self) -> Dict[str, Any]:
        """Get the Telegram bot configuration settings."""
        return {
            "token": self.telegram_token,
            "chat_id": self.telegram_chat_id
        }
    
    def is_telegram_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        telegram_cfg = self.get_telegram_config()
        return bool(telegram_cfg["token"] and telegram_cfg["chat_id"])
    
    def get_agent_instructions(self) -> str:
        """Get the agent instructions."""
        return self.agent_instructions 