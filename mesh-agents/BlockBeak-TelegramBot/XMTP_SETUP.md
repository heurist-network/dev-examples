# XMTP Integration Setup Guide

This guide explains how to set up and run the XMTP chat integration that uses the BlockBeak Agent backend.

## Architecture Overview

The XMTP integration consists of two components:

1. **Python FastAPI Backend** (`src/interfaces/xmtp/api.py`)
   - Provides `/inbox` endpoint for processing XMTP messages
   - Uses the BlockBeak Agent (OpenAI Assistant API with MCP servers)
   - Maintains conversation context per conversation ID
   - Returns structured JSON responses with agent output and trace URLs

2. **Node.js XMTP Client** (`xmtp-gpt/index.ts`)
   - Listens to XMTP messages using the XMTP Node SDK
   - Forwards incoming messages to the Python backend via HTTP
   - Sends agent responses back to XMTP conversations
   - Includes retry logic and error handling

```
┌─────────────┐  HTTP JSON  ┌──────────────┐
│  index.ts   │ ──────────► │ FastAPI/Agent│
│ (XMTP I/O)  │ ◄────────── │   backend     │
└─────────────┘             └──────────────┘
```

## Prerequisites

1. **Python 3.9+** with pip
2. **Node.js 20+** with npm
3. **XMTP wallet and encryption keys**
4. **OpenAI API key** and **MCP SSE URL**

## Environment Setup

1. **Copy environment file:**
   ```bash
   cp env.example .env
   ```

2. **Configure environment variables in `.env`:**
   ```bash
   # Core AI Configuration
   MODEL_PROVIDER=openai
   API_KEY=your_openai_api_key_here
   MODEL=gpt-4o-mini
   TEMPERATURE=0.1
   MAX_TOKENS=500000
   MCP_SSE_URL=your_mcp_sse_url_here

   # XMTP Configuration (for Node.js side)
   WALLET_KEY=your_wallet_private_key_here
   ENCRYPTION_KEY=your_encryption_key_here
   XMTP_ENV=dev
   AGENT_ENDPOINT=http://127.0.0.1:8000/inbox

   # XMTP API Server Configuration (optional)
   XMTP_API_HOST=127.0.0.1
   XMTP_API_PORT=8000
   XMTP_API_RELOAD=false
   ```

### Node.js Dependencies
```bash
# Install Node.js dependencies for XMTP
cd xmtp-gpt
npm install
cd ..
```

## Local Development Workflow

### Step 1: Start the Python Agent API
```bash
# Option 1: Use the main entry point
python main_xmtp.py

# Option 2: Use uvicorn directly
uvicorn src.interfaces.xmtp.api:app --host 127.0.0.1 --port 8000 --reload
```

The server will start on `http://127.0.0.1:8000` and you should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
2025-XX-XX XX:XX:XX,XXX - src.interfaces.xmtp.api - INFO - Starting BlockBeak XMTP Agent API
```

### Step 2: Test the API Health Check
```bash
curl http://127.0.0.1:8000/health
# Should return: {"status":"healthy","version":"1.0.0"}
```

### Step 3: Test the Agent Endpoint
```bash
curl -X POST http://127.0.0.1:8000/inbox \
  -H "Content-Type: application/json" \
  -d '{
    "conversationId": "test-123", 
    "sender": "test-user", 
    "message": "Hello, how are you?"
  }'
```

Expected response:
```json
{
  "response": "Hello! I'm doing well, thanks for asking. How can I assist you today?",
  "trace_url": "https://platform.openai.com/traces/trace?trace_id=trace_..."
}
```

### Step 4: Start the XMTP Node.js Client
```bash
cd xmtp-gpt

# Install missing dependencies if needed
npm install uint8arrays viem @xmtp/node-sdk

# Set environment variables and start
export WALLET_KEY=your_wallet_private_key_here
export ENCRYPTION_KEY=your_encryption_key_here
export XMTP_ENV=dev
export AGENT_ENDPOINT=http://127.0.0.1:8000/inbox

npm run start
# Or for development with auto-reload:
npm run dev
```

The Node.js client will:
1. Connect to XMTP using your wallet
2. Listen for incoming messages
3. Forward messages to the Python agent API
4. Send agent responses back to XMTP

**Note**: The `WALLET_KEY` must be a valid hex private key (starts with 0x), not a test string.

## API Reference

### POST /inbox
Process an incoming XMTP message through the BlockBeak agent.

**Request Body:**
```json
{
  "conversationId": "string",
  "sender": "string", 
  "message": "string",
  "meta": {} // optional metadata
}
```

**Response:**
```json
{
  "response": "string",
  "trace_url": "string"
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

## Error Handling

The Node.js client includes robust error handling:
- **Exponential backoff retry** for API calls (3 attempts)
- **30-second timeout** for agent API requests  
- **Fallback messages** when the agent is unavailable
- **Detailed logging** for debugging

## Troubleshooting

### Python API Issues
1. **Import errors**: Ensure all dependencies are installed
2. **Configuration errors**: Check that required environment variables are set
3. **Port conflicts**: Use a different port with `XMTP_API_PORT`

### Node.js Client Issues
1. **XMTP connection**: Verify `WALLET_KEY` and `ENCRYPTION_KEY` are correct
2. **Agent API connection**: Ensure the Python server is running and `AGENT_ENDPOINT` is correct
3. **Message processing**: Check logs for API call failures

### Common Environment Issues
1. **Missing .env file**: Copy from `env.example`
2. **Invalid API keys**: Verify OpenAI API key is valid
3. **MCP URL**: Ensure MCP SSE URL is accessible

## Development Tips

1. **Run with reload**: Use `--reload` flag for auto-restart during development
2. **Logging**: Both services provide detailed logs for debugging
3. **Testing**: Use curl to test the API endpoints independently
4. **Conversation context**: Each conversation ID maintains separate context
5. **Trace URLs**: Use the returned trace URLs to debug agent behavior

## Production Deployment

For production deployment, consider:
1. **Docker containers** for both services
2. **Health checks** and monitoring
3. **Load balancing** for the Python API
4. **Persistent storage** for conversation context
5. **Rate limiting** and authentication

## Next Steps

1. **Test with real XMTP messages** by sending DMs to your agent's address
2. **Customize agent instructions** in `src/config/agent_instructions.yaml`
3. **Add MCP servers** for additional capabilities
4. **Monitor traces** using the OpenAI platform URLs