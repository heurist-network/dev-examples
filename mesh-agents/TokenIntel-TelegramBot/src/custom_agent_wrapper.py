import httpx
from typing import Any, Dict, List, Optional
from .model_config import get_model_config
import logging

# Set up logging
logger = logging.getLogger(__name__)


class CustomAgentWrapper:
    """Custom agent wrapper that uses our multi-provider configuration"""

    def __init__(self, name: str, instructions: str, tools: Optional[List] = None):
        self.name = name
        self.instructions = instructions
        self.tools = tools or []
        self.config = get_model_config()

        # Agent type mappings for better organization
        self.agent_types = {
            "twitter_symbol": "twitter symbol searcher",
            "twitter_account": "twitter account searcher",
            "web3_info": "web3 info searcher",
            "webpage_crawler": "webpage crawler",
            "solana_wallet": "solana wallet analyzer",
            "token_clusters": "token clusters analyzer",
        }

    async def run_with_tools(self, param: str) -> Dict[str, Any]:
        """Run the agent with tools simulation"""
        try:
            context = self._parse_parameters(param)
            prompt = self._generate_prompt(context, param)
            response = await self._make_api_call(prompt)

            return {"final_output": response, "last_agent": self, "status": "success"}

        except Exception as e:
            logger.error(f"Error in {self.name}: {e}")
            error_response = self._generate_error_response()
            return {
                "final_output": error_response,
                "last_agent": self,
                "status": "error",
                "error": str(e),
            }

    def _parse_parameters(self, param: str) -> Dict[str, str]:
        """Parse input parameters into a context dictionary"""
        context = {}
        if not param:
            return context

        # Handle both comma-separated and colon-separated formats
        parts = param.split(",")
        for part in parts:
            part = part.strip()
            if ":" in part:
                key, value = part.split(":", 1)
                context[key.strip().lower()] = value.strip()
            else:
                # Handle simple parameters without colons
                context["query"] = part

        return context

    def _generate_prompt(self, context: Dict[str, str], original_param: str) -> str:
        """Generate appropriate prompt based on agent type and context"""
        agent_name_lower = self.name.lower()

        # Twitter symbol analysis
        if any(x in agent_name_lower for x in ["twitter symbol", "symbol searcher"]):
            symbol = context.get("symbol") or context.get("query", "unknown")
            return f"Analyze social media sentiment for cryptocurrency symbol: {symbol}. Provide a brief summary of recent mentions, sentiment trends, and key insights."

        # Twitter account analysis
        elif any(
            x in agent_name_lower for x in ["twitter account", "account searcher"]
        ):
            username = context.get("username") or context.get("query", "unknown")
            return f"Analyze Twitter activity for username: {username}. Summarize recent tweets, engagement patterns, and notable activity."

        # Web3 information search
        elif any(x in agent_name_lower for x in ["web3 info", "info searcher"]):
            symbol = context.get("symbol") or context.get("query", "unknown")
            return f"Search for comprehensive information about cryptocurrency: {symbol}. Include recent news, price movements, development updates, and market analysis."

        # Webpage crawler
        elif any(x in agent_name_lower for x in ["webpage", "crawler"]):
            url = context.get("url") or original_param.replace("check url:", "").strip()
            return f"Analyze the website: {url}. Provide a comprehensive summary including the site's purpose, key information, credibility assessment, and relevant details."

        # Solana wallet analyzer
        elif any(x in agent_name_lower for x in ["solana wallet", "wallet analyzer"]):
            token_address = (
                context.get("token address")
                or context.get("address")
                or context.get("query", "unknown")
            )
            return f"Analyze Solana token holders for address: {token_address}. Provide detailed insights into holder distribution, whale activity, and significant wallet patterns."

        # Token clusters analyzer
        elif any(
            x in agent_name_lower for x in ["token clusters", "clusters analyzer"]
        ):
            token_address = (
                context.get("token address")
                or context.get("address")
                or context.get("query", "unknown")
            )
            return f"Analyze wallet clusters for token address: {token_address}. Identify behavioral patterns, cluster relationships, and notable holder dynamics."

        # Default fallback
        else:
            query = context.get("query") or original_param
            return f"Provide a comprehensive analysis for the following request: {query}. Include relevant insights and actionable information."

    def _generate_error_response(self) -> str:
        """Generate a user-friendly error response"""
        agent_type = "analysis"
        if "twitter" in self.name.lower():
            agent_type = "social media analysis"
        elif "web3" in self.name.lower() or "solana" in self.name.lower():
            agent_type = "blockchain analysis"
        elif "webpage" in self.name.lower():
            agent_type = "website analysis"

        return f"🔧 {agent_type.title()} Service Unavailable\n\n• The {agent_type} service is currently experiencing issues\n• Please try again in a few moments\n• Contact support if the issue persists\n\n💡 We're working to resolve this quickly"

    async def _make_api_call(self, prompt: str) -> str:
        """Make API call using the configured provider"""
        try:
            if self.config.provider == "heurist":
                return await self._call_heurist_api(prompt)
            else:
                # For other providers, use model manager
                return await self._call_generic_api(prompt)
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise

    async def _call_generic_api(self, prompt: str) -> str:
        """Call API using generic model manager"""
        try:
            from .model_config import get_model_manager

            manager = get_model_manager()
            response = await manager.complete([{"role": "user", "content": prompt}])
            return self._format_response(response)
        except Exception as e:
            logger.error(f"Generic API call failed: {e}")
            raise

    async def _call_heurist_api(self, prompt: str) -> str:
        """Call Heurist API with proper error handling and formatting"""
        url = "https://llm-gateway.heurist.xyz/v1/chat/completions"

        system_message = self._create_system_message()

        payload = {
            "max_tokens": min(self.config.max_tokens, 800),
            "stream": False,
            "model": self.config.model,
            "temperature": getattr(self.config, "temperature", 0.3),
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

                response_data = response.json()

                if "choices" in response_data and response_data["choices"]:
                    content = response_data["choices"][0]["message"]["content"]
                    return self._format_response(content)
                else:
                    raise ValueError("No valid response from API")

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error calling Heurist API: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.TimeoutException:
            logger.error("Timeout calling Heurist API")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Heurist API: {e}")
            raise

    def _create_system_message(self) -> str:
        """Create a comprehensive system message"""
        base_instructions = f"{self.instructions}\n\n"

        formatting_rules = """
            You are a specialized assistant for cryptocurrency and blockchain analysis. Follow these formatting guidelines:

            RESPONSE FORMAT:
            1. Start with an emoji header (📊, 🔍, 💰, etc.)
            2. Use bullet points with • symbol (never *)
            3. Keep responses under 600 characters for mobile
            4. NO bold formatting with **
            5. Include strategic emojis for readability
            6. End with a brief insight or conclusion

            CONTENT GUIDELINES:
            - Provide accurate, actionable information
            - Focus on key insights and trends
            - Use clear, concise language
            - Include relevant context when possible
            - Maintain professional but accessible tone
        """

        return base_instructions + formatting_rules

    def _format_response(self, content: str) -> str:
        """Format response for optimal Telegram display"""
        if not content or not content.strip():
            return "📊 Analysis Completed\n\n• Processing completed successfully\n• No specific insights generated\n\n💡 Try a more specific query"

        content = content.strip()

        # Clean up formatting
        content = self._clean_formatting(content)

        # Ensure proper structure
        content = self._ensure_proper_structure(content)

        # Limit length
        content = self._limit_length(content)

        return content

    def _clean_formatting(self, content: str) -> str:
        """Clean up text formatting"""
        # Remove bold formatting
        content = content.replace("**", "").replace("__", "")

        # Standardize bullet points
        content = content.replace("*   ", "• ")
        content = content.replace("* ", "• ")
        content = content.replace("- ", "• ")

        # Clean up multiple newlines
        while "\n\n\n" in content:
            content = content.replace("\n\n\n", "\n\n")

        return content

    def _ensure_proper_structure(self, content: str) -> str:
        """Ensure content has proper structure with emoji header"""
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        # Add emoji header if missing
        if lines and not any(
            emoji in lines[0]
            for emoji in [
                "🔍",
                "📊",
                "💡",
                "⚠️",
                "🚀",
                "📈",
                "📉",
                "💰",
                "🔥",
                "🌐",
                "📱",
                "🎯",
            ]
        ):
            # Choose appropriate emoji based on agent type
            if "twitter" in self.name.lower():
                emoji_header = "🐦 Social Analysis"
            elif "web3" in self.name.lower() or "solana" in self.name.lower():
                emoji_header = "⛓️ Blockchain Analysis"
            elif "webpage" in self.name.lower():
                emoji_header = "🌐 Website Analysis"
            else:
                emoji_header = "📊 Analysis"

            lines.insert(0, emoji_header)
            lines.insert(1, "")  # Add spacing

        return "\n".join(lines)

    def _limit_length(self, content: str, max_length: int = 600) -> str:
        """Limit content length while preserving structure"""
        if len(content) <= max_length:
            # Ensure it ends with conclusion
            if not any(
                keyword in content.lower()
                for keyword in ["💡", "🎯", "conclusion", "insight"]
            ):
                content += "\n\n💡 Analysis complete"
            return content

        # Truncate at sentence or line boundary
        truncated = content[: max_length - 50]

        # Find last complete line
        last_newline = truncated.rfind("\n")
        if last_newline > max_length * 0.7:  # If we can keep most content
            truncated = truncated[:last_newline]
        else:
            # Find last sentence
            last_period = truncated.rfind(".")
            if last_period > max_length * 0.5:
                truncated = truncated[: last_period + 1]

        truncated += "\n\n💡 Full analysis available on request"
        return truncated


class MockRunner:
    """Mock runner to simulate the agents library Runner"""

    @staticmethod
    async def run(
        starting_agent: CustomAgentWrapper, input_param: str, **kwargs
    ) -> Dict[str, Any]:
        """Run the custom agent with proper error handling"""
        if not isinstance(starting_agent, CustomAgentWrapper):
            raise TypeError("starting_agent must be a CustomAgentWrapper instance")

        try:
            return await starting_agent.run_with_tools(input_param)
        except Exception as e:
            logger.error(f"MockRunner error: {e}")
            return {
                "final_output": "🔧 Service Temporarily Unavailable\n\n• Analysis could not be completed\n• Please try again shortly\n\n💡 Contact support if issues persist",
                "last_agent": starting_agent,
                "status": "error",
                "error": str(e),
            }


def create_custom_agent(
    name: str, instructions: str, tools: Optional[List] = None
) -> CustomAgentWrapper:
    """
    Create a custom agent that works with our multi-provider setup

    Args:
        name: Agent name/identifier
        instructions: System instructions for the agent
        tools: Optional list of tools (currently unused but kept for compatibility)

    Returns:
        CustomAgentWrapper instance
    """
    if not name or not instructions:
        raise ValueError("Both name and instructions are required")

    return CustomAgentWrapper(name, instructions, tools)


# Utility functions for common agent types
def create_twitter_symbol_agent(instructions: str = "") -> CustomAgentWrapper:
    """Create a Twitter symbol analysis agent"""
    default_instructions = (
        "Analyze social media sentiment and mentions for cryptocurrency symbols."
    )
    final_instructions = instructions or default_instructions
    return create_custom_agent("twitter symbol searcher", final_instructions)


def create_web3_info_agent(instructions: str = "") -> CustomAgentWrapper:
    """Create a Web3 information search agent"""
    default_instructions = (
        "Search and analyze cryptocurrency and blockchain information."
    )
    final_instructions = instructions or default_instructions
    return create_custom_agent("web3 info searcher", final_instructions)


def create_solana_wallet_agent(instructions: str = "") -> CustomAgentWrapper:
    """Create a Solana wallet analysis agent"""
    default_instructions = "Analyze Solana wallet addresses and token holder patterns."
    final_instructions = instructions or default_instructions
    return create_custom_agent("solana wallet analyzer", final_instructions)
