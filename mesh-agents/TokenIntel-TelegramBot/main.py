import os
import sys
import anyio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# from agents import Agent, function_tool, set_tracing_disabled, Runner
from pydantic import BaseModel
from dotenv import load_dotenv

# Import tools
from src.tools import (
    ElfaTwitterIntelligenceAgent,
    ExaSearchAgent,
    MetaSleuthSolTokenWalletClusterAgent,
    SolWalletAgent,
    FirecrawlSearchAgent,
)

# Import model configuration and custom agent wrapper
from src.model_config import validate_model_setup, get_model_config
from src.custom_agent_wrapper import create_custom_agent, MockRunner

import re
from typing import Optional, Dict, Any
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
import httpx

# Load environment variables
load_dotenv()

print("🚀 Starting Multi-Provider Token Intelligence Bot...")
print("=" * 60)

# Validate model configuration at startup
print("🔧 Validating model configuration...")
if not validate_model_setup():
    print("❌ Model setup validation failed. Please check your configuration.")
    print("Make sure your .env file has correct MODEL_PROVIDER, MODEL, and API_KEY")
    sys.exit(1)

config = get_model_config()
print(
    f"✅ Successfully configured {config.provider.upper()} with model: {config.model}"
)

# Telegram configuration validation
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HEURIST_KEY = os.environ.get("HEURIST_KEY")

print("\n🔧 Validating Telegram configuration...")
if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN is required in .env file")
    sys.exit(1)
if not TELEGRAM_CHAT_ID:
    print("❌ TELEGRAM_CHAT_ID is required in .env file")
    sys.exit(1)
if not HEURIST_KEY:
    print("❌ HEURIST_KEY is required for intelligence tools")
    sys.exit(1)

print(f"✅ Telegram bot configured for chat ID: {TELEGRAM_CHAT_ID}")
print("✅ Intelligence tools configured with Heurist API")

# Optional: Disable tracing for cleaner output
# set_tracing_disabled(True)

# Initialize intelligence agents
print("\n🔧 Initializing intelligence agents...")
try:
    elfa = ElfaTwitterIntelligenceAgent()
    exa = ExaSearchAgent()
    crawl = FirecrawlSearchAgent()
    cluster = MetaSleuthSolTokenWalletClusterAgent()
    helius = SolWalletAgent()
    print("✅ All intelligence agents initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize intelligence agents: {e}")
    sys.exit(1)


class SearchResult(BaseModel):
    brief_summary: str


class TokenInfo:
    def __init__(self):
        self.tokens = {}

    async def check_token_address(self, address: str) -> Optional[Dict[str, Any]]:
        """Check token information by address across multiple chains"""
        chains = ["solana", "bsc", "base", "eth"]
        for chain in chains:
            url = f"https://api.dexscreener.com/tokens/v1/{chain}/{address}"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        pair = data[0]
                        return self._extract_token_info(pair)
            except Exception as e:
                print(f"Error checking {chain} for {address}: {e}")
                continue
        return None

    async def search_token_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Search token information by symbol"""
        url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                data = response.json()
                if "pairs" in data and data["pairs"]:
                    pair = data["pairs"][0]
                    return self._extract_token_info(pair)
        except Exception as e:
            print(f"Error searching symbol {symbol}: {e}")
            return None
        return None

    def _extract_token_info(self, pair: Dict) -> Dict[str, Any]:
        """Extract relevant token information from API response"""
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


print("\n🤖 Setting up AI agents with custom multi-provider wrapper...")
print(f"🎯 Provider: {config.provider}")
print(f"🔧 Model: {config.model}")
print(f"🔑 API key configured: {config.api_key[:10]}...")

try:
    twitter_search_agent = create_custom_agent(
        name="twitter symbol searcher",
        instructions="Search tweets for the given symbol/token address. Answer user questions first; if none, provide a concise bullet-point summary in English. Avoid styling like ** or ##.",
        tools=[elfa.search_mentions],
    )

    twitter_account_agent = create_custom_agent(
        name="twitter account searcher",
        instructions="Get tweets for the given username. Answer user questions first; if none, provide a concise bullet-point summary of this account's tweets in English. Avoid styling like ** or ##.",
        tools=[elfa.search_account],
    )

    exa_agent = create_custom_agent(
        name="web3 info searcher",
        instructions="Search for information about the given crypto symbol. Answer user questions first; if none, briefly summarize in English. Avoid styling like ** or ##.",
        tools=[exa.exa_web_search, exa.exa_answer_question],
    )

    cluster_agent = create_custom_agent(
        name="token clusters analyzer",
        instructions="Extract the token address from the user's query. Identify and explain significant holder clusters in English. Present findings in a structured format. Use only available data for the final analysis.",
        tools=[cluster.fetch_token_clusters],
    )

    wallet_agent = create_custom_agent(
        name="solana wallet analyzer",
        instructions="Extract the token address from the user's query. Provide insights into the most valuable tokens held by top holders in English.",
        tools=[helius.analyze_common_holdings_of_top_holders],
    )

    crawl_agent = create_custom_agent(
        name="webpage crawler",
        instructions="Crawl the webpage and extract the data. Briefly summarize the purpose of the site in English.",
        tools=[crawl.firecrawl_extract_web_data],
    )

    print("✅ All AI agents configured successfully with custom wrapper")
    print(f"🔧 Using {config.provider} provider with model: {config.model}")

except Exception as e:
    print(f"❌ Failed to initialize AI agents: {e}")
    sys.exit(1)

bot = AsyncTeleBot(TELEGRAM_TOKEN)
token_tracker = TokenInfo()


def task_wrapper(agent, param, message):
    """Wrapper function to handle agent tasks with error handling"""

    async def task():
        try:
            print(f"🔄 Running {agent.name} with param: {param[:100]}...")
            result = await MockRunner.run(agent, param)

            if result and result.get("final_output"):
                final_output = result["final_output"]
                if (
                    result["last_agent"].name == "solana wallet analyzer"
                    and "**" in final_output
                ):
                    output = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", final_output)
                    await bot.reply_to(message, output, parse_mode="HTML")
                else:
                    await bot.reply_to(message, final_output)

                print(f"✅ Completed {agent.name}")
            else:
                print(f"⚠️ No output from {agent.name}")

        except Exception as e:
            print(f"❌ Error in {agent.name}: {e}")
            error_msg = f"⚠️ {agent.name.title()} Temporarily Unavailable\n\nPlease try again in a moment."
            await bot.reply_to(message, error_msg)

    return task


@bot.message_handler(func=lambda message: True)
async def msg_entry(message):
    """Main message handler for the bot"""
    try:
        print(
            f"\n📨 Received message: '{message.text}' from chat ID: {message.chat.id}"
        )
        if str(message.chat.id) != TELEGRAM_CHAT_ID:
            print(f"🚫 Unauthorized chat ID: {message.chat.id}")
            return

        message_text = message.text.strip()
        if message_text.lower() == "/status":
            status_msg = f"""🤖 **Bot Status Report**

            **AI Configuration:**
            • Provider: {config.provider.upper()}
            • Model: {config.model}
            • Temperature: {config.temperature}
            • Max Tokens: {config.max_tokens}

            **System Status:**
            ✅ Model validated and operational
            ✅ Intelligence tools connected
            ✅ Telegram bot active
            ✅ Chat authorized: {TELEGRAM_CHAT_ID}

            **Available Intelligence:**
            🐦 Twitter sentiment analysis
            🌐 Web search and crawling  
            💰 Solana wallet analysis
            📊 Token holder clusters
            🔗 Website content extraction

            Ready for token analysis! 🚀"""
            await bot.reply_to(message, status_msg, parse_mode="Markdown")
            return

        if message_text.lower() == "/help":
            help_msg = f"""🔍 **Token Intelligence Bot Help**

            **Current Setup:** {config.provider.upper()} ({config.model})

            **How to Use:**
            • Send a token symbol: `$BTC`, `$ETH`, `$SOL`
            • Send a contract address: `0x1234...` or Solana address
            • Add questions after the symbol: `$BTC what's the sentiment?`

            **Commands:**
            • `/status` - Check bot configuration and health
            • `/help` - Show this help message

            **Analysis Features:**
            🐦 Social media sentiment from Twitter
            🌐 Web intelligence and news analysis  
            💰 Wallet analysis for top holders
            📊 Token holder cluster identification
            🔗 Official website content analysis
            📱 Official social media activity

            **Supported Providers:**
            OpenAI • Anthropic • OpenRouter • XAI • Heurist

            *Currently using: {config.provider.upper()}*"""
            await bot.reply_to(message, help_msg, parse_mode="Markdown")
            return

        # Parse token symbols and addresses
        symbol_match = re.search(r"\$(\w+)", message_text)
        sol_address_match = re.search(
            r"([A-Za-z0-9]{32,44}(?:pump|sol)?)", message_text
        )
        evm_address_match = re.search(r"(0x[A-Fa-f0-9]{40})", message_text)

        # Get token information
        token_info = None
        search_term = None

        if symbol_match:
            search_term = symbol_match.group(1)
            print(f"🔍 Searching for token symbol: ${search_term}")
            token_info = await token_tracker.search_token_symbol(search_term)
        elif sol_address_match or evm_address_match:
            search_term = (
                sol_address_match.group(1)
                if sol_address_match
                else evm_address_match.group(1)
            )
            print(f"🔍 Searching for token address: {search_term}")
            token_info = await token_tracker.check_token_address(search_term)

        if not token_info:
            error_msg = f"""⚠️ **Token Not Found**

            Could not find information for: `{search_term or "unknown"}`

            **Supported formats:**
            • Symbols: $BTC, $ETH, $SOL
            • Ethereum: 0x1234567890abcdef1234567890abcdef12345678
            • Solana: 7h8Nq9XYz5T6jQqsQ8E3jKQwHYyGFw8z9xqGc3T4vJHQf

            Please check the format and try again."""
            await bot.reply_to(message, error_msg, parse_mode="Markdown")
            return

        print(f"✅ Found token: {token_info['symbol']} ({token_info['chain']})")

        # Generate analysis plan
        plan_message = (
            f"🤖 **AI Research Plan Generated** ({config.provider.upper()})\n\n"
        )
        plan_items = []
        tasks = []

        # Extract any additional query content
        query_content = re.sub(
            r"\$\w+|[A-Za-z0-9]{43,44}|0x[A-Fa-f0-9]{40}", "", message_text
        ).strip()

        # 1. Twitter sentiment analysis (always included)
        twitter_search_msg = (
            f"symbol:{token_info['symbol']},token address:{token_info['address']}"
        )
        if query_content:
            twitter_search_msg += f",query:{query_content}"
        tasks.append(task_wrapper(twitter_search_agent, twitter_search_msg, message))
        plan_items.append("🔹 Social sentiment scanning via Twitter intelligence...")

        # 2. Website crawling (if website available)
        if token_info.get("website"):
            tasks.append(
                task_wrapper(crawl_agent, f"check url:{token_info['website']}", message)
            )
            plan_items.append("🔹 Website content extraction and analysis...")

        # 3. Official Twitter account analysis (if available)
        if token_info.get("twitter"):
            twitter_username = re.search(r"twitter\.com/([^/]+)", token_info["twitter"])
            if twitter_username:
                username = twitter_username.group(1)
                tasks.append(
                    task_wrapper(twitter_account_agent, f"username:{username}", message)
                )
                plan_items.append("🔹 Official Twitter account activity analysis...")

        # 4. Solana-specific analysis (wallet and clusters)
        if token_info.get("chain") == "solana":
            tasks.append(
                task_wrapper(
                    wallet_agent, f"token address:{token_info['address']}", message
                )
            )
            plan_items.append("🔹 Solana top holder portfolio analysis...")

        # 5. Web search for established tokens
        try:
            created_at = datetime.strptime(token_info["createdAt"], "%Y-%m-%d %H:%M:%S")
            days_since_creation = (datetime.now() - created_at).days
            market_cap = float(token_info.get("marketCap", "0"))

            if days_since_creation > 30 and market_cap > 10000000:
                exa_msg = f"symbol:{token_info['symbol']}"
                if query_content:
                    exa_msg += f",query:{query_content}"
                tasks.append(task_wrapper(exa_agent, exa_msg, message))
                plan_items.append("🔹 Web intelligence gathering via search engines...")
        except (ValueError, TypeError) as e:
            print(f"⚠️ Error processing Exa search criteria: {e}")

        # Send the plan
        full_plan = plan_message + "\n".join(plan_items)
        full_plan += f"\n\n📊 **Token:** {token_info['symbol']} ({token_info['chain']})"
        full_plan += f"\n🔗 **Address:** `{token_info['address'][:10]}...{token_info['address'][-6:]}`"

        await bot.reply_to(message, full_plan, parse_mode="Markdown")

        # Execute all tasks concurrently
        if tasks:
            print(f"🚀 Executing {len(tasks)} analysis tasks...")
            try:
                async with anyio.create_task_group() as tg:
                    for task in tasks:
                        tg.start_soon(task)
                print("✅ All analysis tasks completed")
            except Exception as e:
                print(f"❌ Error in task execution: {e}")
                await bot.reply_to(
                    message,
                    f"❌ Error executing analysis tasks: {str(e)[:100]}...\n\nPlease try again or contact support.",
                )
        else:
            await bot.reply_to(
                message,
                "⚠️ No analysis tasks were scheduled. Please try a different token.",
            )

    except Exception as e:
        print(f"❌ Critical error in message handler: {e}")
        await bot.reply_to(
            message,
            f"❌ A critical error occurred: {str(e)[:100]}...\n\nPlease try again or use /status to check bot health.",
        )


async def main():
    """Main bot loop with error handling"""
    try:
        print(f"\n🚀 Starting bot with {config.provider.upper()} ({config.model})")
        print(f"📱 Authorized for chat ID: {TELEGRAM_CHAT_ID}")
        print(f"🔧 Temperature: {config.temperature}, Max tokens: {config.max_tokens}")
        print("=" * 60)
        print("🎯 Bot is ready! Send a token symbol or address to begin analysis.")
        print("💡 Use /help for usage instructions or /status for health check")
        print("=" * 60)

        await bot.infinity_polling(skip_pending=True)

    except Exception as e:
        print(f"❌ Critical error in bot main loop: {e}")
        print("🔄 Bot will attempt to restart...")


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user (Ctrl+C)")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        print("🔧 Please check your configuration and try again")
