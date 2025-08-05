import {
  createSigner,
  getEncryptionKeyFromHex,
  logAgentDetails,
  validateEnvironment,
} from "./helpers/client.js";
import { Client, type XmtpEnv } from "@xmtp/node-sdk";

/* Get the wallet key associated to the public key of
 * the agent and the encryption key for the local db
 * that stores your agent's messages */
const { WALLET_KEY, ENCRYPTION_KEY, XMTP_ENV, AGENT_ENDPOINT } =
  validateEnvironment([
    "WALLET_KEY",
    "ENCRYPTION_KEY",
    "XMTP_ENV",
    "AGENT_ENDPOINT",
  ]);

/* Default agent endpoint if not provided */
const agentEndpoint = AGENT_ENDPOINT || "http://127.0.0.1:8000/inbox";

/**
 * Call the Python agent API with exponential backoff retry
 */
async function callAgentAPI(conversationId: string, sender: string, message: string, retries = 3): Promise<string> {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      console.log(`Calling agent API (attempt ${attempt}/${retries})...`);
      
      const response = await fetch(agentEndpoint, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversationId,
          sender,
          message,
        }),
        // 30 second timeout
        signal: AbortSignal.timeout(30000),
      });

      if (!response.ok) {
        throw new Error(`Agent API error: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      console.log(`Agent API response received: ${result.response.substring(0, 100)}...`);
      
      return result.response;
    } catch (error) {
      console.error(`Agent API call failed (attempt ${attempt}/${retries}):`, error);
      
      if (attempt === retries) {
        // Last attempt failed
        return "Sorry, I'm currently experiencing technical difficulties. Please try again later.";
      }
      
      // Exponential backoff: wait 1s, 2s, 4s, etc.
      const delay = Math.pow(2, attempt - 1) * 1000;
      console.log(`Retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  // This should never be reached, but TypeScript requires it
  return "Sorry, I'm currently experiencing technical difficulties. Please try again later.";
}

/**
 * Main function to run the agent
 * The agent routes all message processing to the Python backend,
 * enabling multi-round contextual conversations with advanced agent capabilities.
 */
async function main() {
  /* Create the signer using viem and parse the encryption key for the local db */
  const signer = createSigner(WALLET_KEY);
  const dbEncryptionKey = getEncryptionKeyFromHex(ENCRYPTION_KEY);

  const client = await Client.create(signer, {
    dbEncryptionKey,
    env: XMTP_ENV as XmtpEnv,
  });

  void logAgentDetails(client);

  /* Sync the conversations from the network to update the local db */
  console.log("✓ Syncing conversations...");
  await client.conversations.sync();

  // Stream all messages for GPT responses
  const messageStream = async () => {
    console.log("Waiting for messages...");
    const stream = client.conversations.streamAllMessages();
    for await (const message of await stream) {
      /* Ignore messages from the same agent or non-text messages */
      if (
        message.senderInboxId.toLowerCase() === client.inboxId.toLowerCase() ||
        message.contentType?.typeId !== "text"
      ) {
        continue;
      }

      console.log(
        `Received message: ${message.content as string} by ${message.senderInboxId}`,
      );

      /* Get the conversation from the local db */
      const conversation = await client.conversations.getConversationById(
        message.conversationId,
      );

      /* If the conversation is not found, skip the message */
      if (!conversation) {
        console.log("Unable to find conversation, skipping");
        return;
      }

      try {
        /* Call the Python agent API to get the response */
        const response = await callAgentAPI(
          message.conversationId,
          message.senderInboxId,
          message.content as string
        );

        console.log(`Sending agent response: ${response.substring(0, 100)}...`);
        
        /* Send the agent response to the conversation */
        await conversation.send(response);
      } catch (error) {
        console.error("Error getting agent response:", error);
        await conversation.send(
          "Sorry, I encountered an error processing your message.",
        );
      }
    }
  };

  // Start the message stream
  await messageStream();
}

main().catch(console.error);
