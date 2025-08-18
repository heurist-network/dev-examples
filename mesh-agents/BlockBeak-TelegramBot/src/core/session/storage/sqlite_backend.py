#!/usr/bin/env python3

import sqlite3
import json
import asyncio
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import aiosqlite
import logging

from .base import StorageBackend
from ..types import SessionItem

logger = logging.getLogger(__name__)


class SQLiteBackend(StorageBackend):
    """
    SQLite storage backend with async support.
    """
    
    def __init__(self, db_path: str = "data/sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                hash TEXT,
                compressed BOOLEAN DEFAULT 0,
                UNIQUE(session_id, hash)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_id 
            ON sessions(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON sessions(timestamp)
        """)
        conn.commit()
        conn.close()
        logger.info(f"SQLite database initialized at {self.db_path}")
    
    async def get_all_items(self, session_id: str) -> List[SessionItem]:
        """Retrieve all items for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT role, content, timestamp, 
                       metadata, hash, compressed
                FROM sessions
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,)
            )
            rows = await cursor.fetchall()
            
            items = []
            for row in rows:
                try:
                    content = json.loads(row[1]) if row[1].startswith(('{', '[')) else row[1]
                    metadata = json.loads(row[3]) if row[3] else {}
                    
                    item = SessionItem(
                        role=row[0],
                        content=content,
                        timestamp=datetime.fromisoformat(row[2]),
                        metadata=metadata,
                        hash=row[4],
                        compressed=bool(row[5])
                    )
                    items.append(item)
                except Exception as e:
                    logger.warning(f"Failed to parse session item: {e}")
                    continue
            
            return items
    
    async def add_items(self, session_id: str, items: List[SessionItem]) -> None:
        """Store new items for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            for item in items:
                try:
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO sessions 
                        (session_id, role, content, timestamp, metadata, hash, compressed)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session_id,
                            item.role,
                            json.dumps(item.content, default=str),
                            item.timestamp.isoformat(),
                            json.dumps(item.metadata),
                            item.hash,
                            item.compressed
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to add session item: {e}")
                    continue
            
            await db.commit()
            logger.debug(f"Added {len(items)} items to session {session_id}")
    
    async def pop_item(self, session_id: str) -> Optional[SessionItem]:
        """Remove and return the most recent item"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get the most recent item
            cursor = await db.execute(
                """
                SELECT id, role, content, timestamp, 
                       metadata, hash, compressed
                FROM sessions
                WHERE session_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            # Delete the item
            await db.execute(
                "DELETE FROM sessions WHERE id = ?",
                (row[0],)
            )
            await db.commit()
            
            # Return the item
            try:
                content = json.loads(row[2]) if row[2].startswith(('{', '[')) else row[2]
                metadata = json.loads(row[4]) if row[4] else {}
                
                return SessionItem(
                    role=row[1],
                    content=content,
                    timestamp=datetime.fromisoformat(row[3]),
                    metadata=metadata,
                    hash=row[5],
                    compressed=bool(row[6])
                )
            except Exception as e:
                logger.error(f"Failed to parse popped item: {e}")
                return None
    
    async def clear_session(self, session_id: str) -> None:
        """Clear all items for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            await db.commit()
            logger.info(f"Cleared session {session_id}")
    
    async def cleanup_expired(self, before: datetime) -> int:
        """Clean up expired sessions, return count of deleted items"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE timestamp < ?",
                (before.isoformat(),)
            )
            await db.commit()
            deleted_count = cursor.rowcount
            logger.info(f"Cleaned up {deleted_count} expired session items")
            return deleted_count