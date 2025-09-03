#!/usr/bin/env python3
"""
Notifiers for scheduled task results.
"""

import logging
from typing import Optional
from datetime import datetime
import aiohttp
import asyncio
import os

from .models import Task

logger = logging.getLogger(__name__)


class StdoutNotifier:
    """Simple stdout notifier for MVP testing."""
    
    async def notify(self, task: Task, text: str, trace_url: Optional[str] = None):
        """Print task result to stdout."""
        timestamp = datetime.utcnow().isoformat()
        output = f"\n{'='*60}\n"
        output += f"[{timestamp}] SCHEDULED TASK EXECUTED\n"
        output += f"Task ID: {task.id}\n"
        output += f"Task Name: {task.name}\n"
        output += f"Conversation: {task.conversation_id}\n"
        output += f"{'='*60}\n"
        output += f"Result:\n{text}\n"
        
        if trace_url:
            output += f"\nTrace URL: {trace_url}\n"
        
        output += f"{'='*60}\n"
        
        print(output)
        logger.info(f"Task {task.id} result delivered via stdout")


class XMTPNotifier:
    """
    XMTP notifier that sends results back to conversations via Node.js control server.
    (Phase 2 implementation)
    """
    
    def __init__(self):
        self.control_url = os.getenv("XMTP_CONTROL_URL", "http://127.0.0.1:8788/xmtp/send")
        self.control_token = os.getenv("XMTP_CONTROL_TOKEN", "")
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def notify(self, task: Task, text: str, trace_url: Optional[str] = None):
        """Send task result to XMTP conversation via control server."""
        
        # Format the message
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        message = f"📅 Scheduled Task: {task.name}\n"
        message += f"⏰ Executed at {timestamp}\n\n"
        message += text
        
        if trace_url and os.getenv("DEBUG_MODE", "false").lower() == "true":
            message += f"\n\n🔍 Trace: {trace_url}"
        
        # Prepare the request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.control_token}"
        }
        
        payload = {
            "conversationId": task.conversation_id,
            "text": message
        }
        
        # Send with retries
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.control_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Task {task.id} result sent to XMTP conversation")
                            return
                        else:
                            error_text = await response.text()
                            logger.warning(
                                f"XMTP notification failed (attempt {attempt + 1}/{self.max_retries}): "
                                f"Status {response.status}, Error: {error_text}"
                            )
            except Exception as e:
                logger.warning(
                    f"XMTP notification error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"Failed to send task {task.id} result to XMTP after {self.max_retries} attempts")
