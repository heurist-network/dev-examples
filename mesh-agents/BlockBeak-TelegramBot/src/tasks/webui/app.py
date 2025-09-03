#!/usr/bin/env python3
"""
FastAPI app for Tasks WebUI.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, HTTPException, Depends, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

from src.tasks import store
from src.tasks.models import Task
from src.tasks.scheduler import get_task_scheduler
from src.tasks.tools import canonicalize_timezone
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Configuration from environment
WEBUI_ENABLED = os.getenv("TASKS_WEBUI_ENABLED", "false").lower() == "true"
WEBUI_HOST = os.getenv("TASKS_WEBUI_HOST", "127.0.0.1")
WEBUI_PORT = int(os.getenv("TASKS_WEBUI_PORT", "8789"))
WEBUI_BASE_PATH = os.getenv("TASKS_WEBUI_BASE_PATH", "/")
ADMIN_TOKEN = os.getenv("TASKS_WEBUI_ADMIN_TOKEN", "")
READONLY = os.getenv("TASKS_WEBUI_READONLY", "true").lower() == "true" if not ADMIN_TOKEN else False

# Template and static paths
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


# Pydantic models for API requests
class ToggleTaskRequest(BaseModel):
    enabled: bool


class UpdateTaskRequest(BaseModel):
    name: Optional[str] = None
    cron: Optional[str] = None
    timezone: Optional[str] = None


class SetTimezoneRequest(BaseModel):
    timezone: str


def verify_admin_token(x_admin_token: Optional[str] = Header(None)) -> bool:
    """Verify admin token for protected endpoints."""
    if READONLY:
        raise HTTPException(status_code=403, detail="WebUI is in read-only mode")
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token not configured")
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    app = FastAPI(
        title="Tasks WebUI",
        description="Web interface for managing scheduled tasks",
        version="1.0.0",
        root_path=WEBUI_BASE_PATH if WEBUI_BASE_PATH != "/" else "",
    )

    # Setup templates and static files
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.on_event("startup")
    async def startup_event():
        """Start the task scheduler on app startup."""
        scheduler = get_task_scheduler()
        if not scheduler._started:
            await scheduler.start()
            logger.info("Task scheduler started from WebUI")

    # --- HTML Pages ---

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Dashboard page with stats."""
        tasks = await store.list_tasks()
        
        # Calculate stats
        total_tasks = len(tasks)
        enabled_tasks = sum(1 for t in tasks if t.enabled)
        disabled_tasks = total_tasks - enabled_tasks
        conversations = len(set(t.conversation_id for t in tasks))
        
        # Find upcoming tasks (next 5)
        upcoming = []
        for task in tasks:
            if task.enabled and task.next_run_at:
                upcoming.append({
                    "name": task.name,
                    "next_run": task.next_run_at,
                    "conversation": task.conversation_id[:8] + "..."
                })
        upcoming.sort(key=lambda x: x["next_run"] or "9999")
        upcoming = upcoming[:5]
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": {
                "total": total_tasks,
                "enabled": enabled_tasks,
                "disabled": disabled_tasks,
                "conversations": conversations,
            },
            "upcoming": upcoming,
            "readonly": READONLY,
        })

    @app.get("/tasks", response_class=HTMLResponse)
    async def tasks_page(
        request: Request,
        conversation_id: Optional[str] = Query(None),
        enabled: Optional[bool] = Query(None),
        search: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=10, le=100),
    ):
        """Tasks list page with filters and pagination."""
        tasks = await store.list_tasks(conversation_id)
        
        # Apply filters
        if enabled is not None:
            tasks = [t for t in tasks if t.enabled == enabled]
        
        if search:
            search_lower = search.lower()
            tasks = [
                t for t in tasks
                if search_lower in t.name.lower()
                or search_lower in t.prompt.lower()
                or search_lower in t.cron
            ]
        
        # Get unique conversation IDs for filter dropdown
        all_tasks = await store.list_tasks()
        conversation_ids = sorted(set(t.conversation_id for t in all_tasks))
        
        # Pagination
        total_tasks = len(tasks)
        total_pages = (total_tasks + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        tasks = tasks[start_idx:end_idx]
        
        # Format tasks for display
        formatted_tasks = []
        for task in tasks:
            formatted_task = {
                "id": task.id,
                "name": task.name,
                "prompt_preview": task.prompt[:100] + "..." if len(task.prompt) > 100 else task.prompt,
                "cron": task.cron,
                "timezone": task.timezone,
                "conversation_id": task.conversation_id,
                "conversation_short": task.conversation_id[:12] + "...",
                "enabled": task.enabled,
                "last_run_at": task.last_run_at,
                "next_run_at": task.next_run_at,
            }
            
            # Format times
            if task.last_run_at:
                try:
                    dt = datetime.fromisoformat(task.last_run_at.replace('Z', '+00:00'))
                    formatted_task["last_run_formatted"] = dt.strftime("%Y-%m-%d %H:%M UTC")
                except:
                    formatted_task["last_run_formatted"] = task.last_run_at
            else:
                formatted_task["last_run_formatted"] = "—"
            
            if task.next_run_at:
                try:
                    dt = datetime.fromisoformat(task.next_run_at.replace('Z', '+00:00'))
                    formatted_task["next_run_formatted"] = dt.strftime("%Y-%m-%d %H:%M UTC")
                except:
                    formatted_task["next_run_formatted"] = task.next_run_at
            else:
                formatted_task["next_run_formatted"] = "—"
            
            formatted_tasks.append(formatted_task)
        
        return templates.TemplateResponse("tasks.html", {
            "request": request,
            "tasks": formatted_tasks,
            "conversation_ids": conversation_ids,
            "filters": {
                "conversation_id": conversation_id,
                "enabled": enabled,
                "search": search,
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_tasks": total_tasks,
            },
            "readonly": READONLY,
        })

    @app.get("/tasks/{task_id}", response_class=HTMLResponse)
    async def task_detail_page(request: Request, task_id: str):
        """Task detail page."""
        task = await store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Get conversation default timezone
        default_tz = await store.get_default_timezone(task.conversation_id)
        
        # Format times
        formatted_task = task.to_dict()
        
        if task.last_run_at:
            try:
                dt = datetime.fromisoformat(task.last_run_at.replace('Z', '+00:00'))
                formatted_task["last_run_formatted"] = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                
                # Convert to task timezone
                if task.timezone:
                    local_dt = dt.astimezone(ZoneInfo(task.timezone))
                    formatted_task["last_run_local"] = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
            except:
                formatted_task["last_run_formatted"] = task.last_run_at
        
        if task.next_run_at:
            try:
                dt = datetime.fromisoformat(task.next_run_at.replace('Z', '+00:00'))
                formatted_task["next_run_formatted"] = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                
                # Convert to task timezone
                if task.timezone:
                    local_dt = dt.astimezone(ZoneInfo(task.timezone))
                    formatted_task["next_run_local"] = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
            except:
                formatted_task["next_run_formatted"] = task.next_run_at
        
        # Calculate next few runs
        next_runs = []
        if task.enabled and task.cron and task.timezone:
            try:
                trigger = CronTrigger.from_crontab(task.cron, timezone=ZoneInfo(task.timezone))
                current_time = datetime.now(ZoneInfo(task.timezone))
                
                for i in range(5):
                    next_time = trigger.get_next_fire_time(None, current_time)
                    if next_time:
                        next_runs.append({
                            "utc": next_time.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M UTC"),
                            "local": next_time.strftime("%Y-%m-%d %H:%M %Z"),
                        })
                        current_time = next_time
            except Exception as e:
                logger.error(f"Error calculating next runs: {e}")
        
        return templates.TemplateResponse("task_detail.html", {
            "request": request,
            "task": formatted_task,
            "default_timezone": default_tz,
            "next_runs": next_runs,
            "readonly": READONLY,
        })

    # --- API Endpoints ---

    @app.get("/api/tasks")
    async def api_list_tasks(
        conversation_id: Optional[str] = Query(None),
        enabled: Optional[bool] = Query(None),
        search: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=10, le=100),
    ) -> Dict[str, Any]:
        """API endpoint to list tasks."""
        tasks = await store.list_tasks(conversation_id)
        
        # Apply filters
        if enabled is not None:
            tasks = [t for t in tasks if t.enabled == enabled]
        
        if search:
            search_lower = search.lower()
            tasks = [
                t for t in tasks
                if search_lower in t.name.lower()
                or search_lower in t.prompt.lower()
                or search_lower in t.cron
            ]
        
        # Pagination
        total = len(tasks)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        tasks = tasks[start_idx:end_idx]
        
        return {
            "tasks": [t.to_dict() for t in tasks],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    @app.get("/api/tasks/{task_id}")
    async def api_get_task(task_id: str) -> Dict[str, Any]:
        """API endpoint to get a single task."""
        task = await store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.to_dict()

    @app.post("/api/tasks/{task_id}/run")
    async def api_run_task_now(
        task_id: str,
        admin: bool = Depends(verify_admin_token)
    ) -> Dict[str, Any]:
        """Run a task immediately."""
        task = await store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        scheduler = get_task_scheduler()
        await scheduler.run_now(task_id)
        
        return {
            "success": True,
            "message": f"Task '{task.name}' is being executed",
        }

    @app.post("/api/tasks/{task_id}/toggle")
    async def api_toggle_task(
        task_id: str,
        request: ToggleTaskRequest,
        admin: bool = Depends(verify_admin_token)
    ) -> Dict[str, Any]:
        """Enable or disable a task."""
        task = await store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task.enabled = request.enabled
        scheduler = get_task_scheduler()
        await scheduler.update_task(task)
        
        status = "enabled" if request.enabled else "disabled"
        return {
            "success": True,
            "message": f"Task '{task.name}' has been {status}",
        }

    @app.delete("/api/tasks/{task_id}")
    async def api_delete_task(
        task_id: str,
        admin: bool = Depends(verify_admin_token)
    ) -> Dict[str, Any]:
        """Delete a task."""
        task = await store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        scheduler = get_task_scheduler()
        await scheduler.remove_task(task_id)
        
        return {
            "success": True,
            "message": f"Task '{task.name}' has been deleted",
        }

    @app.put("/api/tasks/{task_id}")
    async def api_update_task(
        task_id: str,
        request: UpdateTaskRequest,
        admin: bool = Depends(verify_admin_token)
    ) -> Dict[str, Any]:
        """Update task properties."""
        task = await store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Validate and update fields
        if request.name is not None:
            task.name = request.name
        
        if request.cron is not None:
            # Validate cron expression
            try:
                CronTrigger.from_crontab(request.cron, timezone=ZoneInfo(task.timezone))
                task.cron = request.cron
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid cron expression: {str(e)}")
        
        if request.timezone is not None:
            # Canonicalize and validate timezone
            iana_tz, _, suggestions = canonicalize_timezone(request.timezone)
            if not iana_tz:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid timezone: {request.timezone}",
                    headers={"X-Suggestions": ",".join(suggestions or [])}
                )
            task.timezone = iana_tz
        
        # Update in scheduler
        scheduler = get_task_scheduler()
        await scheduler.update_task(task)
        
        return {
            "success": True,
            "message": f"Task '{task.name}' has been updated",
            "task": task.to_dict(),
        }

    @app.get("/api/prefs/{conversation_id}")
    async def api_get_timezone_pref(conversation_id: str) -> Dict[str, Any]:
        """Get conversation timezone preference."""
        timezone = await store.get_default_timezone(conversation_id)
        return {
            "conversation_id": conversation_id,
            "timezone": timezone,
        }

    @app.post("/api/prefs/{conversation_id}")
    async def api_set_timezone_pref(
        conversation_id: str,
        request: SetTimezoneRequest,
        admin: bool = Depends(verify_admin_token)
    ) -> Dict[str, Any]:
        """Set conversation timezone preference."""
        # Canonicalize and validate timezone
        iana_tz, _, suggestions = canonicalize_timezone(request.timezone)
        if not iana_tz:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timezone: {request.timezone}",
                headers={"X-Suggestions": ",".join(suggestions or [])}
            )
        
        success = await store.set_default_timezone(conversation_id, iana_tz)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save timezone preference")
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "timezone": iana_tz,
            "message": f"Default timezone set to {iana_tz}",
        }

    @app.get("/api/meta/stats")
    async def api_stats() -> Dict[str, Any]:
        """Get task statistics."""
        tasks = await store.list_tasks()
        
        # Calculate stats
        total = len(tasks)
        enabled = sum(1 for t in tasks if t.enabled)
        disabled = total - enabled
        
        # Group by conversation
        by_conversation = {}
        for task in tasks:
            conv_id = task.conversation_id
            if conv_id not in by_conversation:
                by_conversation[conv_id] = {"enabled": 0, "disabled": 0}
            if task.enabled:
                by_conversation[conv_id]["enabled"] += 1
            else:
                by_conversation[conv_id]["disabled"] += 1
        
        # Find upcoming runs (next 24 hours)
        upcoming = []
        now = datetime.utcnow()
        for task in tasks:
            if task.enabled and task.next_run_at:
                try:
                    next_time = datetime.fromisoformat(task.next_run_at.replace('Z', '+00:00'))
                    hours_until = (next_time - now).total_seconds() / 3600
                    if 0 <= hours_until <= 24:
                        upcoming.append({
                            "task_id": task.id,
                            "name": task.name,
                            "next_run": task.next_run_at,
                            "hours_until": round(hours_until, 1),
                        })
                except:
                    pass
        
        upcoming.sort(key=lambda x: x["hours_until"])
        
        return {
            "total": total,
            "enabled": enabled,
            "disabled": disabled,
            "by_conversation": by_conversation,
            "upcoming_24h": upcoming[:10],  # Top 10 upcoming
        }

    return app


def main():
    """CLI entry point."""
    if not WEBUI_ENABLED:
        print("Tasks WebUI is disabled. Set TASKS_WEBUI_ENABLED=true to enable.")
        return
    
    app = create_app()
    
    print(f"Starting Tasks WebUI on http://{WEBUI_HOST}:{WEBUI_PORT}")
    print(f"Read-only mode: {READONLY}")
    if not READONLY:
        print("Admin mode enabled. Use X-Admin-Token header for mutations.")
    
    uvicorn.run(
        app,
        host=WEBUI_HOST,
        port=WEBUI_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
