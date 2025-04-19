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
        print(f"📤 Request Payload:\n{json}\n")

        return await self.request(method="POST", json=json)

    return wrapper


# ---------- Base Wrapper ----------
class HeuAgentApiWrapper:
    base_url = "https://sequencer-v2.heurist.xyz/mesh_request"
    heu_key = os.environ.get("HEURIST_KEY")
    timeout = 10

    async def request(
        self,
        method: Literal["GET", "POST"],
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=self.base_url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs,
                )

                print(f"Response Status Code: {response.status_code}")
                print(f"📨 Response Content:\n{response.text}\n")

                if response.status_code == 200:
                    return response.json()
                else:
                    raise HeuristAPIError(
                        message="Something went wrong with the Heurist API",
                        status_code=response.status_code,
                        response=response.text,
                    )

            except Exception as e:
                print(f"Unknown error occurred: {str(e)}\n")
                raise


# ---------- Agent Classes ----------
class ExaSearchAgent(HeuAgentApiWrapper):
    @post
    async def exa_web_search(self, args: WebSearch):
        return args

    @post
    async def exa_answer_question(self, args: WebSearch):
        return args


class ElfaTwitterIntelligenceAgent(HeuAgentApiWrapper):
    timeout = 30

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
    timeout = 200

    @post
    async def firecrawl_web_search(self, args: WebSearch):
        return args

    @post
    async def firecrawl_extract_web_data(self, args: WebDataExtraction):
        return args


class MetaSleuthSolTokenWalletClusterAgent(HeuAgentApiWrapper):
    timeout = 100

    @post
    async def fetch_token_clusters(self, args: SearchTokenAddressClusters):
        return {**args, "page": 1, "page_size": 100}


class SolWalletAgent(HeuAgentApiWrapper):
    timeout = 120

    @post
    async def analyze_common_holdings_of_top_holders(self, args: ScanTokenAddress):
        return {**args, "top_n": 30}


class TwitterInsightAgent(HeuAgentApiWrapper):
    @post
    async def get_smart_followers_history(self, args: SmartFollowers):
        return args

    @post
    async def get_smart_mentions_feed(self, args: SmartMentions):
        return {"username": args["username"], "limit": str(args["limit"])}
