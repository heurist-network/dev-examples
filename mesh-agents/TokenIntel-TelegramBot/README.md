# TokenIntel-TelegramBot

A Python-based Telegram bot for crypto and web3 intelligence that leverages various specialized agents through the Heurist API to perform token analysis, web searches, social media analysis, and blockchain data analysis.

## Features

- Web search and data extraction using ExaSearch and Firecrawl agents
- Twitter intelligence and analysis with ElfaTwitterIntelligenceAgent
- Blockchain analysis with SolWallet agents
- Twitter insights with follower history and mentions tracking

## Prerequisites

- Telegram Bot Token
- OpenAI API Key
- Heurist API Key

### Telegram Bot Token Setup
1. Create a Telegram bot using [@BotFather](https://t.me/BotFather) and get your token
2. Add the token to your `.env` file as `TELEGRAM_TOKEN`

## Installation

1. Clone the repository
2. Install the required dependencies:
```bash
pip install -r requirements.txt