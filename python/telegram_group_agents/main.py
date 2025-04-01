import os
import anyio
from agents import (
    Agent,
    function_tool,
    set_tracing_disabled,
    Runner
)
from pydantic import BaseModel
from dotenv import load_dotenv
from tools import ElfaTwitterIntelligenceAgent, ExaSearchAgent, MetaSleuthSolTokenWalletClusterAgent, SolWalletAgent, FirecrawlSearchAgent
import re
from typing import Optional, Dict, Any
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
from telebot.handler_backends import State, StatesGroup
import httpx

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
HEURIST_KEY = os.environ.get("HEURIST_API_KEY")
# set_tracing_disabled(True)

elfa = ElfaTwitterIntelligenceAgent()
exa = ExaSearchAgent()
crawl = FirecrawlSearchAgent()
cluster = MetaSleuthSolTokenWalletClusterAgent()
helius = SolWalletAgent()

class SearchResult(BaseModel):
    brief_summary:str

class TokenInfo:
    def __init__(self):
        self.tokens = {}  # Container for storing token information

    async def check_token_address(self, address: str) -> Optional[Dict[str, Any]]:
        # Try different chains
        chains = ["solana", "bsc", "base", "eth"]

        for chain in chains:
            url = f"https://api.dexscreener.com/tokens/v1/{chain}/{address}"
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        pair = data[0]
                        return self._extract_token_info(pair)
            except Exception:
                continue
        return None

    async def search_token_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                data = response.json()
                if "pairs" in data and data["pairs"]:
                    pair = data["pairs"][0]
                    return self._extract_token_info(pair)
        except Exception:
            return None
        return None

    def _extract_token_info(self, pair: Dict) -> Dict[str, Any]:
        # Extract token information
        info = pair.get("info", {})
        website = next((w["url"] for w in info.get("websites", []) if w.get("label") == "Website"), None)
        twitter = next((s["url"] for s in info.get("socials", []) if s.get("type") == "twitter"), None)
        
        token_info = {
            "address": pair["baseToken"]["address"],
            "symbol": pair["baseToken"]["symbol"],
            "chain": pair["chainId"],
            "createdAt": datetime.fromtimestamp(pair.get("pairCreatedAt", 0)/1000).strftime('%Y-%m-%d %H:%M:%S'),
            "marketCap": pair.get("marketCap"),
            "website": website,
            "twitter": twitter
        }
        
        # Store in container
        self.tokens[pair["baseToken"]["address"]] = token_info
        return token_info

twitter_search_agent = Agent(
    name="twitter symbol searcher",
    instructions="Search tweets for the given symbol/token address. Answer user questions first; if none, provide a concise bullet-point summary in Chinese.there is no need to add styles such as ** or ##.",
    model="gpt-4o",
    tools=[function_tool(elfa.search_mentions)]
)

twitter_account_agent = Agent(
    name="twitter account searcher",
    instructions="Get tweets for the given username. Answer user questions first; if none, provide a concise bullet-point summary of this account's tweets in Chinese.there is no need to add styles such as ** or ##.",
    model="gpt-4o",
    tools=[function_tool(elfa.search_account)]
)

exa_agent = Agent(
    name="web3 info searcher",
    instructions="search the info about given crypto symbol. Answer user questions first; if none, briefly summarize in Chinese.there is no need to add styles such as ** or ##.",
    model="gpt-4o",
    tools=[function_tool(exa.exa_web_search), function_tool(exa.exa_answer_question)]
)

cluster_agent = Agent(
    name="token clusters analyzer",
    instructions="Extract the token address from the user's query. Identify and explain significant holder clusters in Chinese. Present the findings in structured format. Use the available data only for the final analysis.",
    model="gpt-4o",
    tools=[function_tool(cluster.fetch_token_clusters)]
)

wallet_agent = Agent(
    name="solana wallet analyzer",
    instructions="Extract the token address from the user's query. Provides insights into the top most valuable tokens that are held by the token holders in Chinese.",
    model="gpt-4o",
    tools=[function_tool(helius.analyze_common_holdings_of_top_holders)]
)

crawl_agent = Agent(
    name="webpage crawler",
    instructions="Crawl the webpage and extract the data, Briefly summarize the purpose of this website in Chinese.",
    model="gpt-4o",
    tools=[function_tool(crawl.firecrawl_extract_web_data)]
)

bot = AsyncTeleBot(os.environ.get("TELEGRAM_TOKEN"))
token_tracker = TokenInfo()

def task_wrapper(agent, param, message):
    async def task():
        try:
            result = await Runner.run(agent, param)           
            if result and result.final_output:
                prefix = ""
                if result.last_agent.name == "twitter symbol searcher":
                    prefix = "🔷 社交媒体舆情扫描 🔷\n"   
                elif result.last_agent.name == "twitter account searcher":
                    prefix = "🔷 官方推文关键事件 🔷\n"
                elif result.last_agent.name == "web3 info searcher":
                    prefix = "🔷 搜索引擎数据扫描 🔷\n"
                elif result.last_agent.name == "webpage crawler":
                    prefix = "🔷 目标网站数据捕获 🔷\n"
                # elif result.last_agent.name == "token clusters analyzer":
                #     prefix = "🔷 链上钱包集群分析 🔷\n"
                elif result.last_agent.name == "solana wallet analyzer":
                    prefix = "🔷 持仓关联资产挖掘 🔷\n"
                    output = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', result.final_output)
                    final_message = prefix + f"<blockquote>{output}</blockquote>"
                    await bot.reply_to(message, final_message, parse_mode="HTML")
                    return
                await bot.reply_to(message, prefix + result.final_output)                
        except Exception as e:
            print(f"Error in task: {e}")
    return task

@bot.message_handler(func=lambda message: True)
async def msg_entry(message):
    try:
        if str(message.chat.id) != os.environ.get("TELEGRAM_CHAT_ID"):
            return

        message_text = message.text
        symbol_match = re.search(r'\$(\w+)', message_text)
        sol_address_match = re.search(r'([A-Za-z0-9]{32,44}(?:pump|sol)?)', message_text)
        evm_address_match = re.search(r'(0x[A-Fa-f0-9]{40})', message_text)

        token_info = None
        if symbol_match:
            symbol = symbol_match.group(1)
            token_info = await token_tracker.search_token_symbol(symbol)
        elif sol_address_match or evm_address_match:
            address = sol_address_match.group(1) if sol_address_match else evm_address_match.group(1)
            token_info = await token_tracker.check_token_address(address)

        if not token_info:
            return

        plan_message = "AI 调研计划生成\n"
        plan_items = []
        tasks = []
        query_content = re.sub(r'\$\w+|[A-Za-z0-9]{43,44}|0x[A-Fa-f0-9]{40}', '', message_text).strip()

        # 1. Twitter search task
        twitter_search_msg = f"symbol:{token_info['symbol']},token address:{token_info['address']}"
        if query_content:
            twitter_search_msg += f",query:{query_content}"
        tasks.append(task_wrapper(twitter_search_agent, twitter_search_msg, message))
        plan_items.append("🔹 社交媒体舆情扫描，激活 twitter agent 智能解析...")

        # 2. Website crawling task
        if token_info.get('website'):
            tasks.append(task_wrapper(crawl_agent, f"check url:{token_info['website']}", message))
            plan_items.append("🔹 目标网站数据捕获，释放 crawl agent 深度爬取...")

        # 3. Twitter account analysis task
        if token_info.get('twitter'):
            twitter_username = re.search(r'twitter\.com/([^/]+)', token_info['twitter'])
            if twitter_username:
                username = twitter_username.group(1)
                tasks.append(task_wrapper(twitter_account_agent, f"username:{username}", message))
                plan_items.append("🔹 官方推文关键事件，激活 twitter agent 信息雷达...")

        # 4. Solana chain related tasks
        if token_info.get('chain') == 'solana':
            # tasks.append(task_wrapper(cluster_agent, f"token address:{token_info['address']}", message))
            tasks.append(task_wrapper(wallet_agent, f"token address:{token_info['address']}", message))
            # plan_items.append("🔹 链上钱包集群分析，启动 cluster agent 区块链显微镜...")
            plan_items.append("🔹 持仓关联资产挖掘，调用 wallet agent 扫描 Top Holder...")

        # 5. Exa search task
        try:
            created_at = datetime.strptime(token_info['createdAt'], '%Y-%m-%d %H:%M:%S')
            days_since_creation = (datetime.now() - created_at).days
            market_cap = float(token_info.get('marketCap', '0'))

            if days_since_creation > 30 and market_cap > 10000000:
                exa_msg = f"symbol:{token_info['symbol']}"
                if query_content:
                    exa_msg += f",query:{query_content}"
                tasks.append(task_wrapper(exa_agent, exa_msg, message))
                plan_items.append("🔹 搜索引擎数据扫描，启动 exa agent 查阅新闻...")
        except (ValueError, TypeError) as e:
            print(f"Error processing Exa search task: {e}")

        await bot.reply_to(message, plan_message + "\n".join(plan_items))

        if tasks:
            try:
                async with anyio.create_task_group() as tg:
                    for task in tasks:
                        tg.start_soon(task)
            except Exception as e:
                print(f"Error in task group: {e}")

    except Exception as e:
        print(f"Error in message handler: {e}")

async def main():
    try:
        print("Bot started...")
        await bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Error in main loop: {e}")

if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        print("Bot stopped gracefully")
    except Exception as e:
        print(f"Fatal error: {e}")


