#!/usr/bin/env python3

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import logging
import yaml
from datetime import datetime


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
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        logger.info(f"Loading environment from {env_path}")
        load_dotenv(env_path, override=True)  # Always override to ensure latest values

        # Get provider configuration
        self.provider = os.getenv("MODEL_PROVIDER", "openai").lower()
        if not os.getenv("API_KEY"):
            raise ValueError(
                f"API_KEY not found in environment variables. Please set it in .env file for {self.provider} provider."
            )

        if not os.getenv("MODEL"):
            raise ValueError(
                "MODEL not found in environment variables. Please set it in .env file."
            )

        if not os.getenv("MCP_SSE_URL"):
            raise ValueError(
                "MCP_SSE_URL not found in environment variables. Please set it in .env file."
            )

        valid_providers = ["openai", "anthropic", "openrouter", "xai", "heurist"]
        if self.provider not in valid_providers:
            raise ValueError(
                f"MODEL_PROVIDER must be one of: {', '.join(valid_providers)}"
            )

        # Agent settings
        # Default to OpenAI's latest lightweight model
        self.base_model = os.getenv("MODEL", "gpt-5-mini")
        # Note: GPT-5 models don't support temperature parameter - handled automatically in agent.py
        self.temperature = float(os.getenv("TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("MAX_TOKENS", "500000"))
        self.api_key = os.getenv("API_KEY")
        self.mcp_sse_url = os.getenv("MCP_SSE_URL")
        
        # Debug settings
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() in ["true", "1", "yes"]
        logger.info(f"DEBUG_MODE is {'enabled' if self.debug_mode else 'disabled'}")
        
        # Agent turn limits
        self.max_turns_normal = int(os.getenv("MAX_TURNS_NORMAL", "15"))
        self.max_turns_deep = int(os.getenv("MAX_TURNS_DEEP", "30"))
        logger.debug(f"Max turns - Normal: {self.max_turns_normal}, Deep: {self.max_turns_deep}")

        # Set OPENAI_API_KEY for OpenAI agents library compatibility
        if self.api_key and self.provider == "openai":
            os.environ["OPENAI_API_KEY"] = self.api_key

        # Telegram Bot settings
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

        # Parse chat IDs directly from os.environ to avoid any caching issues
        chat_id_str = os.environ.get("TELEGRAM_CHAT_ID", "")
        logger.info(f"Raw TELEGRAM_CHAT_ID from os.environ: '{chat_id_str}'")
        self.telegram_chat_id = self._parse_chat_id(chat_id_str)
        
        # Parse debug chat IDs for trace URL visibility
        debug_chat_id_str = os.environ.get("TELEGRAM_DEBUG_CHAT_ID", "")
        logger.info(f"Raw TELEGRAM_DEBUG_CHAT_ID from os.environ: '{debug_chat_id_str}'")
        self.telegram_debug_chat_id = self._parse_chat_id(debug_chat_id_str) if debug_chat_id_str else []

        # XMTP settings
        self.xmtp_agent_endpoint = os.getenv("XMTP_AGENT_ENDPOINT", "http://127.0.0.1:8000")

        self.agent_instructions = self._load_agent_instructions()
        
        # Session settings
        self.session_config = self._load_session_config()

        logger.info(f"Configuration loaded successfully for provider: {self.provider}")
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
            for id_str in chat_id_str.split(","):
                id_str = id_str.strip()
                # Skip empty strings (handles trailing commas gracefully)
                if not id_str:
                    continue
                chat_id = int(id_str)
                logger.info(f"Parsed chat ID: {chat_id} (type: {type(chat_id)})")
                chat_ids.append(chat_id)

            if not chat_ids:
                logger.warning("No valid chat IDs found after parsing")
                return None

            logger.info(f"Final parsed chat IDs: {chat_ids}")
            return chat_ids
        except ValueError as e:
            error_msg = (
                f"TELEGRAM_CHAT_ID must contain valid integers separated by commas: {e}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _get_current_date_context(self) -> Dict[str, str]:
        """Get current date context for instruction template injection."""
        try:
            now = datetime.now()
            # Get UTC time as well for more accurate timestamps
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            
            return {
                "current_date": now.strftime("%A, %B %d, %Y"),
                "current_datetime": now.strftime("%Y-%m-%d %H:%M %Z").strip() or now.strftime("%Y-%m-%d %H:%M"),
                "current_datetime_utc": now_utc.strftime("%Y-%m-%d %H:%M UTC"),
                "current_year": now.strftime("%Y"),
                "current_month_year": now.strftime("%B %Y"),
            }
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get current date context: {e}")
            # Fallback to basic values
            return {
                "current_date": "Date unavailable",
                "current_datetime": "DateTime unavailable",
                "current_datetime_utc": "DateTime unavailable",
                "current_year": "2025",
                "current_month_year": "Month unavailable",
            }

    def _load_agent_instructions(self) -> str:
        """Load agent instructions from YAML file with date injection."""
        # For backward compatibility, load the original instructions file
        return self._load_instructions_by_mode("normal")
    
    def _load_instructions_by_mode(self, mode: str = "normal") -> str:
        """Load agent instructions for specific mode from YAML file with date injection.
        
        Args:
            mode: Either "normal" or "deep" mode
            
        Returns:
            Instructions string with injected date context
        """
        logger = logging.getLogger(__name__)
        try:
            config_dir = Path(__file__).parent
            
            # Try mode-specific file first, fallback to original
            if mode in ["normal", "deep"]:
                yaml_path = config_dir / f"agent_instructions_{mode}.yaml"
            else:
                yaml_path = config_dir / "agent_instructions.yaml"
            
            # Fallback to original file if mode-specific doesn't exist
            if not yaml_path.exists():
                yaml_path = config_dir / "agent_instructions.yaml"
                logger.info(f"Mode-specific instructions not found, using default: {yaml_path}")

            if not yaml_path.exists():
                logger.error(f"Agent instructions file not found at: {yaml_path}")
                raise FileNotFoundError(f"Missing agent instructions file: {yaml_path}")

            with open(yaml_path, "r") as f:
                yaml_content = yaml.safe_load(f)["instructions"]

            # Get current date context
            date_context = self._get_current_date_context()
            logger.info(f"Injecting date context into {mode} mode instructions: {date_context}")

            # Inject date context into instructions
            try:
                injected_instructions = yaml_content.format(**date_context)
                logger.info(
                    f"Successfully injected date context into {mode} mode agent instructions"
                )
                return injected_instructions
            except KeyError as e:
                logger.warning(
                    f"Template placeholder not found: {e}. Returning original instructions."
                )
                return yaml_content

        except Exception as e:
            logger.error(f"Failed to load agent instructions for {mode} mode: {str(e)}")
            raise

    def get_openai_config(self) -> Dict[str, Any]:
        """Get the agent configuration settings with multi-provider support."""
        config = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "mcp_sse_url": self.mcp_sse_url,
            "provider": self.provider,
            "api_key": self.api_key,
            "debug_mode": self.debug_mode,
        }

        if self.provider == "openai":
            config["model"] = self.base_model
        elif self.provider == "anthropic":
            config["model"] = (
                f"anthropic/{self.base_model}"
                if not self.base_model.startswith("anthropic/")
                else self.base_model
            )
        elif self.provider == "openrouter":
            config["model"] = (
                f"openrouter/{self.base_model}"
                if not self.base_model.startswith("openrouter/")
                else self.base_model
            )
        elif self.provider == "xai":
            config["model"] = (
                f"xai/{self.base_model}"
                if not self.base_model.startswith("xai/")
                else self.base_model
            )
        elif self.provider == "heurist":
            # Heurist is an OpenAI-compatible endpoint, so use openai/ prefix
            config["base_url"] = "https://llm-gateway.heurist.xyz/v1"
            config["model"] = (
                f"openai/{self.base_model}"
                if not self.base_model.startswith("openai/")
                else self.base_model
            )

        return config

    def get_telegram_config(self) -> Dict[str, Any]:
        """Get the Telegram bot configuration settings."""
        return {
            "token": self.telegram_token, 
            "chat_id": self.telegram_chat_id,
            "debug_chat_id": self.telegram_debug_chat_id
        }

    def is_telegram_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        telegram_cfg = self.get_telegram_config()
        return bool(telegram_cfg["token"] and telegram_cfg["chat_id"])
    
    def is_debug_enabled_for_chat(self, chat_id: int) -> bool:
        """Check if debug mode (trace URLs) should be enabled for a specific chat.
        
        Args:
            chat_id: The Telegram chat ID to check
            
        Returns:
            True if trace URLs should be shown for this chat
        """
        # Show trace URLs if global debug mode is on OR if chat is in debug chat list
        return self.debug_mode or (chat_id in (self.telegram_debug_chat_id or []))

    def get_agent_instructions(self, mode: str = "normal") -> str:
        """Get the agent instructions for specified mode.
        
        Args:
            mode: Either "normal" or "deep" mode
            
        Returns:
            Instructions string for the specified mode
        """
        if mode not in ["normal", "deep"]:
            mode = "normal"
        return self._load_instructions_by_mode(mode)

    def _load_session_config(self):
        """Load session configuration from environment"""
        from src.core.session.types import SessionConfig
        return SessionConfig(
            max_items=int(os.getenv("SESSION_MAX_ITEMS", "50")),
            window_size=int(os.getenv("SESSION_WINDOW_SIZE", "20")),
            ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "168")),
            cache_enabled=os.getenv("SESSION_CACHE_ENABLED", "true").lower() == "true",
            cache_ttl_seconds=int(os.getenv("SESSION_CACHE_TTL", "300"))
        )

    def get_xmtp_config(self) -> Dict[str, Any]:
        """Get the XMTP configuration settings."""
        return {"agent_endpoint": self.xmtp_agent_endpoint}
