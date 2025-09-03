#!/usr/bin/env python3
"""
SQLite-based storage for scheduled tasks with timezone preferences.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiosqlite

from .models import Task

logger = logging.getLogger(__name__)


class SQLiteTaskStore:
    """SQLite storage backend for scheduled tasks."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SQLite task store.
        
        Args:
            db_path: Path to SQLite database. Defaults to SESSION_DB_PATH or data/sessions.db
        """
        # Use TASKS_DB_PATH, fall back to SESSION_DB_PATH, then default
        if db_path is None:
            db_path = os.getenv("TASKS_DB_PATH")
            if not db_path:
                db_path = os.getenv("SESSION_DB_PATH", "data/sessions.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        logger.info(f"SQLite task store using database: {self.db_path}")
    
    async def _ensure_initialized(self):
        """Ensure database schema is initialized."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # Create scheduled_tasks table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    cron TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    created_by TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    meta TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_conversation 
                ON scheduled_tasks(conversation_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_enabled 
                ON scheduled_tasks(enabled)
            """)
            
            # Create timezone preferences table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_task_prefs (
                    conversation_id TEXT PRIMARY KEY,
                    timezone TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            await db.commit()
            logger.info("SQLite task store schema initialized")
        
        self._initialized = True
    
    async def add(self, task: Task) -> Task:
        """Add a new task to storage."""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Convert meta dict to JSON string
            meta_json = json.dumps(task.meta) if task.meta else "{}"
            
            await db.execute("""
                INSERT INTO scheduled_tasks 
                (id, name, prompt, cron, timezone, conversation_id, created_by, 
                 enabled, last_run_at, next_run_at, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.name, task.prompt, task.cron, task.timezone,
                task.conversation_id, task.created_by, 
                1 if task.enabled else 0,
                task.last_run_at, task.next_run_at, meta_json
            ))
            await db.commit()
            
        logger.info(f"Added task {task.id} to SQLite store")
        return task
    
    async def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    return self._row_to_task(row)
        
        return None
    
    async def remove(self, task_id: str) -> bool:
        """Remove a task by ID."""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM scheduled_tasks WHERE id = ?", (task_id,)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Removed task {task_id} from SQLite store")
                return True
        
        return False
    
    async def update(self, task: Task) -> Task:
        """Update an existing task."""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Convert meta dict to JSON string
            meta_json = json.dumps(task.meta) if task.meta else "{}"
            
            cursor = await db.execute("""
                UPDATE scheduled_tasks 
                SET name = ?, prompt = ?, cron = ?, timezone = ?, 
                    conversation_id = ?, created_by = ?, enabled = ?,
                    last_run_at = ?, next_run_at = ?, meta = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                task.name, task.prompt, task.cron, task.timezone,
                task.conversation_id, task.created_by,
                1 if task.enabled else 0,
                task.last_run_at, task.next_run_at, meta_json,
                task.id
            ))
            await db.commit()
            
            if cursor.rowcount == 0:
                # Task doesn't exist, add it instead
                return await self.add(task)
            
        logger.info(f"Updated task {task.id} in SQLite store")
        return task
    
    async def list_tasks(self, conversation_id: Optional[str] = None) -> List[Task]:
        """List all tasks, optionally filtered by conversation ID."""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if conversation_id:
                query = """
                    SELECT * FROM scheduled_tasks 
                    WHERE conversation_id = ? 
                    ORDER BY created_at DESC
                """
                params = (conversation_id,)
            else:
                query = "SELECT * FROM scheduled_tasks ORDER BY created_at DESC"
                params = ()
            
            tasks = []
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    task = self._row_to_task(row)
                    if task:
                        tasks.append(task)
            
        return tasks
    
    async def get_default_timezone(self, conversation_id: str) -> Optional[str]:
        """Get the default timezone for a conversation."""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT timezone FROM scheduled_task_prefs WHERE conversation_id = ?",
                (conversation_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row["timezone"]
        
        return None
    
    async def set_default_timezone(self, conversation_id: str, timezone: str) -> bool:
        """Set the default timezone for a conversation."""
        await self._ensure_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO scheduled_task_prefs 
                (conversation_id, timezone, updated_at)
                VALUES (?, ?, ?)
            """, (conversation_id, timezone, datetime.utcnow().isoformat()))
            await db.commit()
            
        logger.info(f"Set default timezone for {conversation_id} to {timezone}")
        return True
    
    async def migrate_from_json(self, json_path: str) -> int:
        """
        Migrate tasks from JSON file to SQLite.
        
        Args:
            json_path: Path to JSON file containing tasks
            
        Returns:
            Number of tasks migrated
        """
        if not Path(json_path).exists():
            logger.warning(f"JSON file not found for migration: {json_path}")
            return 0
        
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            
            tasks_data = data.get("tasks", [])
            migrated = 0
            
            for task_data in tasks_data:
                try:
                    task = Task.from_dict(task_data)
                    await self.add(task)
                    migrated += 1
                except Exception as e:
                    logger.error(f"Failed to migrate task: {e}")
            
            logger.info(f"Migrated {migrated} tasks from JSON to SQLite")
            return migrated
            
        except Exception as e:
            logger.error(f"Failed to read JSON file for migration: {e}")
            return 0
    
    def _row_to_task(self, row: aiosqlite.Row) -> Optional[Task]:
        """Convert a database row to a Task object."""
        try:
            # Parse meta JSON
            meta = {}
            if row["meta"]:
                try:
                    meta = json.loads(row["meta"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid meta JSON for task {row['id']}")
            
            return Task(
                id=row["id"],
                name=row["name"],
                prompt=row["prompt"],
                cron=row["cron"],
                timezone=row["timezone"],
                conversation_id=row["conversation_id"],
                created_by=row["created_by"],
                enabled=bool(row["enabled"]),
                last_run_at=row["last_run_at"],
                next_run_at=row["next_run_at"],
                meta=meta
            )
        except Exception as e:
            logger.error(f"Error converting row to Task: {e}")
            return None
