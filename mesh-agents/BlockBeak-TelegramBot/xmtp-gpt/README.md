# XMTP + BlockBeak Agent Integration

This XMTP client integrates with the BlockBeak Agent system, routing all message processing through a Python backend that uses OpenAI's Assistant API with MCP (Model Context Protocol) servers.

## Architecture

```
┌─────────────┐  HTTP JSON  ┌──────────────┐
│  Node.js    │ ──────────► │ Python Agent│
│ (XMTP I/O)  │ ◄────────── │   Backend    │
└─────────────┘             └──────────────┘
```

- **Node.js Client**: Handles XMTP protocol, message I/O, retry logic
- **Python Backend**: Processes messages through OpenAI Agent with MCP servers
- **HTTP API**: Clean separation with JSON request/response format

## Features

- **Advanced AI Agent**: Uses OpenAI Assistant API with MCP server integrations
- **Multi-round conversations**: Conversation context maintained per XMTP conversation ID
- **Secure messaging**: All conversations are encrypted end-to-end via XMTP
- **Robust error handling**: Exponential backoff retry logic and fallback messages
- **Observability**: Detailed logging and OpenAI trace URLs for debugging
- **Easy key generation**: Built-in script to generate XMTP wallet and encryption keys
- **TypeScript support**: Fully typed with proper module resolution

## Requirements

- **Node.js** v20 or higher
- **Python** 3.9+ with pip
- **npm** or **yarn**
- **OpenAI API key** and **MCP SSE URL**
- **XMTP wallet keys** (private key and encryption key)

## Setup

### 1. Install Dependencies

```bash
# Install Node.js dependencies
npm install

# Dependencies are automatically installed from package.json:
# - @xmtp/node-sdk: XMTP protocol implementation
# - viem: Ethereum utilities for wallet operations
# - uint8arrays: Utility for handling byte arrays
# - @types/node: TypeScript definitions for Node.js (dev dependency)
```

### 2. Start the Python Backend

The Python backend must be running before starting the XMTP client.

```bash
# Navigate to project root
cd ..

# Activate virtual environment (if using one)
source .venv/bin/activate

# Set required environment variables
export API_KEY=your_openai_api_key_here
export MODEL=gpt-5-mini
export MCP_SSE_URL=your_mcp_sse_url_here

# Start the Python agent API server
python main_xmtp.py
```

The server will start on `http://127.0.0.1:8000` and you should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 3. Configure Environment Variables

> [!NOTE]
> The `WALLET_KEY` must be a valid hex private key starting with `0x`, not a test string.

You can generate random XMTP keys using the included script:

```bash
# Generate new wallet and encryption keys
npm run gen:keys

# Or run the script directly
npx tsx scripts/generateKeys.ts
```

This will:
- Generate a random wallet private key and derive the public address
- Generate a random encryption key for the local XMTP database
- Append the keys to your `.env` file (or create one if it doesn't exist)
- Display the public wallet address for sharing/funding


In the `.env` file or set environment variables:

```bash
WALLET_KEY=0x... # your wallet private key (must be valid hex)
ENCRYPTION_KEY=your_encryption_key_here # encryption key for local database
XMTP_ENV=dev # local, dev, production
AGENT_ENDPOINT=http://127.0.0.1:8000/inbox # Python agent API endpoint
```


### 4. Run the XMTP Client

```bash
# Set environment variables
export WALLET_KEY=0x...
export ENCRYPTION_KEY=your_encryption_key
export XMTP_ENV=dev
export AGENT_ENDPOINT=http://127.0.0.1:8000/inbox

# Start the client
npm run start

# Or for development with auto-reload
npm run dev
```

## Project Structure

The XMTP client includes the following key files:

```
xmtp-gpt/
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration with path mapping
├── index.ts              # Main XMTP client application
├── helpers/
│   └── client.ts         # XMTP client utilities and key generation
└── scripts/
    └── generateKeys.ts   # Key generation script
```

The `tsconfig.json` file configures TypeScript with:
- ES2022 target for modern Node.js features
- Path mapping for `@helpers/*` imports
- Proper module resolution for Node.js libraries

## How It Works

1. **XMTP Message Received**: Node.js client receives encrypted messages via XMTP
2. **Forward to Agent**: Client sends message data to Python backend via HTTP POST to `/inbox`
3. **Agent Processing**: Python backend processes message through OpenAI Agent with MCP servers
4. **Response Generation**: Agent generates contextual response with full conversation history
5. **Send Response**: Node.js client sends agent response back through XMTP

## API Integration

The Node.js client communicates with the Python backend using this HTTP API:

### POST /inbox
```json
{
  "conversationId": "xmtp-conversation-id",
  "sender": "sender-wallet-address", 
  "message": "user message content",
  "meta": {} // optional metadata
}
```

**Response:**
```json
{
  "response": "agent response text",
  "trace_url": "https://platform.openai.com/traces/trace?trace_id=..."
}
```

## Error Handling

The client includes robust error handling:
- **Exponential backoff retry** for API calls (3 attempts)
- **30-second timeout** for agent requests
- **Fallback messages** when agent is unavailable
- **Detailed logging** for debugging

## Troubleshooting

### TypeScript/Node.js Issues

1. **"Cannot find module '@helpers/client'"**: Fixed with proper `tsconfig.json` path mapping
2. **"Cannot find name 'process'"**: Fixed by adding `@types/node` dependency
3. **"Cannot find module 'node:fs/promises'"**: Ensure Node.js v20+ and proper TypeScript configuration
4. **Key generation script fails**: Run `npm install` to ensure all dependencies are installed

### Python Backend Issues

5. **"ModuleNotFoundError: No module named 'fastapi'"**: Install Python dependencies as shown above
6. **"Missing env vars: AGENT_ENDPOINT"**: Set all required environment variables
7. **Agent API connection failed**: Ensure Python backend is running on port 8000

### XMTP Issues

8. **"private key must be hex string"**: Use a valid wallet private key starting with `0x`
9. **Database connection errors**: Ensure `ENCRYPTION_KEY` is set and valid
10. **Message sending fails**: Check wallet has sufficient funds for gas (if using mainnet)

## Development

For development, run both services with auto-reload:

```bash
# Terminal 1: Python backend with reload
cd .. && python main_xmtp.py

# Terminal 2: Node.js client with reload  
npm run dev
```

See the main [XMTP_SETUP.md](../XMTP_SETUP.md) for complete setup instructions and additional configuration options.
