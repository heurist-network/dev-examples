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
        conversation_agents[conversation_id] = create_agent_manager()
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
    
        # Add reply context to metadata if available
        if message.replyContext:
            context_update["reply_context"] = message.replyContext
        
        # Handle image meta data - merge into context if present, clear if absent
        has_image = False
        if message.meta:
            logger.info(f"Context update keys: {list(message.meta.keys())}")
            context_update.update(message.meta)
            # Log if image data is present (without logging the actual data URL for brevity)
            if "image_data_url" in message.meta:
                logger.info(f"Image data received - filename: {message.meta.get('filename', 'unknown')}, mime_type: {message.meta.get('mime_type', 'unknown')}")
                has_image = True
        else:
            # Clear any previous image data to ensure text-only turns don't retain old images
            context_update["image_data_url"] = None
        
        # If an image is present, do not pass session to allow multimodal list input
        # We'll persist this turn into our session storage manually afterwards.
        session_for_call = None if has_image else session
        
        # Process the message through the agent (XMTP client already handles ordering)
        logger.info(f"Processing message for conversation {message.conversationId}")
        result = await agent_manager.process_message(
            message=processed_message,
            streaming=False,
            context_update=context_update,
            session=session_for_call
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
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}"
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