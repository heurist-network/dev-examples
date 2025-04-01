import os
from functools import wraps
from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
import httpx
from dotenv import load_dotenv

load_dotenv()

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
    # fromDate: Optional[int]
    # toDate: Optional[int]

class HeuristAPIError(Exception):
    """Base exception for Heurist API errors"""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)

def post(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        payload = await func(self, *args, **kwargs)
        assert isinstance(self,HeuAgentApiWrapper)
        json = {
            "api_key": self.heu_key,
            "agent_id": self.__class__.__name__,
            "input": {
                "tool": func.__name__,
                "tool_arguments": payload,
                "raw_data_only": True
            }
        }
        return await self.request(method="POST", json=json)
    return wrapper

class HeuAgentApiWrapper:
    base_url = "https://sequencer-v2.heurist.xyz/mesh_request"
    heu_key = os.environ.get("HEURIST_KEY")
    timeout = 10

    async def request(
        self,
        method: Literal["GET", "POST"],
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
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
                    **kwargs
                )
                # response.raise_for_status()
                print(response)

                match response.status_code:
                    case 200:
                        return response.json()

                    case _:
                        raise HeuristAPIError(
                            "something wrong with heurist api",
                            response.status_code,
                            response.json()
                        )

            except Exception as e:
                # print(f"HTTP request failed: {str(e)}")
                print(f"Unknown error occurs {e}")
                raise

class ExaSearchAgent(HeuAgentApiWrapper):
    @post
    async def exa_web_search(self, args: WebSearch):
        '''
        Search for webpages related to a query using Exa search.
        '''
        return args

    @post
    async def exa_answer_question(self, args: WebSearch):
        '''
        Get a direct answer to a question using Exa's answer API.
        '''
        return args


class ElfaTwitterIntelligenceAgent(HeuAgentApiWrapper):
    timeout=30

    @post
    async def search_mentions(self, args: SearchMentions):
        '''
        Search crypto token name/symbol on twitter
        '''

        return {**args,"days_ago":7,"limit":20}

    @post
    async def search_account(self, args: SearchAccount):
        '''
        Search Twitter accounts
        '''
        return {**args,"days_ago":7,"limit":20}

    @post
    async def get_trending_tokens(self, args: TrendingTokens):
        '''
        Get trending tokens from Twitter
        '''
        print(args)
        return {"time_window":"24h"}

class FirecrawlSearchAgent(HeuAgentApiWrapper):
    timeout = 200
    @post
    async def firecrawl_web_search(self, args: WebSearch):
        '''
        Perform web search using Firecrawl
        '''
        return args

    @post
    async def firecrawl_extract_web_data(self, args: WebDataExtraction):
        '''
        Extract data from web pages using Firecrawl
        '''
        return args

class MetaSleuthSolTokenWalletClusterAgent(HeuAgentApiWrapper):

    timeout=100

    @post
    async def fetch_token_clusters(self, args: SearchTokenAddressClusters):
        '''
        find the cluters of given address
        '''
        # print(args)
        return {**args,"page":1,"page_size":100}

class SolWalletAgent(HeuAgentApiWrapper):
    timeout=120
    @post
    async def analyze_common_holdings_of_top_holders(self, args: ScanTokenAddress):
        '''Analyze common token holdings among top wallet holders'''
        print(args)
        return {**args,"top_n":30}

class TwitterInsightAgent(HeuAgentApiWrapper):
    @post
    async def get_smart_followers_history(self, args: SmartFollowers):
        '''
        Get historical data about smart followers
        '''
        return args

    @post
    async def get_smart_mentions_feed(self, args: SmartMentions):
        '''
        Get feed of smart mentions
        '''

        d = {"username":args["username"],"limit":str(args["limit"])}
        return d
