#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime


class StorageBackend(ABC):
    """Abstract base for session storage backends"""
    
    @abstractmethod
    async def get_all_items(self, session_id: str) -> List["SessionItem"]:
        """Retrieve all items for a session"""
        pass
    
    @abstractmethod
    async def add_items(self, session_id: str, items: List["SessionItem"]) -> None:
        """Store new items for a session"""
        pass
    
    @abstractmethod
    async def pop_item(self, session_id: str) -> Optional["SessionItem"]:
        """Remove and return the most recent item"""
        pass
    
    @abstractmethod
    async def clear_session(self, session_id: str) -> None:
        """Clear all items for a session"""
        pass
    
    @abstractmethod
    async def cleanup_expired(self, before: datetime) -> int:
        """Clean up expired sessions, return count of deleted items"""
        pass