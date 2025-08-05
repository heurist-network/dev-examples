#!/usr/bin/env python3

import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from src.core.agent import create_agent_manager, AgentError
from src.config.settings import Settings

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
    meta: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    response: str
    trace_url: str

class HealthResponse(BaseModel):
    status: str
    version: str

# Global agent manager cache per conversation
conversation_agents: Dict[str, Any] = {}

def get_or_create_agent_manager(conversation_id: str):
    """Get or create an agent manager for a specific conversation."""
    if conversation_id not in conversation_agents:
        logger.info(f"Creating new agent manager for conversation: {conversation_id}")
        conversation_agents[conversation_id] = create_agent_manager()
    return conversation_agents[conversation_id]

@app.post("/inbox", response_model=AgentResponse)
async def process_xmtp_message(message: XMTPMessage):
    """
    Process an incoming XMTP message and return the agent's response.
    
    Args:
        message: XMTPMessage containing conversationId, sender, message, and optional meta
        
    Returns:
        AgentResponse containing the AI response and trace URL
    """
    try:
        logger.info(f"Processing message from {message.sender} in conversation {message.conversationId}")
        logger.debug(f"Message content: {message.message}")
        
        # Get or create agent manager for this conversation
        agent_manager = get_or_create_agent_manager(message.conversationId)
        
        # Prepare context update with sender and conversation info
        context_update = {
            "conversation_id": message.conversationId,
            "sender": message.sender,
        }
        
        # Add any additional metadata to context
        if message.meta:
            context_update.update(message.meta)
        
        # Process the message through the agent
        result = await agent_manager.process_message(
            message=message.message,
            streaming=False,
            context_update=context_update
        )
        
        logger.info(f"Agent response generated for conversation {message.conversationId}")
        logger.debug(f"Response: {result['output'][:100]}...")  # Log first 100 chars
        
        return AgentResponse(
            response=result["output"],
            trace_url=result["trace_url"]
        )
        
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

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down BlockBeak XMTP Agent API")
    # Clear conversation cache
    conversation_agents.clear()

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