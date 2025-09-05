#!/usr/bin/env python3

import asyncio
import logging
import os
from typing import Dict, Any, Optional, Deque, Tuple
from collections import deque
from time import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from src.core.agent import create_agent_manager, AgentError, detect_mode
from src.config.settings import Settings
from src.core.session.manager import get_session_manager, SessionType

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# FastAPI app instance
app = FastAPI(
    title="BlockBeak XMTP Agent API",
    description="API endpoint for XMTP chat integration with BlockBeak Agent",
    version="1.0.0",
)

# Pydantic models for request/response
class XMTPMessage(BaseModel):
    conversationId: str
    sender: str
    message: str
    replyContext: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    id: Optional[str] = None  # Message ID for idempotency

class AgentResponse(BaseModel):
    response: str
    trace_url: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str

class ModeDetectionRequest(BaseModel):
    message: str

class ModeDetectionResponse(BaseModel):
    mode: str

# Global agent manager cache per conversation
conversation_agents: Dict[str, Any] = {}



# Duplicate message tracking for idempotency
DEDUP_TTL_SEC = 10 * 60  # 10 minutes
DEDUP_MAX_PER_CONVO = 1000
recent_messages: Dict[str, Deque[Tuple[float, str]]] = {}

# Initialize session manager
session_manager = get_session_manager()

# Get DEBUG_MODE from settings
settings = Settings()
DEBUG_MODE = settings.debug_mode

def get_or_create_agent_manager(conversation_id: str):
    """Get or create an agent manager for a specific conversation."""
    if conversation_id not in conversation_agents:
        logger.info(f"Creating new agent manager for conversation: {conversation_id}")
        
        # Create conversation-scoped tools for scheduled tasks
        from src.tasks.tools import (
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
        
        # Check if conversation has a default timezone
        import asyncio
        from src.tasks import store
        
        # Get default timezone synchronously (we'll handle async properly later)
        default_tz = None
        try:
            loop = asyncio.get_event_loop()
            default_tz = loop.run_until_complete(store.get_default_timezone(conversation_id))
        except Exception as e:
            logger.debug(f"Could not get default timezone: {e}")
        
        # Add scheduling hint to context
        scheduling_context = {
            "xmtp_conversation_id": conversation_id,
            "scheduling_enabled": True,
            "scheduling_hint": (
                "When users ask to set up recurring updates or scheduled tasks "
                "(e.g., 'Give me BTC price every day at 9pm'), help them create a scheduled task. "
                "IMPORTANT: Always clarify the user's timezone before creating the task. "
                "Ask them to specify their timezone using city names (e.g., 'New York', 'Los Angeles', 'London') "
                "or standard timezone names (e.g., 'America/New_York', 'Europe/London'). "
                "Avoid ambiguous abbreviations like 'CST' (could be US Central or China Standard). "
                "If the user provides an ambiguous timezone, ask them to clarify by specifying the city. "
                "You can also suggest they set a default timezone using set_default_timezone. "
                "Common cron patterns: '0 21 * * *' = 9pm daily, '0 9 * * 1-5' = 9am weekdays, '*/30 * * * *' = every 30 minutes."
            )
        }
        
        # Add default timezone to context if available
        if default_tz:
            scheduling_context["default_timezone"] = default_tz
            scheduling_context["scheduling_hint"] += (
                f" Your default timezone is set to {default_tz}. "
                "Confirm with the user if they want to use this timezone or specify a different one."
            )
        
        conversation_agents[conversation_id] = create_agent_manager(
            extra_tools=extra_tools,
            context=scheduling_context
        )
    return conversation_agents[conversation_id]



def is_duplicate_message(conversation_id: str, message_id: Optional[str]) -> bool:
    """Check if a message has been recently processed (idempotency check)."""
    if not message_id:
        return False  # Can't check duplicates without message ID
    
    now = time()
    dq = recent_messages.setdefault(conversation_id, deque())
    
    # Prune old messages
    while dq and now - dq[0][0] > DEDUP_TTL_SEC:
        dq.popleft()
    
    # Check for duplicate
    for _, mid in dq:
        if mid == message_id:
            logger.info(f"Duplicate message detected: {message_id} for conversation {conversation_id}")
            return True
    
    # Add new message and cap the deque size
    dq.append((now, message_id))
    if len(dq) > DEDUP_MAX_PER_CONVO:
        dq.popleft()
    
    return False

@app.post("/inbox", response_model=AgentResponse)
async def process_xmtp_message(message: XMTPMessage):
    """
    Process an incoming XMTP message and return the agent's response.
    Supports optional per-conversation locking for serialization control.
    
    Args:
        message: XMTPMessage containing conversationId, sender, message, and optional meta
        
    Returns:
        AgentResponse containing the AI response and trace URL
    """
    try:
        # Check for duplicate message (idempotency)
        if is_duplicate_message(message.conversationId, message.id):
            logger.info(f"Skipping duplicate message {message.id} for conversation {message.conversationId}")
            return AgentResponse(
                response="[Duplicate message - already processed]",
                trace_url=None
            )
        
        logger.info(f"Processing message from {message.sender} in conversation {message.conversationId}")
        if message.id:
            logger.debug(f"Message ID: {message.id}")
        logger.debug(f"Message content: {message.message}")
        
        # Check if this is a reply to another message
        if message.replyContext:
            logger.info(f"Message is a reply to: {message.replyContext}")
        
        # Get session for conversation
        session_id = session_manager.get_session_id(
            SessionType.XMTP_CONVERSATION,
            conversation_id=message.conversationId
        )
        session = await session_manager.get_or_create_session(session_id)
        
        # Get or create agent manager for this conversation
        agent_manager = get_or_create_agent_manager(message.conversationId)
        
        # Prepare the message content with reply context if available
        processed_message = message.message
        if message.replyContext:
            processed_message = f"[Replying to: \"{message.replyContext}\"]\n{message.message}"
        
        # Create context update
        context_update = {
            "conversation_id": message.conversationId,
            "sender": message.sender,
        }
        
        # Debug log for incoming meta
        if message.meta:
            logger.info(f"Received meta with keys: {list(message.meta.keys())}")
    
        # Add reply context to metadata if available
        if message.replyContext:
            context_update["reply_context"] = message.replyContext
        
        # Handle image meta data - merge into context if present, clear if absent
        has_image = False
        if message.meta:
            logger.info(f"Context update keys: {list(message.meta.keys())}")
            context_update.update(message.meta)
            # Log if wallet info is present
            if "wallet" in message.meta:
                wallet_info = message.meta["wallet"]
                if wallet_info.get("has_address"):
                    logger.info(f"Wallet context: {wallet_info.get('primary_address', 'unknown')} on {wallet_info.get('chain', 'unknown')} chain")
                else:
                    logger.info("Wallet context: No associated address found")
            # Log if image data is present (without logging the actual data URL for brevity)
            if "image_data_url" in message.meta:
                logger.info(f"Image data received - filename: {message.meta.get('filename', 'unknown')}, mime_type: {message.meta.get('mime_type', 'unknown')}")
                has_image = True
        else:
            # Clear any previous image data to ensure text-only turns don't retain old images
            context_update["image_data_url"] = None
        
        # Process the message through the agent (XMTP client already handles ordering)
        logger.info(f"Processing message for conversation {message.conversationId}")
        result = await agent_manager.process_message(
            message=processed_message,
            streaming=False,
            context_update=context_update,
            session=session  # Session is handled internally, not passed to Runner.run
        )
        
        logger.info(f"Agent response generated for conversation {message.conversationId}")
        logger.debug(f"Response: {result['output'][:100]}...")  # Log first 100 chars
        
        # Build response based on debug mode
        response_data = AgentResponse(response=result["output"])
        
        # Only include trace_url if debug_mode is enabled and trace_url exists
        if DEBUG_MODE and "trace_url" in result:
            response_data.trace_url = result["trace_url"]
            logger.debug(f"Trace URL included in response: {result['trace_url']}")
        
        # Persist this turn to session storage when we skipped session_for_call
        # to keep conversation history consistent (avoid storing large base64).
        try:
            if has_image and session is not None and isinstance(processed_message, str):
                user_summary = processed_message
                # Add a compact image note without embedding data URL
                filename = message.meta.get("filename", "image") if message.meta else "image"
                mime_type = message.meta.get("mime_type", "image/*") if message.meta else "image/*"
                user_summary += f"\n[Attached image: {filename} ({mime_type})]"
                await session.add_items([
                    {"role": "user", "content": user_summary},
                    {"role": "assistant", "content": result.get("output", "")},
                ])
        except Exception as persist_err:
            logger.warning(f"Failed to persist image turn to session: {persist_err}")

        return response_data
        
    except AgentError as e:
        logger.error(f"Agent error processing message: {str(e)}")
        
        # Include trace URL in error detail if available and debug mode is enabled
        error_detail = f"Agent error: {str(e)}"
        if DEBUG_MODE and hasattr(e, 'details') and e.details:
            trace_url = e.details.get('trace_url')
            if trace_url:
                # Return error with trace URL in structured format
                logger.info(f"Including trace URL in error response: {trace_url}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": str(e),
                        "trace_url": trace_url
                    }
                )
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )
    except Exception as e:
        logger.error(f"Unexpected error processing message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/detect-mode", response_model=ModeDetectionResponse)
async def detect_agent_mode(request: ModeDetectionRequest):
    """
    Detect which agent mode (normal/deep) should be used for a message.
    Fast endpoint that only does mode detection without processing.
    
    Args:
        request: ModeDetectionRequest containing the message text
        
    Returns:
        ModeDetectionResponse containing the detected mode
    """
    try:
        logger.info(f"Detecting mode for message: {request.message[:50]}...")
        
        # Use the existing mode detection logic
        detected_mode = detect_mode(request.message)
        
        logger.info(f"Mode detected: {detected_mode}")
        return ModeDetectionResponse(mode=detected_mode)
        
    except Exception as e:
        logger.error(f"Error detecting mode: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Mode detection error: {str(e)}"
        )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Verify that settings can be loaded
        settings = Settings()
        if not settings.api_key:
            raise HTTPException(
                status_code=503,
                detail="Service unavailable: Missing API configuration"
            )
        
        return HealthResponse(status="healthy", version="1.0.0")
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("Starting BlockBeak XMTP Agent API")
    await session_manager.start_cleanup_task()
    
    # Start the task scheduler
    from src.tasks.scheduler import get_task_scheduler
    # Enable XMTP notifier if control server is configured
    use_xmtp = bool(os.getenv("XMTP_CONTROL_URL"))
    scheduler = get_task_scheduler(use_xmtp_notifier=use_xmtp)
    await scheduler.start()
    logger.info(f"Task scheduler started (XMTP notifier: {use_xmtp})")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down BlockBeak XMTP Agent API")
    # Clear conversation cache
    conversation_agents.clear()
    # Clear duplicate tracking
    recent_messages.clear()
    # Stop session cleanup task
    await session_manager.stop_cleanup_task()
    
    # Stop the task scheduler
    from src.tasks.scheduler import get_task_scheduler
    scheduler = get_task_scheduler()
    await scheduler.shutdown()
    logger.info("Task scheduler shut down")

def run_api(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the XMTP API server."""
    logger.info(f"Starting XMTP API server on {host}:{port}")
    uvicorn.run(
        "src.interfaces.xmtp.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    run_api(reload=True)