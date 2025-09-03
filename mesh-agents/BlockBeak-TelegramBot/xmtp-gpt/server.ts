import { createServer, IncomingMessage, ServerResponse } from 'http';
import { Client } from "@xmtp/node-sdk";

interface SendMessageRequest {
  conversationId: string;
  text: string;
}

/**
 * Create an HTTP server to receive messages from Python and send them via XMTP
 */
export function createControlServer(client: Client, port: number = 8788) {
  const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    // CORS headers for development
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    // Handle preflight requests
    if (req.method === 'OPTIONS') {
      res.writeHead(200);
      res.end();
      return;
    }

    // Only accept POST requests to /xmtp/send
    if (req.method !== 'POST' || req.url !== '/xmtp/send') {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Not found' }));
      return;
    }

    // Check authorization token (optional but recommended)
    const authHeader = req.headers.authorization;
    const expectedToken = process.env.XMTP_CONTROL_TOKEN;
    if (expectedToken && authHeader !== `Bearer ${expectedToken}`) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Unauthorized' }));
      return;
    }

    // Parse request body
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
    });

    req.on('end', async () => {
      try {
        const data: SendMessageRequest = JSON.parse(body);
        
        if (!data.conversationId || !data.text) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Missing conversationId or text' }));
          return;
        }

        console.log(`📨 Control server: Sending message to conversation ${data.conversationId.slice(0, 8)}...`);

        // Get the conversation
        const conversation = await client.conversations.getConversationById(data.conversationId);
        if (!conversation) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Conversation not found' }));
          return;
        }

        // Send the message
        await conversation.send(data.text);
        console.log(`✅ Control server: Message sent successfully`);

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, message: 'Message sent' }));

      } catch (error) {
        console.error('❌ Control server error:', error);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Failed to send message', details: String(error) }));
      }
    });
  });

  server.listen(port, '127.0.0.1', () => {
    console.log(`🎮 Control server listening on http://127.0.0.1:${port}/xmtp/send`);
    console.log(`   Use this endpoint to send messages from Python to XMTP conversations`);
  });

  return server;
}
