#!/usr/bin/env python3
"""
Agent function tools for scheduled task management.
These tools are bound per-conversation for isolation.
"""

import uuid
import logging
import os
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo

from agents import function_tool
from apscheduler.triggers.cron import CronTrigger

from .models import Task
from .scheduler import get_task_scheduler
from . import store

logger = logging.getLogger(__name__)


def canonicalize_timezone(tz_input: str) -> Tuple[Optional[str], Optional[str], Optional[List[str]]]:
    """
    Canonicalize timezone input to IANA timezone identifier.
    
    Args:
        tz_input: User-provided timezone string (abbreviation, city, or IANA)
        
    Returns:
        Tuple of (iana_tz, abbrev_used, suggestions)
        - iana_tz: Canonical IANA timezone or None if invalid/ambiguous
        - abbrev_used: The abbreviation that was mapped (if any)
        - suggestions: List of suggestions if ambiguous
    """
    if not tz_input:
        return None, None, ["UTC", "America/New_York", "America/Los_Angeles", "Europe/London"]
    
    tz_input = tz_input.strip()
    
    # Common timezone mappings (abbreviation/nickname -> IANA)
    tz_mappings = {
        # US timezones
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
        "PT": "America/Los_Angeles",
        "Pacific": "America/Los_Angeles",
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "ET": "America/New_York",
        "Eastern": "America/New_York",
        "CST": None,  # Ambiguous - could be US Central or China Standard
        "CDT": "America/Chicago",
        "CT": "America/Chicago",
        "Central": "America/Chicago",
        "MST": "America/Denver",
        "MDT": "America/Denver",
        "MT": "America/Denver",
        "Mountain": "America/Denver",
        
        # European timezones
        "GMT": "Europe/London",
        "BST": "Europe/London",
        "CET": "Europe/Paris",
        "CEST": "Europe/Paris",
        "EET": "Europe/Athens",
        "EEST": "Europe/Athens",
        
        # Asian timezones
        "JST": "Asia/Tokyo",
        "KST": "Asia/Seoul",
        "IST": None,  # Ambiguous - could be India or Israel
        "SGT": "Asia/Singapore",
        "HKT": "Asia/Hong_Kong",
        "AEST": "Australia/Sydney",
        "AEDT": "Australia/Sydney",
        
        # City names (common ones)
        "New York": "America/New_York",
        "Los Angeles": "America/Los_Angeles",
        "Chicago": "America/Chicago",
        "London": "Europe/London",
        "Paris": "Europe/Paris",
        "Berlin": "Europe/Berlin",
        "Tokyo": "Asia/Tokyo",
        "Shanghai": "Asia/Shanghai",
        "Beijing": "Asia/Shanghai",
        "Hong Kong": "Asia/Hong_Kong",
        "Singapore": "Asia/Singapore",
        "Sydney": "Australia/Sydney",
        "Mumbai": "Asia/Kolkata",
        "Delhi": "Asia/Kolkata",
    }
    
    # Check case-insensitive mapping
    tz_upper = tz_input.upper()
    for key, value in tz_mappings.items():
        if key.upper() == tz_upper:
            if value is None:
                # Ambiguous abbreviation
                if tz_upper == "CST":
                    return None, "CST", [
                        "America/Chicago (US Central)",
                        "Asia/Shanghai (China Standard)"
                    ]
                elif tz_upper == "IST":
                    return None, "IST", [
                        "Asia/Kolkata (India Standard)",
                        "Asia/Jerusalem (Israel Standard)"
                    ]
            return value, key if key != value else None, None
    
    # Try as direct IANA timezone
    try:
        # Validate with ZoneInfo
        test_tz = ZoneInfo(tz_input)
        return tz_input, None, None
    except Exception:
        pass
    
    # If not found, provide suggestions
    suggestions = [
        "UTC",
        "America/New_York (Eastern Time)",
        "America/Los_Angeles (Pacific Time)",
        "America/Chicago (Central Time)",
        "Europe/London (British Time)",
        "Asia/Tokyo (Japan Time)",
        "Asia/Shanghai (China Time)"
    ]
    
    return None, None, suggestions


def make_create_task_tool(conversation_id: str):
    """
    Factory function to create a conversation-scoped task creation tool.
    """
    
    @function_tool
    async def create_scheduled_task(
        prompt: str,
        cron: str,
        timezone: Optional[str] = None,
        name: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new scheduled task.
        
        Args:
            prompt: The message/prompt to execute at scheduled times
            cron: Cron expression (e.g., "0 21 * * *" for 9pm daily)
            timezone: IANA timezone (e.g., "America/Los_Angeles", "UTC") or common abbreviation
            name: Optional friendly name for the task
            created_by: Optional identifier of who created the task
            
        Returns:
            Dictionary with task details or error information
        """
        try:
            # Check if we're in a scheduled task execution context
            # We'll check for a marker in the prompt itself since we can't access context directly
            if "[SCHEDULED TASK EXECUTION" in prompt or "DO NOT CREATE NEW TASKS" in prompt:
                logger.warning(f"Attempted to create task during scheduled execution: {prompt[:50]}...")
                return {
                    "ok": False,
                    "error": "Cannot create new tasks during scheduled task execution",
                    "hint": "This is an automated task execution. New tasks should be created through regular conversations."
                }
            
            # Legacy check for scheduled execution (can be removed once context is reliable)
            import asyncio
            try:
                # Try to get the current event loop's context
                loop = asyncio.get_running_loop()
                # This is a hack to check if we're in scheduled execution
                # In production, this should be passed properly through context
                if hasattr(loop, '_scheduled_execution') or os.getenv('SCHEDULED_EXECUTION') == 'true':
                    return {
                        "ok": False,
                        "error": "Cannot create new scheduled tasks during task execution.",
                        "hint": "This is an automated task execution. The task is already scheduled."
                    }
            except:
                pass  # Not in async context or no loop
            # Get default timezone if not provided
            if not timezone:
                default_tz = await store.get_default_timezone(conversation_id)
                if default_tz:
                    timezone = default_tz
                    logger.info(f"Using conversation default timezone: {timezone}")
                else:
                    return {
                        "ok": False,
                        "error": "No timezone specified and no default timezone set.",
                        "hint": "Please specify a timezone (e.g., 'America/New_York', 'UTC') or set a default timezone first using set_default_timezone.",
                        "suggestions": [
                            "America/New_York (Eastern Time)",
                            "America/Los_Angeles (Pacific Time)",
                            "America/Chicago (Central Time)",
                            "Europe/London",
                            "Asia/Tokyo",
                            "UTC"
                        ]
                    }
            
            # Canonicalize timezone
            iana_tz, abbrev_used, suggestions = canonicalize_timezone(timezone)
            if not iana_tz:
                error_msg = f"Invalid or ambiguous timezone: '{timezone}'."
                if abbrev_used:
                    error_msg = f"Ambiguous timezone abbreviation '{abbrev_used}'. Please specify by city or full timezone."
                return {
                    "ok": False,
                    "error": error_msg,
                    "suggestions": suggestions or []
                }
            
            timezone = iana_tz  # Use canonicalized timezone
            # Validate cron expression and timezone
            try:
                CronTrigger.from_crontab(cron, timezone=ZoneInfo(timezone))
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"Invalid cron expression or timezone: {str(e)}",
                    "hint": "Cron format: 'minute hour day month weekday'. Example: '0 21 * * *' for 9pm daily."
                }
            
            # Check for duplicate tasks
            existing_tasks = await store.list_tasks(conversation_id)
            
            # Check task limit per conversation
            max_tasks = int(os.getenv("MAX_TASKS_PER_CONVERSATION", "10"))
            if len(existing_tasks) >= max_tasks:
                return {
                    "ok": False,
                    "error": f"Task limit reached. Maximum {max_tasks} tasks per conversation.",
                    "hint": "Delete an existing task to create a new one."
                }
            
            # Create the task
            task = Task(
                id=str(uuid.uuid4()),
                name=name or f"Task {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                prompt=prompt,
                cron=cron,
                timezone=timezone,
                conversation_id=conversation_id,
                created_by=created_by,
                enabled=True,
                meta={
                    "created_at": datetime.utcnow().isoformat(),
                    "timezone_input": abbrev_used if abbrev_used else timezone
                }
            )
            
            # Add to scheduler
            scheduler = get_task_scheduler()
            await scheduler.add_task(task)
            
            # Calculate next run time for user feedback
            trigger = CronTrigger.from_crontab(cron, timezone=ZoneInfo(timezone))
            next_run = trigger.get_next_fire_time(None, datetime.now(ZoneInfo(timezone or "UTC")))
            next_run_str = next_run.strftime("%Y-%m-%d %H:%M %Z") if next_run else "Unknown"
            
            logger.info(f"Created scheduled task {task.id} for conversation {conversation_id}")
            
            return {
                "ok": True,
                "taskId": task.id,
                "name": task.name,
                "cron": task.cron,
                "timezone": task.timezone,
                "nextRun": next_run_str,
                "message": f"Task '{task.name}' scheduled successfully. Next run: {next_run_str}"
            }
            
        except Exception as e:
            logger.error(f"Error creating scheduled task: {e}", exc_info=True)
            return {
                "ok": False,
                "error": f"Failed to create task: {str(e)}"
            }
    
    return create_scheduled_task


def make_list_tasks_tool(conversation_id: str):
    """
    Factory function to create a conversation-scoped task listing tool.
    """
    
    @function_tool
    async def list_scheduled_tasks(enabled_only: Optional[bool] = None) -> Dict[str, Any]:
        """
        List all scheduled tasks for this conversation.
        
        Args:
            enabled_only: If True, only show enabled tasks. If False, only disabled. If None, show all.
        
        Returns:
            Dictionary with list of tasks or error information
        """
        try:
            tasks = await store.list_tasks(conversation_id)
            
            # Filter by enabled status if requested
            if enabled_only is not None:
                tasks = [t for t in tasks if t.enabled == enabled_only]
            
            # Get conversation's default timezone for local time display
            default_tz = await store.get_default_timezone(conversation_id)
            
            task_list = []
            for task in tasks:
                task_info = {
                    "id": task.id,
                    "name": task.name,
                    "prompt": task.prompt[:50] + "..." if len(task.prompt) > 50 else task.prompt,
                    "cron": task.cron,
                    "timezone": task.timezone,
                    "enabled": task.enabled,
                    "lastRun": task.last_run_at,
                    "nextRunUtc": task.next_run_at,
                    "createdAt": task.meta.get("created_at") if task.meta else None
                }
                
                # Add local time if we have a default timezone and it's different from task timezone
                if default_tz and task.next_run_at:
                    try:
                        # Parse UTC time and convert to local
                        from datetime import datetime
                        next_utc = datetime.fromisoformat(task.next_run_at.replace('Z', '+00:00'))
                        local_tz = ZoneInfo(default_tz)
                        next_local = next_utc.astimezone(local_tz)
                        task_info["nextRunLocal"] = next_local.strftime("%Y-%m-%d %H:%M %Z")
                    except Exception as e:
                        logger.debug(f"Could not convert time to local: {e}")
                
                task_list.append(task_info)
            
            return {
                "ok": True,
                "tasks": task_list,
                "count": len(task_list),
                "message": f"Found {len(task_list)} scheduled task(s)"
            }
            
        except Exception as e:
            logger.error(f"Error listing tasks: {e}", exc_info=True)
            return {
                "ok": False,
                "error": f"Failed to list tasks: {str(e)}"
            }
    
    return list_scheduled_tasks


def make_delete_task_tool():
    """
    Factory function to create a task deletion tool.
    """
    
    @function_tool
    async def delete_scheduled_task(task_id: str) -> Dict[str, Any]:
        """
        Delete a scheduled task.
        
        Args:
            task_id: The ID of the task to delete
            
        Returns:
            Dictionary with deletion status
        """
        try:
            # Check if task exists
            task = await store.get(task_id)
            if not task:
                return {
                    "ok": False,
                    "error": f"Task with ID '{task_id}' not found"
                }
            
            # Remove from scheduler
            scheduler = get_task_scheduler()
            removed = await scheduler.remove_task(task_id)
            
            if removed:
                logger.info(f"Deleted task {task_id}")
                return {
                    "ok": True,
                    "message": f"Task '{task.name}' deleted successfully"
                }
            else:
                return {
                    "ok": False,
                    "error": "Task not found in scheduler"
                }
                
        except Exception as e:
            logger.error(f"Error deleting task: {e}", exc_info=True)
            return {
                "ok": False,
                "error": f"Failed to delete task: {str(e)}"
            }
    
    return delete_scheduled_task


def make_run_task_now_tool():
    """
    Factory function to create a task immediate execution tool.
    """
    
    @function_tool
    async def run_task_now(task_id: str) -> Dict[str, Any]:
        """
        Execute a scheduled task immediately (ad-hoc run).
        
        Args:
            task_id: The ID of the task to run
            
        Returns:
            Dictionary with execution status
        """
        try:
            # Check if task exists
            task = await store.get(task_id)
            if not task:
                return {
                    "ok": False,
                    "error": f"Task with ID '{task_id}' not found"
                }
            
            # Run the task
            scheduler = get_task_scheduler()
            await scheduler.run_now(task_id)
            
            logger.info(f"Triggered immediate execution of task {task_id}")
            
            return {
                "ok": True,
                "message": f"Task '{task.name}' is being executed. Results will be delivered shortly."
            }
            
        except Exception as e:
            logger.error(f"Error running task immediately: {e}", exc_info=True)
            return {
                "ok": False,
                "error": f"Failed to run task: {str(e)}"
            }
    
    return run_task_now


def make_toggle_task_tool():
    """
    Factory function to create a task enable/disable tool.
    """
    
    @function_tool
    async def toggle_scheduled_task(task_id: str, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable a scheduled task.
        
        Args:
            task_id: The ID of the task to toggle
            enabled: True to enable, False to disable
            
        Returns:
            Dictionary with toggle status
        """
        try:
            # Get the task
            task = await store.get(task_id)
            if not task:
                return {
                    "ok": False,
                    "error": f"Task with ID '{task_id}' not found"
                }
            
            # Update enabled status
            task.enabled = enabled
            
            # Update in scheduler
            scheduler = get_task_scheduler()
            await scheduler.update_task(task)
            
            status = "enabled" if enabled else "disabled"
            logger.info(f"Task {task_id} {status}")
            
            return {
                "ok": True,
                "message": f"Task '{task.name}' has been {status}"
            }
            
        except Exception as e:
            logger.error(f"Error toggling task: {e}", exc_info=True)
            return {
                "ok": False,
                "error": f"Failed to toggle task: {str(e)}"
            }
    
    return toggle_scheduled_task


# Helper functions for natural language to cron conversion hints
def get_cron_examples() -> str:
    """Get helpful cron expression examples."""
    return """
Common cron expressions:
- "0 9 * * *" = Every day at 9:00 AM
- "0 21 * * *" = Every day at 9:00 PM
- "0 */4 * * *" = Every 4 hours
- "0 9 * * 1-5" = Weekdays at 9:00 AM
- "0 10 * * 1" = Every Monday at 10:00 AM
- "*/30 * * * *" = Every 30 minutes

Format: minute hour day month weekday
"""


def get_timezone_examples() -> str:
    """Get helpful timezone examples."""
    return """
Common timezones:
- "UTC" = Coordinated Universal Time
- "America/New_York" = Eastern Time
- "America/Los_Angeles" = Pacific Time
- "Europe/London" = British Time
- "Asia/Tokyo" = Japan Time
- "Asia/Shanghai" = China Time
"""


def make_set_default_timezone_tool(conversation_id: str):
    """
    Factory function to create a tool for setting default timezone.
    """
    
    @function_tool
    async def set_default_timezone(timezone: str) -> Dict[str, Any]:
        """
        Set the default timezone for this conversation.
        
        Args:
            timezone: IANA timezone (e.g., "America/New_York") or common abbreviation
            
        Returns:
            Dictionary with success status
        """
        try:
            # Canonicalize timezone
            iana_tz, abbrev_used, suggestions = canonicalize_timezone(timezone)
            if not iana_tz:
                error_msg = f"Invalid or ambiguous timezone: '{timezone}'."
                if abbrev_used:
                    error_msg = f"Ambiguous timezone abbreviation '{abbrev_used}'. Please specify by city or full timezone."
                return {
                    "ok": False,
                    "error": error_msg,
                    "suggestions": suggestions or []
                }
            
            # Validate with ZoneInfo
            try:
                ZoneInfo(iana_tz)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"Invalid timezone: {str(e)}"
                }
            
            # Save preference
            success = await store.set_default_timezone(conversation_id, iana_tz)
            
            if success:
                logger.info(f"Set default timezone for {conversation_id} to {iana_tz}")
                return {
                    "ok": True,
                    "timezone": iana_tz,
                    "message": f"Default timezone set to {iana_tz}. All future scheduled tasks will use this timezone unless specified otherwise."
                }
            else:
                return {
                    "ok": False,
                    "error": "Failed to save timezone preference"
                }
                
        except Exception as e:
            logger.error(f"Error setting default timezone: {e}", exc_info=True)
            return {
                "ok": False,
                "error": f"Failed to set timezone: {str(e)}"
            }
    
    return set_default_timezone


def make_get_default_timezone_tool(conversation_id: str):
    """
    Factory function to create a tool for getting default timezone.
    """
    
    @function_tool
    async def get_default_timezone() -> Dict[str, Any]:
        """
        Get the default timezone for this conversation.
        
        Returns:
            Dictionary with timezone information
        """
        try:
            timezone = await store.get_default_timezone(conversation_id)
            
            if timezone:
                # Get current time in that timezone
                try:
                    from datetime import datetime
                    tz = ZoneInfo(timezone)
                    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")
                    
                    return {
                        "ok": True,
                        "timezone": timezone,
                        "currentTime": current_time,
                        "message": f"Default timezone is {timezone}. Current time: {current_time}"
                    }
                except Exception as e:
                    logger.debug(f"Could not get current time: {e}")
                    return {
                        "ok": True,
                        "timezone": timezone,
                        "message": f"Default timezone is {timezone}"
                    }
            else:
                return {
                    "ok": True,
                    "timezone": None,
                    "message": "No default timezone set. Tasks will require timezone to be specified.",
                    "suggestions": [
                        "America/New_York (Eastern Time)",
                        "America/Los_Angeles (Pacific Time)",
                        "America/Chicago (Central Time)",
                        "Europe/London",
                        "Asia/Tokyo",
                        "UTC"
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error getting default timezone: {e}", exc_info=True)
            return {
                "ok": False,
                "error": f"Failed to get timezone: {str(e)}"
            }
    
    return get_default_timezone


