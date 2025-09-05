#!/usr/bin/env python3
"""
Task scheduler using APScheduler.
"""

import asyncio
import os
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

from src.core.agent import create_agent_manager
from src.core.session.manager import get_session_manager, SessionType
from .models import Task
from . import store
from .notifiers import StdoutNotifier, XMTPNotifier

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Manages scheduled tasks using APScheduler."""
    
    def __init__(self, default_tz: str = "UTC", use_xmtp_notifier: bool = False):
        """
        Initialize the task scheduler.
        
        Args:
            default_tz: Default timezone for tasks
            use_xmtp_notifier: Whether to use XMTP notifier (Phase 2) or stdout (MVP)
        """
        self.default_tz = default_tz
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo(default_tz))
        
        # Select notifier based on configuration
        if use_xmtp_notifier:
            self.notifier = XMTPNotifier()
            logger.info("Using XMTP notifier for scheduled tasks")
        else:
            self.notifier = StdoutNotifier()
            logger.info("Using stdout notifier for scheduled tasks (MVP)")
        
        self._started = False
        self._agent_managers: Dict[str, Any] = {}  # Cache per conversation
        self._execution_locks: Dict[str, asyncio.Lock] = {}  # Locks per conversation
    
    async def start(self):
        """Start the scheduler and load existing tasks."""
        if self._started:
            logger.warning("Scheduler already started")
            return
        
        self.scheduler.start()
        self._started = True
        logger.info("Task scheduler started")
        
        # Load and schedule existing tasks
        tasks = await store.list_tasks()
        scheduled_count = 0
        
        for task in tasks:
            if task.enabled:
                try:
                    self._schedule_task(task)
                    scheduled_count += 1
                except Exception as e:
                    logger.error(f"Failed to schedule task {task.id}: {e}")
                    # Disable invalid tasks
                    task.enabled = False
                    task.meta["error"] = str(e)
                    await store.update(task)
        
        logger.info(f"Loaded {len(tasks)} tasks, scheduled {scheduled_count}")
    
    async def shutdown(self):
        """Shutdown the scheduler."""
        if not self._started:
            return
        
        self.scheduler.shutdown(wait=False)
        self._started = False
        self._agent_managers.clear()
        logger.info("Task scheduler shut down")
    
    def _schedule_task(self, task: Task):
        """Schedule a task with APScheduler."""
        try:
            # Parse and validate the cron expression
            trigger = CronTrigger.from_crontab(
                task.cron, 
                timezone=ZoneInfo(task.timezone)
            )
            
            # Add or update the job
            self.scheduler.add_job(
                self._run_task,
                trigger=trigger,
                args=[task.id],
                id=task.id,
                name=f"{task.name} ({task.conversation_id})",
                replace_existing=True,
                misfire_grace_time=300  # 5 minutes grace period
            )
            
            # Calculate next run time
            next_run = self.scheduler.get_job(task.id).next_run_time
            if next_run:
                task.next_run_at = next_run.isoformat()
            
            logger.info(f"Scheduled task {task.id}: {task.cron} in {task.timezone}")
            
        except Exception as e:
            logger.error(f"Failed to schedule task {task.id}: {e}")
            raise
    
    async def add_task(self, task: Task) -> Task:
        """Add and schedule a new task."""
        # Validate before saving
        try:
            CronTrigger.from_crontab(task.cron, timezone=ZoneInfo(task.timezone))
        except Exception as e:
            raise ValueError(f"Invalid cron expression or timezone: {e}")
        
        # Save to store
        await store.add(task)
        
        # Schedule if enabled
        if task.enabled:
            self._schedule_task(task)
        
        return task
    
    async def remove_task(self, task_id: str) -> bool:
        """Remove a task from scheduler and store."""
        # Get task info before removing (for cleanup)
        task = await store.get(task_id)
        
        # Remove from scheduler
        try:
            self.scheduler.remove_job(task_id)
            logger.info(f"Removed task {task_id} from scheduler")
        except JobLookupError:
            logger.warning(f"Task {task_id} not found in scheduler")
        
        # Remove from store
        removed = await store.remove(task_id)
        
        # Clean up agent manager cache if exists
        if task and task.conversation_id in self._agent_managers:
            del self._agent_managers[task.conversation_id]
        
        return removed
    
    async def update_task(self, task: Task) -> Task:
        """Update an existing task."""
        # Update in store
        await store.update(task)
        
        # Reschedule if enabled
        if task.enabled:
            self._schedule_task(task)
        else:
            # Remove from scheduler if disabled
            try:
                self.scheduler.remove_job(task.id)
            except JobLookupError:
                pass
        
        return task
    
    async def list_tasks(self, conversation_id: Optional[str] = None) -> List[Task]:
        """List all tasks, optionally filtered by conversation."""
        return await store.list_tasks(conversation_id)
    
    async def run_now(self, task_id: str):
        """Execute a task immediately (ad-hoc run)."""
        logger.info(f"Running task {task_id} immediately")
        await self._run_task(task_id)
    
    def _get_or_create_agent_manager(self, conversation_id: str):
        """Get or create an agent manager for a conversation."""
        if conversation_id not in self._agent_managers:
            logger.info(f"Creating agent manager for scheduled task in conversation {conversation_id}")
            
            # Create conversation-scoped tools for scheduled tasks (same as XMTP API)
            from .tools import (
                make_create_task_tool,
                make_list_tasks_tool,
                make_delete_task_tool,
                make_run_task_now_tool,
                make_toggle_task_tool,
                make_set_default_timezone_tool,
                make_get_default_timezone_tool,
            )
            
            extra_tools = [
                make_create_task_tool(conversation_id),
                make_list_tasks_tool(conversation_id),
                make_delete_task_tool(),
                make_run_task_now_tool(),
                make_toggle_task_tool(),
                make_set_default_timezone_tool(conversation_id),
                make_get_default_timezone_tool(conversation_id),
            ]
            
            # Get default timezone if exists (we'll skip this for now in scheduler context)
            # The timezone is already part of each task, so we don't need conversation default here
            default_tz = None
            
            # Build context with scheduling info
            scheduling_context = {
                "xmtp_conversation_id": conversation_id,
                "scheduling_enabled": True,
                "is_scheduled_execution": True,  # Mark this as a scheduled execution
            }
            
            if default_tz:
                scheduling_context["default_timezone"] = default_tz
            
            self._agent_managers[conversation_id] = create_agent_manager(
                extra_tools=extra_tools,
                context=scheduling_context
            )
        return self._agent_managers[conversation_id]
    
    async def _run_task(self, task_id: str):
        """Execute a scheduled task."""
        logger.info(f"Executing scheduled task {task_id}")
        
        # Add a small random delay to prevent exact simultaneous execution
        import random
        await asyncio.sleep(random.uniform(0.1, 1.0))
        
        try:
            # Load task from store
            task = await store.get(task_id)
            if not task:
                logger.error(f"Task {task_id} not found in store")
                return
            
            if not task.enabled:
                logger.info(f"Task {task_id} is disabled, skipping execution")
                return
            
            # Get or create a lock for this conversation
            if task.conversation_id not in self._execution_locks:
                self._execution_locks[task.conversation_id] = asyncio.Lock()
            
            # Acquire lock to prevent concurrent executions for same conversation
            async with self._execution_locks[task.conversation_id]:
                await self._execute_task_with_lock(task_id, task)
        
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}", exc_info=True)
            
            # Try to notify about the error
            try:
                error_message = f"❌ Task execution failed: {str(e)}"
                task = await store.get(task_id)
                if task:
                    await self.notifier.notify(task, error_message, None)
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
    
    async def _execute_task_with_lock(self, task_id: str, task: Task):
        """Execute task with conversation lock held."""
        # Get session for the conversation
        session_manager = get_session_manager()
        session_id = session_manager.get_session_id(
            SessionType.XMTP_CONVERSATION,
            conversation_id=task.conversation_id
        )
        session = await session_manager.get_or_create_session(session_id)
        
        # Get or create agent manager for this conversation
        agent_manager = self._get_or_create_agent_manager(task.conversation_id)
        
        # Execute the task prompt
        logger.info(f"Processing prompt for task {task_id}: {task.prompt[:50]}...")
        
        # Modify the prompt to make it clear this is an execution, not a request to schedule
        execution_prompt = f"[SCHEDULED TASK EXECUTION - DO NOT CREATE NEW TASKS]\n\n{task.prompt}\n\nNote: This is an automated execution of an existing scheduled task. Simply perform the requested action without creating any new scheduled tasks."
        
        result = await agent_manager.process_message(
            message=execution_prompt,
            streaming=False,
            session=session,  # Session is handled internally, not passed to Runner.run
            context_update={
                "scheduled_task_execution": True,  # Changed from scheduled_task to be clearer
                "is_scheduled_execution": True,
                "task_id": task.id,
                "task_name": task.name,
                "do_not_create_tasks": True  # Explicit flag
            }
        )
        
        # Extract output and trace URL
        output = result.get("output", "")
        trace_url = result.get("trace_url")
        
        # Send notification
        await self.notifier.notify(task, output, trace_url)
        
        # Check if task still exists before updating (might have been deleted during execution)
        if await store.get(task_id) is None:
            logger.warning(f"Task {task_id} was deleted during execution - skipping metadata update")
            return
        
        # Update task metadata
        task.last_run_at = datetime.utcnow().isoformat()
        
        # Get next run time from scheduler
        job = self.scheduler.get_job(task_id)
        if job and job.next_run_time:
            task.next_run_at = job.next_run_time.isoformat()
        
        # Save updated task
        await store.update(task)
        
        logger.info(f"Task {task_id} executed successfully")


# Global scheduler instance
task_scheduler: Optional[TaskScheduler] = None


def get_task_scheduler(use_xmtp_notifier: bool = False) -> TaskScheduler:
    """Get or create the global task scheduler instance."""
    global task_scheduler
    if task_scheduler is None:
        default_tz = os.getenv("SCHED_DEFAULT_TZ", "UTC")
        task_scheduler = TaskScheduler(default_tz=default_tz, use_xmtp_notifier=use_xmtp_notifier)
    return task_scheduler
