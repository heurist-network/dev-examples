#!/usr/bin/env python3

import asyncio
import random
import logging
from typing import AsyncGenerator, Dict, List, Optional, Union, Callable, Any
from openai import OpenAI, OpenAIError
from agents import Agent as OpenAIAgent, Runner, gen_trace_id, trace, ModelSettings
from agents.mcp import MCPServerStdio

# Set up logger
logger = logging.getLogger(__name__)

# Default instructions for the BlockBeak agent
DEFAULT_INSTRUCTIONS = """
# ROLE: BlockBeak

You are BlockBeak, an advanced AI agent developed by Heurist. Operating within Telegram, you specialize in **cryptocurrency Q&A and analysis** and serve as a helpful **generalist assistant**. Prioritize accuracy, objectivity, and data-driven insights in all responses.

# DYNAMIC PERSONALITY

You adapt your communication style based on the user's query and context. Your primary goal is always accurate information delivery, but your framing shifts:

* Analyst (Default): Neutral, data-first, comprehensive. Used for standard requests.
* Pragmatic Pro: Confident, direct, focused on key takeaways and market context. Uses light, common crypto vernacular naturally. Activated for queries about price action, trends, sentiment, or direct token comparisons.
* The Pulse: Engaged, dynamic, reflects market energy and narratives. Uses more evocative language for significant events (pumps, dumps, major updates) similar to KOL commentary, but remains fact-based. Activated by queries focusing on the *why* behind dramatic price action ("Why did X pump/dump?"), significant project news/updates, or the prevailing narrative around a token.

The active personality influences tone and emphasis ONLY. Core data and adherence to output requirements remain paramount.

# CORE OPERATING PRINCIPLES

Autonomous Exploration: Analyze user requests and context. Independently devise the best plan and tool sequence to address the query. You are encouraged to explore relevant data points autonomously.
Iterative Refinement: Operate cyclically: Plan -> Act (Use Tool) -> Observe -> Reflect -> Refine Plan -> Respond. Adapt dynamically to tool outputs and information gathered.
Strategic Tool Use: Select the most appropriate tools from your suite (covering on-chain, market, social, web, wallet, KOL data). Synthesize findings from multiple sources for a comprehensive view. When assessing liquidity pools, prioritize Dexscreener data. Missing data or irregularity in data might indicate that you used the wrong search strategy, which you need to adjust your strategy. Don't give up or draw a conclusion too early.
Objective Reporting: Present factual data. Acknowledge data limitations or uncertainties clearly.

# CRYPTO ANALYSIS GUIDANCE

For crypto queries, let the user's request guide your analysis. Autonomously decide which aspects are most relevant to investigate, potentially including:

Token/Address Identification: Accurately identify entities across various chains (Solana, EVM, etc.) and formats (names, symbols, addresses, pump.fun).
Background Research: Investigate origins, narratives, news, official announcements, or teams if pertinent.
On-Chain & Market Data: Analyze price, volume, liquidity, holders, and other key info.
Social Signals: Evaluate sentiment, mentions, and community trends. MUST include full URLs for specific Tweets or Twitter profiles cited.
Key Wallets/Individuals: Research influential addresses or people if relevant to the query.

# FOUNDATIONAL KNOWLEDGE: HEURIST AI TOKEN

You are developed by Heurist. Remember these facts about the Heurist AI token:
* Name: Heurist
* Chain: Base
* Address: 0xEF22cb48B8483dF6152e1423b19dF5553BbD818b
* CoinGecko ID: heurist
* Dexscreener Search: heurist


# OUTPUT REQUIREMENTS (ABSOLUTE & STRICT)

Use Markdown formatting sparingly. NO bold or italics. NO Markdown headings. You may include lists and links if needed.
GMGN Links (Solana Only - CRITICAL):
    * Immediately after a Solana Token Address: https://gmgn.ai/sol/token/{token_address}
    * Immediately after a Solana Wallet Address: https://gmgn.ai/sol/address/{wallet_address}
    NEVER use GMGN links for non-Solana addresses (e.g., EVM `0x...`).
Source URLs: Provide full, plain text URLs for Tweets/Profiles when citing them.
Language: Match the user's query language.

# NO FOLLOW-UP QUESTIONS
Never prompt users to ask follow-up questions at the end of the response.

# GENERALIST CAPABILITIES

Address non-crypto questions and engage in general conversation naturally, maintaining the BlockBeak persona.
"""

class AgentError(Exception):
    """Custom error class for agent-related errors"""
    def __init__(self, message: str, details: Optional[Dict] = None, retriable: bool = False):
        super().__init__(message)
        self.details = details
        self.retriable = retriable

class AgentManager:
    """
    Core Agent Manager class that handles agent interactions.
    This class encapsulates all the OpenAI Agent SDK functionality.
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.1,
        max_tokens: int = 1000000,
        instructions: str = DEFAULT_INSTRUCTIONS,
        max_retries: int = 3,
        retry_delay_base: float = 1.0,
        handoffs: List[OpenAIAgent] = None,
        context: Optional[Dict[str, Any]] = None,
        enable_mcp_cache: bool = True,
        cache_ttl_seconds: int = 3600,  # Default: 1 hour cache lifetime
    ):
        """
        Initialize the Agent Manager.
        
        Args:
            model: The OpenAI model to use
            temperature: Model temperature setting
            max_tokens: Maximum tokens for response
            instructions: Agent instructions/system prompt
            max_retries: Maximum number of retries for API calls
            retry_delay_base: Base delay (in seconds) for exponential backoff
            handoffs: List of agents that this agent can hand off to
            context: Initial context for the agent
            enable_mcp_cache: Whether to enable caching for MCP server responses
            cache_ttl_seconds: Time-to-live for cached MCP responses in seconds
        """
        # Import settings here to avoid circular imports
        from ..config.settings import Settings
        
        # Get settings instance
        settings = Settings()
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        # Always use settings values for MCP proxy
        self.mcp_proxy_command = settings.mcp_proxy_command
        self.mcp_proxy_url = settings.mcp_proxy_url
        self.instructions = instructions
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.client = OpenAI()
        self.handoffs = handoffs or []
        self.context = context or {}
        self.enable_mcp_cache = enable_mcp_cache
        self.cache_ttl_seconds = cache_ttl_seconds
        
        self.fallback_models = ["gpt-4.1-nano"]
        self.mcp_server = None

    async def _exponential_backoff(self, retry_count: int) -> None:
        """Exponential backoff with jitter for retries."""
        delay = self.retry_delay_base * (2 ** retry_count) + random.uniform(0, 1)
        await asyncio.sleep(delay)
        
    def _create_error_details(self, error: Exception, retry_count: Optional[int] = None, model: Optional[str] = None, **extra_fields) -> Dict[str, Any]:
        """
        Create standardized error details dictionary.
        
        Args:
            error: The exception that occurred
            retry_count: Optional current retry count
            model: Optional model name if relevant
            **extra_fields: Any additional fields to include
            
        Returns:
            Standardized error details dictionary
        """
        details = {
            "type": type(error).__name__,
            "message": str(error),
        }
        
        # Add retry information if provided
        if retry_count is not None:
            details["retry"] = retry_count + 1
            details["max_retries"] = self.max_retries
        
        # Add model information if provided
        if model:
            details["model"] = model
            
        # Add OpenAI specific error details if available
        if isinstance(error, OpenAIError):
            if hasattr(error, 'request_id'):
                details["request_id"] = error.request_id
            if hasattr(error, 'status_code'):
                details["status_code"] = error.status_code
                # Add suggestion for server errors
                if getattr(error, 'status_code', 0) == 500 and "server_error" in str(error).lower():
                    details["suggestion"] = "The server error might be due to processing too much data. Try splitting your query into multiple smaller queries or reducing the complexity."
        
        # Add any extra fields
        details.update(extra_fields)
        
        return details

    async def _execute_with_retry(self, func, *args, models_to_try=None, **kwargs):
        """
        Generic retry utility that executes a function with retries.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            models_to_try: Optional list of models to try (for model-specific functions)
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the function if successful
            
        Raises:
            AgentError: If all retries fail
        """
        last_exception = None
        
        # If models are provided, try each model
        if models_to_try:
            for retry in range(self.max_retries):
                for model_idx, current_model in enumerate(models_to_try):
                    try:
                        # Add current model to kwargs
                        model_kwargs = {**kwargs, "model": current_model}
                        logger.debug(f"Trying model {current_model} (attempt {retry+1}/{self.max_retries})")
                        result = await func(*args, **model_kwargs)
                        
                        # If using a fallback model, log it
                        if current_model != self.model and "model" in model_kwargs:
                            logger.info(f"Using fallback model: {current_model} instead of {self.model}")
                            
                        return result
                    except Exception as e:
                        last_exception = e
                        logger.warning(f"Error with model {current_model}: {str(e)}")
                        error_details = self._create_error_details(
                            e, 
                            retry, 
                            current_model,
                            model_attempt=model_idx + 1
                        )
                        
                        # If we've tried all models in this retry, wait before the next retry
                        if model_idx == len(models_to_try) - 1 and retry < self.max_retries - 1:
                            logger.debug(f"Tried all models in retry {retry+1}, backing off before next attempt")
                            await self._exponential_backoff(retry)
        # Standard retry logic without model switching
        else:
            for retry in range(self.max_retries):
                try:
                    logger.debug(f"Executing function (attempt {retry+1}/{self.max_retries})")
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Error in retry {retry+1}/{self.max_retries}: {str(e)}")
                    error_details = self._create_error_details(e, retry)
                    
                    # Only retry if not the last attempt
                    if retry < self.max_retries - 1:
                        logger.debug(f"Backing off before retry {retry+2}")
                        await self._exponential_backoff(retry)
        
        # If we get here, all retries failed
        error_message = "Failed to execute function after multiple retries"
        logger.error(f"{error_message}: {str(last_exception)}", exc_info=True)
        error_details = self._create_error_details(
            last_exception if last_exception else Exception("Unknown error"),
            extra_operation="retry_exhausted"
        )
        
        raise AgentError(error_message, error_details, retriable=False)

    async def _create_agent_with_retry(self):
        """Create and return an OpenAI agent instance with retries."""
        logger.debug("Creating agent with retry mechanism")
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        
        async def create_agent(model):
            try:
                # Generate trace ID for this run
                self.trace_id = gen_trace_id()
                logger.debug(f"Generated trace ID: {self.trace_id}")
                
                # Create MCP server with proper tool caching
                logger.debug(f"Initializing MCP server with proxy: {self.mcp_proxy_command}")
                self.mcp_server = MCPServerStdio(
                    name="MCP Proxy Server",
                    params={
                        "command": self.mcp_proxy_command,
                        "args": [self.mcp_proxy_url],
                    },
                    # Enable tools caching per the OpenAI SDK documentation
                    cache_tools_list=self.enable_mcp_cache
                )
                
                # Create the agent with model settings
                model_settings = ModelSettings(
                    temperature=self.temperature,
                    max_tokens=min(self.max_tokens, 10000),  # Cap max_tokens to prevent errors
                )
                
                logger.debug(f"Creating OpenAI agent with model: {model}")
                return OpenAIAgent(
                    name="Assistant",
                    instructions=self.instructions,
                    mcp_servers=[self.mcp_server],
                    model=model,
                    model_settings=model_settings,
                    handoffs=self.handoffs
                )
            except Exception as e:
                logger.error(f"Error creating agent: {str(e)}", exc_info=True)
                raise
        
        return await self._execute_with_retry(create_agent, models_to_try=models_to_try)

    async def _run_agent_with_retry(self, agent, message):
        """Run the agent with retry logic."""
        async def run_agent():
            logger.info(f"Running agent with message: '{message[:50]}...' (truncated)")
            try:
                result = await Runner.run(
                    starting_agent=agent,
                    input=message,
                    context=self.context
                )
                
                # Update context with any new values from the result
                if hasattr(result, 'context') and result.context:
                    self.context.update(result.context)
                
                logger.info("Agent execution completed successfully")
                return result
            except Exception as e:
                logger.error(f"Error during agent execution: {str(e)}", exc_info=True)
                raise
        
        # Use the generic retry utility
        return await self._execute_with_retry(run_agent)

    async def process_message(
        self, 
        message: str,
        streaming: bool = False,
        context_update: Optional[Dict[str, Any]] = None
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Process a user message and return response.
        
        Args:
            message: The user message to process
            streaming: Whether to return a streaming response
            context_update: Optional dictionary to update the context
        
        Returns:
            Either a complete response string or an async generator for streaming
        """
        logger.info(f"Processing message: '{message[:50]}...' (truncated)")
        
        # Update context if provided
        if context_update:
            self.context.update(context_update)
            logger.debug(f"Updated context with {len(context_update)} keys")
            
        async def process():
            try:
                # Create agent first to initialize mcp_server with retries
                logger.debug("Creating agent with retry mechanism")
                agent = await self._create_agent_with_retry()
                
                # Now we can use self.mcp_server which was created in _create_agent
                logger.debug(f"MCP server initialized: {self.mcp_server is not None}")
                async with self.mcp_server:
                    # Run with tracing
                    with trace(workflow_name="MCP Agent", trace_id=self.trace_id):
                        trace_url = f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"
                        logger.debug(f"Trace ID: {self.trace_id}")
                        
                        # Run the agent with retries
                        logger.debug("Running agent with retries")
                        result = await self._run_agent_with_retry(agent, message)
                        
                        if streaming:
                            logger.debug("Preparing streaming response")
                            # For streaming, split the response into chunks
                            async def stream_response():
                                yield f"View trace: {trace_url}\n\n"
                                for chunk in result.final_output.split():
                                    yield chunk + " "
                            return stream_response()
                        else:
                            logger.info(f"Generated response of length {len(result.final_output)}")
                            return f"View trace: {trace_url}\n\n{result.final_output}"
            except Exception as e:
                logger.error(f"Error in process function: {str(e)}", exc_info=True)
                raise
        
        # Use the generic retry utility
        return await self._execute_with_retry(process)

    async def process_message_robust(
        self,
        message: str,
        streaming: bool = False,
        context_update: Optional[Dict[str, Any]] = None
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Process a message with top-level retries for extra robustness.
        """
        logger.info(f"Processing message robustly: '{message[:50]}...' (truncated)")
        
        # Special debug for cryptocurrency queries
        is_crypto_query = '$' in message or 'price' in message.lower() or 'token' in message.lower()
        if is_crypto_query:
            logger.info(f"Agent processing cryptocurrency query: '{message}'")
            
            # Special handling for crypto queries
            if message.startswith("what") and "$" in message:
                # This is likely a token price query
                logger.info("Detected token price query, optimizing processing")
        
        # Initialize top-level retry counter
        self._top_level_retry_count = 0
        
        # Try processing the message with retries
        try:
            # Add standard number of retries (resets for each new message)
            for retry in range(3):  # Maximum of 3 retries at this level
                try:
                    logger.debug(f"Attempt {retry+1}/3 to process message")
                    # Set a timeout for the entire processing operation
                    return await asyncio.wait_for(
                        self.process_message(message, streaming, context_update),
                        timeout=120  # 2 minute timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Timeout occurred during processing (attempt {retry+1})")
                    if retry < 2:  # If not the last retry
                        self._top_level_retry_count += 1
                        logger.warning(f"Top-level retry {retry+1}/3 after timeout")
                        await asyncio.sleep(2 * (retry + 1))  # Progressive backoff
                    else:
                        logger.error("All retries timed out")
                        raise AgentError("Operation timed out after multiple retries", 
                                        self._create_error_details(Exception("Timeout")), 
                                        retriable=False)
                except Exception as e:
                    if retry < 2:  # If not the last retry
                        self._top_level_retry_count += 1
                        error_details = self._create_error_details(e, retry, extra_level="top")
                        logger.warning(f"Top-level retry {retry+1}/3 after error: {str(e)}")
                        await asyncio.sleep(2 * (retry + 1))  # Progressive backoff
                    else:
                        # On last retry, just re-raise the exception
                        logger.error(f"All retries failed: {str(e)}", exc_info=True)
                        raise
            
            # Should never reach here due to the raise above
            logger.error("Failed to process message after maximum retries")
            raise AgentError(
                "Failed to process message after maximum retries", 
                self._create_error_details(Exception("All retries exhausted"), extra_level="top"),
                retriable=False
            )
        except Exception as e:
            # Wrap the exception in AgentError with standardized details if it's not already
            logger.error(f"Error during robust message processing: {str(e)}", exc_info=True)
            if not isinstance(e, AgentError):
                raise AgentError(
                    f"Error during message processing: {str(e)}", 
                    self._create_error_details(e, extra_level="top"),
                    retriable=False
                ) from e
            # Re-raise AgentError exceptions as is
            raise e

    def get_trace_url(self) -> str:
        """Get the URL for the current trace."""
        return f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"
    
    def add_handoff(self, agent: OpenAIAgent) -> None:
        """
        Add a handoff agent to this agent's handoffs.
        
        Args:
            agent: The agent to add as a handoff option
        """
        if agent not in self.handoffs:
            self.handoffs.append(agent)
    
    def clear_cache(self) -> None:
        """
        Clear the MCP server cache.
        This is useful when you want to force fresh data retrieval.
        """
        # Skip if caching isn't enabled
        if not self.enable_mcp_cache:
            print("MCP caching is disabled, nothing to clear.")
            return
            
        # If we don't have an MCP server instance yet, nothing to do
        if not hasattr(self, 'mcp_server') or self.mcp_server is None:
            print("No active MCP server instance, nothing to clear.")
            return
            
        # Try to invalidate cache using the SDK method
        if hasattr(self.mcp_server, 'invalidate_tools_cache'):
            self.mcp_server.invalidate_tools_cache()
            print("MCP server tools cache invalidated successfully.")
        else:
            # Fall back to recreating the server on next use
            self.mcp_server = None
            print("MCP server reset. Cache will be rebuilt on next request.")
