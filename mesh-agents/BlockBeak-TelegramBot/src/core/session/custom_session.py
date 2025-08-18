#!/usr/bin/env python3

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .types import SessionConfig, SessionItem
from .storage.base import StorageBackend
from .storage.sqlite_backend import SQLiteBackend

logger = logging.getLogger(__name__)


class CustomSession:
    """
    Custom session implementation with:
    - Simple memory windowing
    - Input normalization
    """
    
    def __init__(
        self,
        session_id: str,
        config: Optional[SessionConfig] = None,
        storage_backend: Optional[StorageBackend] = None
    ):
        self.session_id = session_id
        self.config = config or SessionConfig()
        self.storage = storage_backend or SQLiteBackend()
        self._cache = {}
        self._last_access = datetime.now()
        
    async def get_items(self, limit: Optional[int] = None) -> List[dict]:
        """
        Retrieve recent conversation history.
        
        Strategy:
        1. Fetch items from storage
        2. Return most recent items within window size
        """
        # Step 1: Fetch all items from storage
        all_items = await self.storage.get_all_items(self.session_id)
        
        if not all_items:
            return []
        
        # Filter out any empty content items that might have been stored previously
        all_items = [
            item for item in all_items 
            if item.content and (not isinstance(item.content, str) or item.content.strip())
        ]
        
        # Step 2: Simple windowing - get recent items
        window_size = limit or self.config.window_size
        
        # Take the most recent items within window size
        final_items = all_items[-window_size:] if len(all_items) > window_size else all_items
        
        # Convert to simple format
        return self._normalize_items(final_items)

    async def add_items(self, items: List[dict]) -> None:
        """
        Add items with metadata enrichment.
        """
        if not items:
            return
            
        session_items = []
        for item in items:
            # Skip empty content items to prevent pollution of conversation history
            content = item.get("content", "")
            if not content or (isinstance(content, str) and not content.strip()):
                logger.debug(f"Skipping empty {item.get('role', 'unknown')} message")
                continue
                
            # Convert to SessionItem
            session_item = SessionItem(
                role=item.get("role", "user"),
                content=content,
                timestamp=datetime.now(),
                metadata={"original_item": item}
            )
            session_items.append(session_item)
        
        # Store in backend (only if we have valid items)
        if session_items:
            await self.storage.add_items(self.session_id, session_items)
            logger.debug(f"Added {len(session_items)} valid items to session {self.session_id}")
        else:
            logger.debug(f"No valid items to add to session {self.session_id} (all were empty)")
        
        # Update last access
        self._last_access = datetime.now()

    async def pop_item(self) -> Optional[dict]:
        """Remove and return the most recent item."""
        item = await self.storage.pop_item(self.session_id)
        if item:
            return {
                "role": item.role,
                "content": item.content
            }
        return None

    async def clear_session(self) -> None:
        """Clear all items for this session."""
        await self.storage.clear_session(self.session_id)
        self._cache.clear()
        logger.info(f"Cleared session {self.session_id}")







    def _normalize_items(self, items: List[SessionItem]) -> List[dict]:
        """
        Normalize items for the agent, adding timestamp nonces to prevent caching.
        """
        normalized = []
        for item in items:
            item_dict = {
                "role": item.role,
                "content": item.content
            }
            
            # Add invisible timestamp nonce for user inputs to prevent duplicate suppression
            # This ensures tools fire correctly even on repeated identical prompts
            if item.role == "user" and isinstance(item_dict["content"], str):
                # Append invisible unicode character with timestamp
                nonce = f"\u200B{item.timestamp.isoformat()}"
                item_dict["content"] += nonce
            
            normalized.append(item_dict)
        
        return normalized