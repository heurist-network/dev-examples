#!/usr/bin/env python3
"""
Storage adapter for scheduled tasks - supports SQLite (default) and JSON backends.
"""

import asyncio
import json
import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from .models import Task

logger = logging.getLogger(__name__)

# Determine which backend to use
_STORAGE_TYPE = os.getenv("TASKS_STORAGE_TYPE", "sqlite").lower()

# Import and initialize the appropriate backend
if _STORAGE_TYPE == "sqlite":
    from .sqlite_store import SQLiteTaskStore
    _store_instance = SQLiteTaskStore()
    logger.info("Using SQLite backend for task storage")
    
    # SQLite backend delegates
    async def add(task: Task) -> Task:
        return await _store_instance.add(task)
    
    async def get(task_id: str) -> Optional[Task]:
        return await _store_instance.get(task_id)
    
    async def remove(task_id: str) -> bool:
        return await _store_instance.remove(task_id)
    
    async def update(task: Task) -> Task:
        return await _store_instance.update(task)
    
    async def list_tasks(conversation_id: Optional[str] = None) -> List[Task]:
        return await _store_instance.list_tasks(conversation_id)
    
    async def save_all(tasks: List[Task]):
        """Not supported for SQLite - use update() for individual tasks"""
        logger.warning("save_all() called on SQLite backend - ignoring")
    
    async def get_default_timezone(conversation_id: str) -> Optional[str]:
        return await _store_instance.get_default_timezone(conversation_id)
    
    async def set_default_timezone(conversation_id: str, timezone: str) -> bool:
        return await _store_instance.set_default_timezone(conversation_id, timezone)

else:
    # JSON backend for compatibility
    logger.info("Using JSON backend for task storage")
    _STORE_PATH = os.getenv("TASKS_STORE_PATH", "./data/tasks.json")
    _lock = asyncio.Lock()
    
    async def _ensure_store_exists():
        """Ensure the store file and directory exist."""
        store_path = Path(_STORE_PATH)
        store_path.parent.mkdir(parents=True, exist_ok=True)
        if not store_path.exists():
            store_path.write_text(json.dumps({"tasks": []}, indent=2))
    
    async def _read() -> Dict[str, Any]:
        """Read tasks from storage."""
        await _ensure_store_exists()
        async with _lock:
            try:
                with open(_STORE_PATH, "r") as f:
                    data = json.load(f)
                    # Ensure the expected structure
                    if "tasks" not in data:
                        data = {"tasks": []}
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error reading tasks store: {e}")
                return {"tasks": []}
    
    async def _write(data: Dict[str, Any]):
        """Write tasks to storage."""
        await _ensure_store_exists()
        async with _lock:
            try:
                with open(_STORE_PATH, "w") as f:
                    json.dump(data, f, indent=2, default=str)
            except IOError as e:
                logger.error(f"Error writing tasks store: {e}")
                raise
    
    async def add(task: Task) -> Task:
        """Add a new task to storage."""
        data = await _read()
        data["tasks"].append(task.to_dict())
        await _write(data)
        logger.info(f"Added task {task.id} to store")
        return task
    
    async def get(task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        data = await _read()
        for task_data in data["tasks"]:
            if task_data.get("id") == task_id:
                return Task.from_dict(task_data)
        return None
    
    async def remove(task_id: str) -> bool:
        """Remove a task by ID."""
        data = await _read()
        original_count = len(data["tasks"])
        data["tasks"] = [t for t in data["tasks"] if t.get("id") != task_id]
        
        if len(data["tasks"]) < original_count:
            await _write(data)
            logger.info(f"Removed task {task_id} from store")
            return True
        return False
    
    async def update(task: Task) -> Task:
        """Update an existing task."""
        data = await _read()
        for i, task_data in enumerate(data["tasks"]):
            if task_data.get("id") == task.id:
                data["tasks"][i] = task.to_dict()
                await _write(data)
                logger.info(f"Updated task {task.id} in store")
                return task
        
        # If not found, add it
        return await add(task)
    
    async def list_tasks(conversation_id: Optional[str] = None) -> List[Task]:
        """List all tasks, optionally filtered by conversation ID."""
        data = await _read()
        tasks = []
        
        for task_data in data["tasks"]:
            try:
                task = Task.from_dict(task_data)
                if conversation_id is None or task.conversation_id == conversation_id:
                    tasks.append(task)
            except Exception as e:
                logger.error(f"Error loading task from store: {e}")
                continue
        
        return tasks
    
    async def save_all(tasks: List[Task]):
        """Save all tasks (replaces existing)."""
        data = {"tasks": [t.to_dict() for t in tasks]}
        await _write(data)
        logger.info(f"Saved {len(tasks)} tasks to store")
    
    # JSON backend doesn't support timezone preferences
    async def get_default_timezone(conversation_id: str) -> Optional[str]:
        """Not supported in JSON backend"""
        return None
    
    async def set_default_timezone(conversation_id: str, timezone: str) -> bool:
        """Not supported in JSON backend"""
        logger.warning("Timezone preferences not supported in JSON backend")
        return False


# Optional migration on startup for SQLite backend
if _STORAGE_TYPE == "sqlite" and os.getenv("TASKS_MIGRATE_FROM_JSON", "false").lower() == "true":
    json_path = os.getenv("TASKS_STORE_PATH", "./data/tasks.json")
    if os.path.exists(json_path):
        async def _migrate_on_first_use():
            """Migrate tasks from JSON to SQLite on first use."""
            try:
                count = await _store_instance.migrate_from_json(json_path)
                if count > 0:
                    logger.info(f"Successfully migrated {count} tasks from JSON to SQLite")
                    # Rename the JSON file to indicate migration
                    try:
                        migrated_path = f"{json_path}.migrated"
                        os.rename(json_path, migrated_path)
                        logger.info(f"Renamed {json_path} to {migrated_path}")
                    except Exception as e:
                        logger.warning(f"Could not rename migrated JSON file: {e}")
            except Exception as e:
                logger.error(f"Migration failed: {e}")
        
        # Create a task to run migration on first access
        _migration_task = None
        
        async def _ensure_migrated():
            global _migration_task
            if _migration_task is None:
                _migration_task = asyncio.create_task(_migrate_on_first_use())
                await _migration_task