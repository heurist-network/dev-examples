#!/usr/bin/env python3

from typing import Dict, Optional, Any
from enum import Enum
import asyncio
import os
from datetime import datetime, timedelta
import logging

from .custom_session import CustomSession
from .types import SessionConfig
from .storage.base import StorageBackend
from .storage.sqlite_backend import SQLiteBackend

logger = logging.getLogger(__name__)


class SessionType(Enum):
    TELEGRAM_USER = "telegram_user"
    TELEGRAM_GROUP = "telegram_group"
    XMTP_CONVERSATION = "xmtp_conversation"


class SessionManager:
    """
    Centralized session management for all interfaces.
    """
    
    def __init__(self, config: Optional[SessionConfig] = None):
        self.config = config or SessionConfig()
        self.storage_backend = self._init_storage()
        self._sessions_cache: Dict[str, CustomSession] = {}
        self._cleanup_task = None
        
    def _init_storage(self) -> StorageBackend:
        """Initialize storage backend based on configuration"""
        storage_type = os.getenv("SESSION_STORAGE_TYPE", "sqlite")
        
        if storage_type == "sqlite":
            db_path = os.getenv("SESSION_DB_PATH", "data/sessions.db")
            return SQLiteBackend(db_path)
        elif storage_type == "redis":
            try:
                # Import here to avoid dependency if not using Redis
                from .storage.redis_backend import RedisBackend
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                return RedisBackend(redis_url)
            except ImportError:
                logger.error("Redis backend requested but redis dependencies not installed. Install with: pip install redis")
                logger.warning("Falling back to SQLite backend")
                db_path = os.getenv("SESSION_DB_PATH", "data/sessions.db")
                return SQLiteBackend(db_path)
        else:
            logger.warning(f"Unknown storage type '{storage_type}', falling back to SQLite")
            db_path = os.getenv("SESSION_DB_PATH", "data/sessions.db")
            return SQLiteBackend(db_path)
    
    def get_session_id(
        self, 
        session_type: SessionType,
        **kwargs
    ) -> str:
        """
        Generate consistent session IDs based on type.
        
        Examples:
        - Telegram user: "telegram_user_123456"
        - Telegram group: "telegram_group_-987654_user_123456"
        - XMTP: "xmtp_conversation_abc123"
        """
        if session_type == SessionType.TELEGRAM_USER:
            return f"telegram_user_{kwargs['user_id']}"
        elif session_type == SessionType.TELEGRAM_GROUP:
            return f"telegram_group_{kwargs['chat_id']}_user_{kwargs['user_id']}"
        elif session_type == SessionType.XMTP_CONVERSATION:
            return f"xmtp_conversation_{kwargs['conversation_id']}"
        else:
            raise ValueError(f"Unknown session type: {session_type}")
    
    async def get_or_create_session(
        self,
        session_id: str,
        config_override: Optional[SessionConfig] = None
    ) -> CustomSession:
        """
        Get existing session or create new one.
        """
        if session_id not in self._sessions_cache:
            config = config_override or self.config
            session = CustomSession(
                session_id=session_id,
                config=config,
                storage_backend=self.storage_backend
            )
            self._sessions_cache[session_id] = session
            logger.debug(f"Created new session: {session_id}")
        else:
            logger.debug(f"Using cached session: {session_id}")
        
        # Update last access
        session = self._sessions_cache[session_id]
        session._last_access = datetime.now()
        return session
    
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started session cleanup task")
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped session cleanup task")
    
    async def _cleanup_loop(self):
        """Periodically clean up expired sessions"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up expired sessions from storage
                cutoff = datetime.now() - timedelta(hours=self.config.ttl_hours)
                deleted = await self.storage_backend.cleanup_expired(cutoff)
                
                # Clear cache for expired sessions
                expired_sessions = []
                for session_id, session in self._sessions_cache.items():
                    if session._last_access < cutoff:
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    del self._sessions_cache[session_id]
                
                if deleted > 0 or expired_sessions:
                    logger.info(f"Cleaned up {deleted} expired storage items and {len(expired_sessions)} cached sessions")
                
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions"""
        return {
            "active_sessions": len(self._sessions_cache),
            "storage_backend": type(self.storage_backend).__name__,
            "config": {
                "max_items": self.config.max_items,
                "window_size": self.config.window_size,
                "ttl_hours": self.config.ttl_hours
            }
        }
    
    async def clear_all_sessions(self):
        """Clear all sessions (for testing/admin purposes)"""
        for session in self._sessions_cache.values():
            await session.clear_session()
        self._sessions_cache.clear()
        logger.warning("Cleared all sessions")


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(config: Optional[SessionConfig] = None) -> SessionManager:
    """Get or create the global session manager instance"""
    global _session_manager
    if _session_manager is None:
        # Use config from settings if none provided
        if config is None:
            try:
                from src.config.settings import Settings
                settings = Settings()
                config = settings.session_config
            except Exception as e:
                logger.warning(f"Could not load session config from settings: {e}")
                config = SessionConfig()  # Use defaults
        _session_manager = SessionManager(config)
    return _session_manager