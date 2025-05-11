#!/usr/bin/env python3

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import logging


class Settings:
    """
    Configuration settings manager for the application.
    Loads settings from environment variables and provides accessor methods.
    
    This is implemented as a singleton to ensure environment variables
    are loaded only once and consistently accessed throughout the application.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls, env_file: Optional[str] = None, force_reload: bool = False):
        """
        Create a singleton instance of Settings.
        
        Args:
            env_file: Optional path to a .env file to load
            force_reload: Whether to force reload environment variables
        """
        if cls._instance is None or force_reload:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._initialized = False
        return cls._instance
    
    def __init__(self, env_file: Optional[str] = None, force_reload: bool = False):
        """
        Initialize settings by loading from environment variables.
        
        Args:
            env_file: Optional path to a .env file to load
            force_reload: Whether to force reload environment variables
        """
        # Skip initialization if already initialized and not forcing reload
        if self._initialized and not force_reload:
            return
            
        logger = logging.getLogger(__name__)
        logger.info(f"Initializing Settings (force_reload={force_reload})")
            
        # Find the .env file if not specified
        if env_file is None:
            env_path = Path(__file__).resolve().parent.parent.parent / '.env'
            logger.info(f"Loading environment from {env_path}")
            load_dotenv(env_path, override=True)  # Always override to ensure latest values
        else:
            logger.info(f"Loading environment from {env_file}")
            load_dotenv(env_file, override=True)  # Always override to ensure latest values
            
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
        
        # Mark as initialized
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
    
    def get_agent_config(self) -> Dict[str, Any]:
        """Get the agent configuration settings."""
        return {
            "model": self.default_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
    
    def is_telegram_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.telegram_token and self.telegram_chat_id) 