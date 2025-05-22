#!/usr/bin/env python3

import asyncio
import random
import logging
from typing import AsyncGenerator, Dict, Optional, Union, Callable, Any
from openai import OpenAI, OpenAIError
from agents import Agent as OpenAIAgent, Runner, gen_trace_id, trace, ModelSettings
from agents.mcp import MCPServerSse
from src.config.settings import Settings

logger = logging.getLogger(__name__)

class AgentError(Exception):
    """Custom error class for agent-related errors"""
    def __init__(self, message: str, details: Optional[Dict] = None, retryable: bool = False):
        super().__init__(message)
        self.details = details or {}
        self.retryable = retryable

class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: Optional[float] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.retryable_exceptions = [
            AgentError,
            asyncio.TimeoutError,
            OpenAIError,
        ]
    
    def is_retryable(self, error: Exception) -> bool:
        if isinstance(error, AgentError):
            return error.retryable
        return isinstance(error, tuple(self.retryable_exceptions))
        
    async def backoff(self, retry_count: int) -> None:
        delay = min(
            self.base_delay * (2 ** retry_count) + random.uniform(0, 1),
            self.max_delay
        )
        await asyncio.sleep(delay)

class AgentManager:
    """Core Agent Manager class that handles agent interactions."""
    
    def __init__(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        mcp_sse_url: str,
        instructions: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        context: Optional[Dict[str, Any]] = None,
        enable_mcp_cache: bool = True,
        cache_ttl_seconds: int = 3600,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.mcp_sse_url = mcp_sse_url
        self.enable_mcp_cache = enable_mcp_cache
        self.cache_ttl_seconds = cache_ttl_seconds
        
        self.mcp_server = MCPServerSse(
            name="MCP SSE Server",
            params={"url": self.mcp_sse_url},
            cache_tools_list=self.enable_mcp_cache,
            client_session_timeout_seconds=60
        )

        self.instructions = instructions or Settings().get_agent_instructions()
        self.retry_config = retry_config or RetryConfig()
        self.client = OpenAI()
        self.context = context or {}

        self.trace_id = None

    async def _execute_with_retry(self, func: Callable, *args, **kwargs):
        """Execute a function with retries based on retry configuration"""
        config = self.retry_config
        last_error = None
        
        for retry in range(config.max_retries):
            try:
                if config.timeout:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=config.timeout)
                return await func(*args, **kwargs)
                
            except Exception as error:
                last_error = error
                is_retryable = config.is_retryable(error)
                
                if not is_retryable or retry >= config.max_retries - 1:
                    break
                    
                logger.warning(f"retryable error in attempt {retry+1}/{config.max_retries}: {str(error)}")
                await config.backoff(retry)
        
        # If we get here, all retries failed or error wasn't retryable
        error_message = f"Operation failed: {str(last_error)}"
        logger.error(error_message)
        raise AgentError(error_message, {"original_error": str(last_error)})

    async def process_message(
        self, 
        message: str,
        streaming: bool = False,
        context_update: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, str], AsyncGenerator[str, None]]:
        """Process a user message and return the agent's response"""
        if context_update:
            self.context.update(context_update)
    
        self.trace_id = gen_trace_id()
        logger.debug(f"Generated trace ID: {self.trace_id}")
        
        
        # Create agent
        model_settings = ModelSettings(
            temperature=self.temperature,
            max_tokens=min(self.max_tokens, 10000),
        )
        
        agent = OpenAIAgent(
            name="Assistant",
            instructions=self.instructions,
            mcp_servers=[self.mcp_server],
            model=self.model,
            model_settings=model_settings
        )
    
        async with self.mcp_server:
            with trace(workflow_name="BlockBeak MCP Agent", trace_id=self.trace_id):
                try:
                    result = await self._execute_with_retry(
                        Runner.run,
                        starting_agent=agent,
                        input=message,
                        context=self.context,
                    )
                    
                    # Update context with any new values from result
                    if hasattr(result, 'context') and result.context:
                        self.context.update(result.context)
                    
                    trace_url = self.get_trace_url()
                    
                    if streaming:
                        async def stream_response():
                            yield f"View trace: {trace_url}\n\n"
                            for chunk in result.final_output.split():
                                yield chunk + " "
                        return stream_response()
                    else:
                        return {
                            "output": result.final_output,
                            "trace_url": trace_url
                        }
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    raise AgentError(f"Failed to process message: {str(e)}")

    def get_trace_url(self) -> str:
        """Get the URL for the current trace."""
        return f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"
    
    def clear_cache(self) -> None:
        """Clear the MCP server cache."""
        if not self.enable_mcp_cache or not hasattr(self, 'mcp_server') or self.mcp_server is None:
            logger.info("MCP caching is disabled or server not initialized, nothing to clear.")
            return
            
        if hasattr(self.mcp_server, 'invalidate_tools_cache'):
            self.mcp_server.invalidate_tools_cache()
            logger.info("MCP server tools cache invalidated successfully.")
        else:
            self.mcp_server = None
            logger.info("MCP server reset. Cache will be rebuilt on next request.")

def create_agent_manager(
    agent_config_override: Optional[Dict[str, Any]] = None,
    **kwargs
) -> AgentManager:
    """
    Create an AgentManager instance.
    It fetches its core configuration (model, temp, tokens, mcp_url) 
    from Settings, but allows overrides.
    
    Args:
        agent_config_override: Optional dict to override specific agent config values 
                               (model, temperature, max_tokens, mcp_sse_url).
        **kwargs: Additional keyword arguments to pass directly to AgentManager constructor
                  (e.g., instructions, retry_config, context, enable_mcp_cache).
    """
    
    config = Settings().get_openai_config()
    
    if agent_config_override:
        config.update(agent_config_override)

    return AgentManager(**{**config, **kwargs})
