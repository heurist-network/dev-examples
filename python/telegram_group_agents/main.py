import os
import anyio
from agents import Agent, function_tool, set_tracing_disabled, Runner
from pydantic import BaseModel
from dotenv import load_dotenv
from tools import (
    ElfaTwitterIntelligenceAgent,
    ExaSearchAgent,
    MetaSleuthSolTokenWalletClusterAgent,
    SolWalletAgent,
    FirecrawlSearchAgent,
)
import re
from typing import Optional, Dict, Any
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
import httpx

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
HEURIST_KEY = os.environ.get("HEURIST_KEY")
# set_tracing_disabled(True)

elfa = ElfaTwitterIntelligenceAgent()
exa = ExaSearchAgent()
crawl = FirecrawlSearchAgent()
cluster = MetaSleuthSolTokenWalletClusterAgent()
helius = SolWalletAgent()


class SearchResult(BaseModel):
    brief_summary: str


class TokenInfo:
    def __init__(self):
        self.tokens = {}

    async def check_token_address(self, address: str) -> Optional[Dict[str, Any]]:
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
        info = pair.get("info", {})
        website = next(
            (w["url"] for w in info.get("websites", []) if w.get("label") == "Website"),
            None,
        )
        twitter = next(
            (s["url"] for s in info.get("socials", []) if s.get("type") == "twitter"),
            None,
        )

        token_info = {
            "address": pair["baseToken"]["address"],
            "symbol": pair["baseToken"]["symbol"],
            "chain": pair["chainId"],
            "createdAt": datetime.fromtimestamp(
                pair.get("pairCreatedAt", 0) / 1000
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "marketCap": pair.get("marketCap"),
            "website": website,
            "twitter": twitter,
        }

        self.tokens[pair["baseToken"]["address"]] = token_info
        return token_info


twitter_search_agent = Agent(
    name="twitter symbol searcher",
    instructions="Search tweets for the given symbol/token address. Answer user questions first; if none, provide a concise bullet-point summary in English. Avoid styling like ** or ##.",
    model="gpt-4o",
    tools=[function_tool(elfa.search_mentions)],
)

twitter_account_agent = Agent(
    name="twitter account searcher",
    instructions="Get tweets for the given username. Answer user questions first; if none, provide a concise bullet-point summary of this account's tweets in English. Avoid styling like ** or ##.",
    model="gpt-4o",
    tools=[function_tool(elfa.search_account)],
)

exa_agent = Agent(
    name="web3 info searcher",
    instructions="Search for information about the given crypto symbol. Answer user questions first; if none, briefly summarize in English. Avoid styling like ** or ##.",
    model="gpt-4o",
    tools=[function_tool(exa.exa_web_search), function_tool(exa.exa_answer_question)],
)

cluster_agent = Agent(
    name="token clusters analyzer",
    instructions="Extract the token address from the user's query. Identify and explain significant holder clusters in English. Present findings in a structured format. Use only available data for the final analysis.",
    model="gpt-4o",
    tools=[function_tool(cluster.fetch_token_clusters)],
)

wallet_agent = Agent(
    name="solana wallet analyzer",
    instructions="Extract the token address from the user's query. Provide insights into the most valuable tokens held by top holders in English.",
    model="gpt-4o",
    tools=[function_tool(helius.analyze_common_holdings_of_top_holders)],
)

crawl_agent = Agent(
    name="webpage crawler",
    instructions="Crawl the webpage and extract the data. Briefly summarize the purpose of the site in English.",
    model="gpt-4o",
    tools=[function_tool(crawl.firecrawl_extract_web_data)],
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
                    prefix = "🔷 Social Media Sentiment Scan 🔷\n"
                elif result.last_agent.name == "twitter account searcher":
                    prefix = "🔷 Key Events from Official Twitter 🔷\n"
                elif result.last_agent.name == "web3 info searcher":
                    prefix = "🔷 Search Engine Data Scan 🔷\n"
                elif result.last_agent.name == "webpage crawler":
                    prefix = "🔷 Website Data Capture 🔷\n"
                elif result.last_agent.name == "solana wallet analyzer":
                    prefix = "🔷 Related Holdings Analysis 🔷\n"
                    output = re.sub(
                        r"\*\*([^*]+)\*\*", r"<b>\1</b>", result.final_output
                    )
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
        print(f"Received message: {message.text} from chat ID: {message.chat.id}")

        if str(message.chat.id) != os.environ.get("TELEGRAM_CHAT_ID"):
            return

        message_text = message.text
        symbol_match = re.search(r"\$(\w+)", message_text)
        sol_address_match = re.search(
            r"([A-Za-z0-9]{32,44}(?:pump|sol)?)", message_text
        )
        evm_address_match = re.search(r"(0x[A-Fa-f0-9]{40})", message_text)

        token_info = None
        if symbol_match:
            symbol = symbol_match.group(1)
            token_info = await token_tracker.search_token_symbol(symbol)
        elif sol_address_match or evm_address_match:
            address = (
                sol_address_match.group(1)
                if sol_address_match
                else evm_address_match.group(1)
            )
            token_info = await token_tracker.check_token_address(address)

        if not token_info:
            await bot.reply_to(
                message,
                "⚠️ Could not recognize this symbol or address. Please check the format.",
            )
            return

        plan_message = "AI Research Plan Generated\n"
        plan_items = []
        tasks = []
        query_content = re.sub(
            r"\$\w+|[A-Za-z0-9]{43,44}|0x[A-Fa-f0-9]{40}", "", message_text
        ).strip()

        twitter_search_msg = (
            f"symbol:{token_info['symbol']},token address:{token_info['address']}"
        )
        if query_content:
            twitter_search_msg += f",query:{query_content}"
        tasks.append(task_wrapper(twitter_search_agent, twitter_search_msg, message))
        plan_items.append(
            "🔹 Social sentiment scanning initiated using Twitter agent..."
        )

        if token_info.get("website"):
            tasks.append(
                task_wrapper(crawl_agent, f"check url:{token_info['website']}", message)
            )
            plan_items.append("🔹 Website crawling initiated using crawler agent...")

        if token_info.get("twitter"):
            twitter_username = re.search(r"twitter\.com/([^/]+)", token_info["twitter"])
            if twitter_username:
                username = twitter_username.group(1)
                tasks.append(
                    task_wrapper(twitter_account_agent, f"username:{username}", message)
                )
                plan_items.append("🔹 Official Twitter activity check triggered...")

        if token_info.get("chain") == "solana":
            tasks.append(
                task_wrapper(
                    wallet_agent, f"token address:{token_info['address']}", message
                )
            )
            plan_items.append(
                "🔹 Solana wallet scan triggered to analyze top holder assets..."
            )

        try:
            created_at = datetime.strptime(token_info["createdAt"], "%Y-%m-%d %H:%M:%S")
            days_since_creation = (datetime.now() - created_at).days
            market_cap = float(token_info.get("marketCap", "0"))

            if days_since_creation > 30 and market_cap > 10000000:
                exa_msg = f"symbol:{token_info['symbol']}"
                if query_content:
                    exa_msg += f",query:{query_content}"
                tasks.append(task_wrapper(exa_agent, exa_msg, message))
                plan_items.append(
                    "🔹 Search engine analysis triggered via Exa agent..."
                )
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
