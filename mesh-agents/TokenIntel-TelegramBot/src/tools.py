import os
from functools import wraps
from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
import httpx
from dotenv import load_dotenv

load_dotenv()


# ---------- Request Models ----------
class SearchMentions(TypedDict):
    keywords: List[str]


class SearchAccount(TypedDict):
    username: str


class TrendingTokens(TypedDict):
    time_window: str


class WebSearch(TypedDict):
    search_term: str


class WebDataExtraction(TypedDict):
    urls: List[str]
    extraction_prompt: str
    enable_web_search: bool


class SearchTokenAddressClusters(TypedDict):
    address: str


class ScanTokenAddress(TypedDict):
    token_address: str


class SmartFollowers(TypedDict):
    username: str
    timeframe: str


class SmartMentions(TypedDict):
    username: str
    limit: int


# ---------- Custom Exception ----------
class HeuristAPIError(Exception):
    """Base exception for Heurist API errors"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


# ---------- Decorator for POST ----------
def post(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        payload = await func(self, *args, **kwargs)
        assert isinstance(self, HeuAgentApiWrapper)

        json = {
            "api_key": self.heu_key,
            "agent_id": self.__class__.__name__,
            "input": {
                "tool": func.__name__,
                "tool_arguments": payload,
                "raw_data_only": True,
            },
        }

        print(f"\n🔧 Preparing POST call for tool: {func.__name__}")
        print(f"📤 Agent: {self.__class__.__name__}")
        print(f"🎯 Tool arguments: {str(payload)[:200]}...")

        return await self.request(method="POST", json=json)

    return wrapper


# ---------- Base Wrapper ----------
class HeuAgentApiWrapper:
    base_url = "https://sequencer-v2.heurist.xyz/mesh_request"
    heu_key = os.environ.get("HEURIST_KEY")
    timeout = 10

    def __init__(self):
        if not self.heu_key:
            raise ValueError("HEURIST_KEY is required in environment variables")

    async def request(
        self,
        method: Literal["GET", "POST"],
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                print(f"🌐 Making {method} request to Heurist API...")

                response = await client.request(
                    method=method,
                    url=self.base_url,
                    params=params,
                    json=json,
                    headers=headers,
                    **kwargs,
                )

                print(f"📊 Response Status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Request successful - received {len(str(result))} chars")
                    return result
                else:
                    error_text = response.text[:500]  # Limit error text length
                    print(f"❌ API Error: {response.status_code}")
                    print(f"📝 Error details: {error_text}")
                    raise HeuristAPIError(
                        message=f"Heurist API error: {response.status_code}",
                        status_code=response.status_code,
                        response=error_text,
                    )

            except httpx.TimeoutException:
                print(f"⏰ Request timeout after {self.timeout}s")
                raise HeuristAPIError(
                    message=f"Request timeout after {self.timeout} seconds",
                    status_code=408,
                )
            except httpx.RequestError as e:
                print(f"🌐 Network error: {str(e)}")
                raise HeuristAPIError(
                    message=f"Network error: {str(e)}",
                    status_code=500,
                )
            except Exception as e:
                print(f"💥 Unexpected error: {str(e)}")
                raise HeuristAPIError(
                    message=f"Unexpected error: {str(e)}",
                    status_code=500,
                )


# ---------- Agent Classes ----------
class ExaSearchAgent(HeuAgentApiWrapper):
    """Agent for web search and question answering"""

    def __init__(self):
        super().__init__()
        self.timeout = 30

    @post
    async def exa_web_search(self, args: WebSearch):
        return args

    @post
    async def exa_answer_question(self, args: WebSearch):
        return args


class ElfaTwitterIntelligenceAgent(HeuAgentApiWrapper):
    """Agent for Twitter intelligence and social media analysis"""

    def __init__(self):
        super().__init__()
        self.timeout = 30

    @post
    async def search_mentions(self, args: SearchMentions):
        return {**args, "days_ago": 7, "limit": 20}

    @post
    async def search_account(self, args: SearchAccount):
        return {**args, "days_ago": 7, "limit": 20}

    @post
    async def get_trending_tokens(self, args: TrendingTokens):
        return {"time_window": "24h"}


class FirecrawlSearchAgent(HeuAgentApiWrapper):
    """Agent for web crawling and data extraction"""

    def __init__(self):
        super().__init__()
        self.timeout = 200  # Web crawling can take longer

    @post
    async def firecrawl_web_search(self, args: WebSearch):
        return args

    @post
    async def firecrawl_extract_web_data(self, args: WebDataExtraction):
        return args


class MetaSleuthSolTokenWalletClusterAgent(HeuAgentApiWrapper):
    """Agent for analyzing Solana token wallet clusters"""

    def __init__(self):
        super().__init__()
        self.timeout = 100

    @post
    async def fetch_token_clusters(self, args: SearchTokenAddressClusters):
        return {**args, "page": 1, "page_size": 100}


class SolWalletAgent(HeuAgentApiWrapper):
    """Agent for Solana wallet analysis and holder insights"""

    def __init__(self):
        super().__init__()
        self.timeout = 120

    @post
    async def analyze_common_holdings_of_top_holders(self, args: ScanTokenAddress):
        return {**args, "top_n": 30}


class TwitterInsightAgent(HeuAgentApiWrapper):
    """Agent for advanced Twitter insights and analytics"""

    def __init__(self):
        super().__init__()
        self.timeout = 60

    @post
    async def get_smart_followers_history(self, args: SmartFollowers):
        return args

    @post
    async def get_smart_mentions_feed(self, args: SmartMentions):
        return {"username": args["username"], "limit": str(args["limit"])}


# ---------- Utility Functions ----------
def validate_tools_configuration():
    """Validate that all required environment variables are set"""
    heurist_key = os.environ.get("HEURIST_KEY")

    if not heurist_key:
        raise ValueError(
            "HEURIST_KEY is required for intelligence tools. "
            "Get your API key from https://heurist.xyz"
        )

    print("✅ Tools configuration validated")
    return True


def get_available_tools():
    """Get list of available intelligence tools"""
    return [
        "ElfaTwitterIntelligenceAgent - Twitter sentiment and social media analysis",
        "ExaSearchAgent - Web search and question answering",
        "FirecrawlSearchAgent - Website crawling and data extraction",
        "MetaSleuthSolTokenWalletClusterAgent - Solana token wallet cluster analysis",
        "SolWalletAgent - Solana wallet analysis and holder insights",
        "TwitterInsightAgent - Advanced Twitter analytics and insights",
    ]


# Initialize and validate tools on import
if __name__ == "__main__":
    try:
        validate_tools_configuration()
        tools = get_available_tools()
        print("\n🛠️  Available Intelligence Tools:")
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool}")
    except Exception as e:
        print(f"❌ Tools validation failed: {e}")
else:
    # Validate when imported
    try:
        validate_tools_configuration()
    except Exception as e:
        print(f"⚠️  Tools configuration warning: {e}")
        print("Some intelligence features may not work properly")
