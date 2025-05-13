#!/usr/bin/env python3

import asyncio
import random
import logging
import yaml
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Union, Callable, Any
from openai import OpenAI, OpenAIError
from agents import Agent as OpenAIAgent, Runner, gen_trace_id, trace, ModelSettings
from agents.mcp import MCPServerSse
from src.config.settings import Settings

logger = logging.getLogger(__name__)

def load_agent_instructions() -> str:
    """Load agent instructions from YAML file."""
    try:
        config_dir = Path(__file__).parent.parent / "config"
        yaml_path = config_dir / "agent_instructions.yaml"
        
        if not yaml_path.exists():
            logger.error(f"Agent instructions file not found at: {yaml_path}")
            raise FileNotFoundError(f"Missing agent instructions file: {yaml_path}")
            
        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f)['instructions']
            
    except Exception as e:
        logger.error(f"Failed to load agent instructions: {str(e)}")
        raise

DEFAULT_INSTRUCTIONS = load_agent_instructions()

class AgentError(Exception):
    """Custom error class for agent-related errors"""
    def __init__(self, message: str, details: Optional[Dict] = None, retriable: bool = False):
        super().__init__(message)
        self.details = details
        self.retriable = retriable

class RetryableError(AgentError):
    """Error class for operations that can be retried"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, details, retriable=True)

class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: Optional[float] = None,
        retriable_exceptions: Optional[List[type]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        # Default retriable exceptions if none provided
        self.retriable_exceptions = retriable_exceptions or [
            RetryableError,
            asyncio.TimeoutError,
            OpenAIError,  # Most OpenAI errors are retriable
        ]

class AgentManager:
    """
    Core Agent Manager class that handles agent interactions.
    This class encapsulates all the OpenAI Agent SDK functionality.
    """
    
    def __init__(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        mcp_sse_url: str,
        instructions: str = DEFAULT_INSTRUCTIONS,
        retry_config: Optional[RetryConfig] = None,
        context: Optional[Dict[str, Any]] = None,
        enable_mcp_cache: bool = True,
        cache_ttl_seconds: int = 3600,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.mcp_sse_url = mcp_sse_url   
        self.instructions = instructions
        self.retry_config = retry_config or RetryConfig()
        self.client = OpenAI()
        self.context = context or {}
        self.enable_mcp_cache = enable_mcp_cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self.mcp_server = None

    def _create_error_details(self, error: Exception, retry_count: Optional[int] = None, model: Optional[str] = None, **extra_fields) -> Dict[str, Any]:
        details = {
            "type": type(error).__name__,
            "message": str(error),
        }
        
        if retry_count is not None:
            details["retry"] = retry_count + 1
            details["max_retries"] = self.retry_config.max_retries
        
        if model:
            details["model"] = model
            
        if isinstance(error, OpenAIError):
            if hasattr(error, 'request_id'):
                details["request_id"] = error.request_id
            if hasattr(error, 'status_code'):
                details["status_code"] = error.status_code
        
        details.update(extra_fields)
        return details

    async def _exponential_backoff(self, retry_count: int) -> None:
        delay = min(
            self.retry_config.base_delay * (2 ** retry_count) + random.uniform(0, 1),
            self.retry_config.max_delay
        )
        await asyncio.sleep(delay)

    async def _execute_with_retry(
        self,
        func: Callable,
        *args,
        retry_config: Optional[RetryConfig] = None,
        **kwargs
    ):
        """
        Enhanced retry utility that executes a function with retries.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            retry_config: Optional retry configuration override
            **kwargs: Keyword arguments for the function
        """
        config = retry_config or self.retry_config
        last_exception = None
        
        async def execute_with_timeout(f, *a, **kw):
            if config.timeout:
                return await asyncio.wait_for(f(*a, **kw), timeout=config.timeout)
            return await f(*a, **kw)

        for retry in range(config.max_retries):
            try:
                logger.debug(f"Executing function (attempt {retry+1}/{config.max_retries})")
                return await execute_with_timeout(func, *args, **kwargs)
                
            except Exception as e:
                last_exception = e
                error_details = self._create_error_details(e, retry)

                is_retriable = isinstance(e, tuple(config.retriable_exceptions))
                if not is_retriable:
                    logger.error(f"Non-retriable error encountered: {str(e)}")
                    raise AgentError(str(e), error_details, retriable=False)
                
                logger.warning(f"Retriable error in attempt {retry+1}: {str(e)}")
                
                if retry < config.max_retries - 1:
                    await self._exponential_backoff(retry)
        
        # If we get here, all retries failed
        error_message = "Failed to execute function after maximum retries"
        logger.error(f"{error_message}: {str(last_exception)}")
        error_details = self._create_error_details(
            last_exception or Exception("Unknown error"),
            extra_operation="retry_exhausted"
        )
        
        raise AgentError(error_message, error_details, retriable=False)

    async def _create_agent_with_retry(self):
        async def create_agent():
            self.trace_id = gen_trace_id()
            logger.debug(f"Generated trace ID: {self.trace_id}")
            
            self.mcp_server = MCPServerSse(
                name="MCP SSE Server",
                params={"url": self.mcp_sse_url},
                cache_tools_list=self.enable_mcp_cache,
                client_session_timeout_seconds=60
            )
            
            model_settings = ModelSettings(
                temperature=self.temperature,
                max_tokens=min(self.max_tokens, 10000),
            )
            
            logger.debug(f"Creating OpenAI agent with model: {self.model}")
            return OpenAIAgent(
                name="Assistant",
                instructions=self.instructions,
                mcp_servers=[self.mcp_server],
                model=self.model,
                model_settings=model_settings
            )
        
        return await self._execute_with_retry(
            create_agent,
            retry_config=RetryConfig(timeout=30)
        )

    async def _run_agent_with_retry(self, agent, message):
        async def run_agent():
            logger.info(f"Running agent with message: '{message[:50]}...' (truncated)")
            result = await Runner.run(
                starting_agent=agent,
                input=message,
                context=self.context
            )
            
            if hasattr(result, 'context') and result.context:
                self.context.update(result.context)
            
            logger.info("Agent execution completed successfully")
            return result
        
        return await self._execute_with_retry(
            run_agent,
            retry_config=RetryConfig(timeout=120)  # 2 minute timeout for agent execution
        )

    async def process_message(
        self, 
        message: str,
        streaming: bool = False,
        context_update: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, str], AsyncGenerator[str, None]]:
        if context_update:
            self.context.update(context_update)
            logger.debug(f"Updated context with {len(context_update)} keys")

        agent = await self._create_agent_with_retry()
        
        logger.debug(f"MCP server initialized: {self.mcp_server is not None}")
        async with self.mcp_server:
            with trace(workflow_name="MCP Agent", trace_id=self.trace_id):
                trace_url = f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"
                logger.debug(f"Trace ID: {self.trace_id}")
                
                result = await self._run_agent_with_retry(agent, message)
                
                if streaming:
                    logger.debug("Preparing streaming response")
                    async def stream_response():
                        yield f"View trace: {trace_url}\n\n"
                        for chunk in result.final_output.split():
                            yield chunk + " "
                    return stream_response()
                else:
                    logger.info(f"Generated response of length {len(result.final_output)}")
                    return {
                        "output": result.final_output,
                        "trace_url": trace_url
                    }

    def get_trace_url(self) -> str:
        """Get the URL for the current trace."""
        return f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"
    
    def clear_cache(self) -> None:
        """Clear the MCP server cache."""
        if not self.enable_mcp_cache:
            logger.info("MCP caching is disabled, nothing to clear.")
            return
            
        if not hasattr(self, 'mcp_server') or self.mcp_server is None:
            logger.info("No active MCP server instance, nothing to clear.")
            return
            
        if hasattr(self.mcp_server, 'invalidate_tools_cache'):
            self.mcp_server.invalidate_tools_cache()
            logger.info("MCP server tools cache invalidated successfully.")
        else:
            self.mcp_server = None
            logger.info("MCP server reset. Cache will be rebuilt on next request.")

def create_agent_manager(
    agent_config_override: Optional[Dict[str, Any]] = None,
    **kwargs  # For other AgentManager direct params like instructions, retry_config etc.
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
