# Heurist Mesh Agents with MCP

This folder contains advanced examples that demonstrate how to integrate with specialized Heurist Mesh Agents using the Model Context Protocol (MCP).

## What are Mesh Agents?

Heurist Mesh Agents are specialized AI agents that provide domain-specific capabilities through the Model Context Protocol (MCP). They extend the functionality of base LLMs by adding:

- Web search and information retrieval
- Social media analysis
- Blockchain data analysis
- Financial market data access
- And much more

## Examples

### Telegram Multi-Agent Bot
[`telegram-bot/`](telegram-bot/) - Demonstrates how to integrate multiple specialized agents into a Telegram bot:

- ExaSearchAgent (web search)
- ElfaTwitterIntelligenceAgent (Twitter analysis)
- FirecrawlSearchAgent (advanced web search)
- SolWalletAgent (blockchain wallet analysis)
- TwitterInsightAgent (Twitter follower tracking)

### Google Sheets Data Pipeline 
[`sheets-pipeline/`](sheets-pipeline/) - Shows how to create a data pipeline that:

- Fetches cryptocurrency and financial data from multiple sources
- Uses Google's Agent Development Kit (ADK)
- Connects to multiple MCP servers (Heurist Mesh + Google Sheets)
- Automatically populates spreadsheets with the results

## Creating Your Own Mesh Agent Applications

1. Get a Heurist API Key from [the developer portal](https://dev-api-form.heurist.ai/)
2. Visit the [Heurist Mesh MCP platform](https://mcp.heurist.ai/)
3. Select your desired specialized agents
4. Create your dedicated MCP server
5. Use the MCP server URL in your application
6. Follow the examples in this repository

## Resources

- [Mesh MCP Server Repository](https://github.com/heurist-network/heurist-mesh-mcp-server)
- [Mesh Agents Repository](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh)
- [Create Your Own MCP Server](https://github.com/heurist-network/heurist-agent-framework/tree/main/mesh)
- [Heurist Mesh MCP Platform](https://mcp.heurist.ai/)