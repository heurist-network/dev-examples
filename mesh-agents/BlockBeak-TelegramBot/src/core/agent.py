#!/usr/bin/env python3

import asyncio
import random
import logging
from typing import AsyncGenerator, Dict, Optional, Union, Callable, Any, Literal
from openai import OpenAI, OpenAIError
from agents import Agent as OpenAIAgent, Runner, gen_trace_id, trace, ModelSettings
from agents.mcp import MCPServerSse
from agents.extensions.models.litellm_model import LitellmModel
from src.config.settings import Settings

logger = logging.getLogger(__name__)

# Agent modes
AgentMode = Literal["normal", "deep"]

def detect_mode(message: str) -> AgentMode:
    """
    Detect which agent mode to use based on message content.
    Supports multiple languages.
    
    Returns "deep" if message contains keywords indicating need for deep analysis,
    otherwise returns "normal" for standard responses.
    """
    # Multi-language deep mode keywords
    deep_keywords = {
        # English
        "deep", "analyze", "analysis", "research", "comprehensive", "detailed",
        "in-depth", "thorough", "extensive", "investigate", "examination",
        
        # Chinese (Simplified & Traditional)
        "深入", "分析", "研究", "全面", "详细", "深度", "透彻", "详尽",
        "調研", "探究", "剖析", "综合分析", "深入分析", "全面分析",
        "詳細", "深度分析", "徹底", "詳盡", "綜合分析",
        
        # Japanese
        "詳しく", "分析", "研究", "詳細", "深く", "徹底的", "包括的",
        "調査", "検証", "深掘り", "詳しい分析",
        
        # Korean
        "심층", "분석", "연구", "상세", "자세한", "종합적", "심도있는",
        "깊이있는", "면밀한", "철저한",
        
        # Spanish
        "profundo", "analizar", "análisis", "investigar", "investigación",
        "detallado", "exhaustivo", "comprensivo", "minucioso",
        
        # French
        "approfondi", "analyser", "analyse", "recherche", "détaillé",
        "exhaustif", "complet", "minutieux",
        
        # German
        "tiefgehend", "analysieren", "analyse", "forschung", "umfassend",
        "detailliert", "gründlich", "ausführlich",
        
        # Russian
        "глубокий", "анализ", "исследование", "подробный", "детальный",
        "всесторонний", "тщательный", "углубленный",
        
        # Portuguese
        "profundo", "analisar", "análise", "pesquisa", "detalhado",
        "abrangente", "minucioso", "aprofundado",
        
        # Arabic
        "عميق", "تحليل", "بحث", "شامل", "مفصل", "دراسة",
        
        # Hindi
        "गहन", "विश्लेषण", "अनुसंधान", "विस्तृत", "व्यापक",
    }
    
    message_lower = message.lower()
    
    # Check for any deep mode keyword in the message
    for keyword in deep_keywords:
        if keyword in message_lower:
            logger.info(f"Deep mode activated - keyword '{keyword}' detected")
            return "deep"
    
    # Additional heuristics for non-keyword based detection
    # Check for question complexity indicators
    complexity_indicators = [
        # Multiple questions (indicated by multiple question marks)
        message.count("?") >= 2,
        message.count("？") >= 2,  # Chinese/Japanese question mark
        
        # Long messages often require deeper analysis
        len(message) > 200,
        
        # Comparison requests (vs, versus, compare, etc.)
        any(indicator in message_lower for indicator in [
            " vs ", " versus ", "compare", "difference between",
            "对比", "比较", "相比", "区别",  # Chinese
            "比べ", "違い",  # Japanese
            "비교", "차이",  # Korean
            "comparar", "diferencia",  # Spanish
            "comparer", "différence",  # French
        ]),
        
        # "Why" questions often need deeper analysis
        any(why in message_lower for why in [
            "why", "how come", "reason",
            "为什么", "为何", "怎么会",  # Chinese
            "なぜ", "どうして",  # Japanese
            "왜", "어째서",  # Korean
            "por qué", "por que",  # Spanish
            "pourquoi",  # French
            "warum",  # German
            "почему",  # Russian
        ]),
        
        # Technical mechanism questions
        any(tech in message_lower for tech in [
            "mechanism", "how does", "how it works", "architecture",
            "机制", "原理", "如何工作", "架构",  # Chinese
            "仕組み", "メカニズム",  # Japanese
            "메커니즘", "구조",  # Korean
        ]),
    ]
    
    # If any complexity indicator is true, consider deep mode
    if any(complexity_indicators):
        logger.info("Deep mode activated - complexity indicators detected")
        return "deep"
    
    logger.info("Normal mode selected")
    return "normal"


class AgentError(Exception):
    """Custom error class for agent-related errors"""

    def __init__(
        self, message: str, details: Optional[Dict] = None, retryable: bool = False
    ):
        super().__init__(message)
        self.details = details or {}
        self.retryable = retryable


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(
        self,
        max_retries: int = 1,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: Optional[float] = None,
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
            self.base_delay * (2**retry_count) + random.uniform(0, 1), self.max_delay
        )
        await asyncio.sleep(delay)


class AgentManager:
    """Core Agent Manager class that handles agent interactions with dual-mode support."""

    def __init__(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        mcp_sse_url: str,
        instructions: Optional[str] = None,
        instructions_normal: Optional[str] = None,
        instructions_deep: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        context: Optional[Dict[str, Any]] = None,
        enable_mcp_cache: bool = True,
        cache_ttl_seconds: int = 3600,
        provider: str = "openai",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.mcp_sse_url = mcp_sse_url
        self.enable_mcp_cache = enable_mcp_cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url

        self.mcp_server = MCPServerSse(
            name="MCP SSE Server",
            params={"url": self.mcp_sse_url},
            cache_tools_list=self.enable_mcp_cache,
            client_session_timeout_seconds=60,
        )

        # Load instructions for both modes
        settings = Settings()
        self.instructions_normal = instructions_normal or settings.get_agent_instructions("normal")
        self.instructions_deep = instructions_deep or settings.get_agent_instructions("deep")
        # Keep backward compatibility
        self.instructions = instructions or self.instructions_normal
        self.retry_config = retry_config or RetryConfig()

        # Only initialize OpenAI client for OpenAI provider
        self.client = None
        if self.provider == "openai" and self.api_key:
            self.client = OpenAI(api_key=self.api_key)

        self.context = context or {}
        self.trace_id = None

    def _get_model_instance(self):
        """Get the appropriate model instance based on provider"""
        if self.provider == "openai":
            return self.model
        else:
            # For LiteLLM providers
            litellm_kwargs = {"model": self.model, "api_key": self.api_key}
            if self.base_url:
                litellm_kwargs["base_url"] = self.base_url
            return LitellmModel(**litellm_kwargs)

    async def _execute_with_retry(self, func: Callable, *args, **kwargs):
        """Execute a function with retries based on retry configuration"""
        config = self.retry_config
        last_error = None

        for retry in range(config.max_retries):
            try:
                if config.timeout:
                    return await asyncio.wait_for(
                        func(*args, **kwargs), timeout=config.timeout
                    )
                return await func(*args, **kwargs)

            except Exception as error:
                last_error = error
                is_retryable = config.is_retryable(error)

                if not is_retryable or retry >= config.max_retries - 1:
                    break

                logger.warning(
                    f"retryable error in attempt {retry + 1}/{config.max_retries}: {str(error)}"
                )
                await config.backoff(retry)

        # If we get here, all retries failed or error wasn't retryable
        error_message = f"Operation failed: {str(last_error)}"
        logger.error(error_message)
        raise AgentError(error_message, {"original_error": str(last_error)})

    async def process_message(
        self,
        message: str,
        streaming: bool = False,
        context_update: Optional[Dict[str, Any]] = None,
        force_mode: Optional[AgentMode] = None,
    ) -> Union[Dict[str, str], AsyncGenerator[str, None]]:
        """Process a user message and return the agent's response
        
        Args:
            message: The user's message
            streaming: Whether to stream the response
            context_update: Additional context to update
            force_mode: Force a specific mode ('normal' or 'deep'), otherwise auto-detect
        """
        if context_update:
            self.context.update(context_update)

        self.trace_id = gen_trace_id()
        logger.debug(f"Generated trace ID: {self.trace_id}")

        # Detect mode based on message content or use forced mode
        mode = force_mode or detect_mode(message)
        logger.info(f"Using {mode} mode for processing message")
        
        # Select instructions based on mode
        instructions = self.instructions_deep if mode == "deep" else self.instructions_normal
        
        # Adjust model settings based on mode and model type
        # GPT-5 models don't support temperature but support reasoning
        is_gpt5_model = "gpt-5" in self.model.lower()
        
        if mode == "deep":
            # Deep mode: for GPT-5 use reasoning, for others use higher temperature
            if is_gpt5_model:
                from agents.model_settings import Reasoning
                model_settings = ModelSettings(
                    max_tokens=min(self.max_tokens, 15000),  # More tokens for comprehensive analysis
                    reasoning=Reasoning(effort="high")  # High reasoning effort for deep analysis
                )
            else:
                model_settings = ModelSettings(
                    temperature=min(self.temperature * 1.5, 0.7),  # Higher temp for exploration
                    max_tokens=min(self.max_tokens, 15000),
                )
            agent_name = "DeepAnalyst"
        else:
            # Normal mode: standard settings
            if is_gpt5_model:
                from agents.model_settings import Reasoning
                model_settings = ModelSettings(
                    max_tokens=min(self.max_tokens, 10000),
                    reasoning=Reasoning(effort="medium")  # Medium reasoning for normal mode
                )
            else:
                model_settings = ModelSettings(
                    temperature=self.temperature,
                    max_tokens=min(self.max_tokens, 10000),
                )
            agent_name = "Assistant"

        agent = OpenAIAgent(
            name=agent_name,
            instructions=instructions,
            mcp_servers=[self.mcp_server],
            model=self._get_model_instance(),
            model_settings=model_settings,
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
                    if hasattr(result, "context") and result.context:
                        self.context.update(result.context)

                    trace_url = self.get_trace_url()

                    if streaming:

                        async def stream_response():
                            yield f"[{mode.upper()} MODE] View trace: {trace_url}\n\n"
                            for chunk in result.final_output.split():
                                yield chunk + " "

                        return stream_response()
                    else:
                        return {
                            "output": result.final_output, 
                            "trace_url": trace_url,
                            "mode": mode
                        }
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    raise AgentError(f"Failed to process message: {str(e)}")

    def get_trace_url(self) -> str:
        """Get the URL for the current trace."""
        return f"https://platform.openai.com/traces/trace?trace_id={self.trace_id}"

    def clear_cache(self) -> None:
        """Clear the MCP server cache."""
        if (
            not self.enable_mcp_cache
            or not hasattr(self, "mcp_server")
            or self.mcp_server is None
        ):
            logger.info(
                "MCP caching is disabled or server not initialized, nothing to clear."
            )
            return

        if hasattr(self.mcp_server, "invalidate_tools_cache"):
            self.mcp_server.invalidate_tools_cache()
            logger.info("MCP server tools cache invalidated successfully.")
        else:
            self.mcp_server = None
            logger.info("MCP server reset. Cache will be rebuilt on next request.")


def create_agent_manager(
    agent_config_override: Optional[Dict[str, Any]] = None, **kwargs
) -> AgentManager:
    """
    Create an AgentManager instance with dual-mode support.
    It fetches its core configuration (model, temp, tokens, mcp_url)
    from Settings, but allows overrides.

    Args:
        agent_config_override: Optional dict to override specific agent config values
                               (model, temperature, max_tokens, mcp_sse_url).
        **kwargs: Additional keyword arguments to pass directly to AgentManager constructor
                  (e.g., instructions, instructions_normal, instructions_deep, 
                   retry_config, context, enable_mcp_cache).
    """

    config = Settings().get_openai_config()

    if agent_config_override:
        config.update(agent_config_override)

    return AgentManager(**{**config, **kwargs})
