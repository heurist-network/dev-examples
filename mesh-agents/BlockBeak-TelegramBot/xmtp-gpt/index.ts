import {
  createSigner,
  getEncryptionKeyFromHex,
  logAgentDetails,
  validateEnvironment,
} from "./helpers/client.js";
import { Client, type XmtpEnv } from "@xmtp/node-sdk";
import {
  ReactionCodec,
  ContentTypeReaction,
  type Reaction,
} from "@xmtp/content-type-reaction";
import {
  ReplyCodec,
  ContentTypeReply,
  type Reply,
} from "@xmtp/content-type-reply";
import {
  AttachmentCodec,
  RemoteAttachmentCodec,
  ContentTypeRemoteAttachment,
  type RemoteAttachment,
} from "@xmtp/content-type-remote-attachment";
import { createHash } from "node:crypto";

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

type ImageMeta = {
  image_data_url: string;
  filename?: string;
  mime_type?: string;
  content_digest?: string;
};

type PendingTurn = {
  senderInboxId: string;
  text?: string;
  imageMeta?: ImageMeta | null;
  replyContext?: string | null;
  timer?: ReturnType<typeof setTimeout> | null;
  pairedTextId?: string | null;
  hasUserText?: boolean; // Track if user provided explicit text
  imageTimestamp?: number; // Timestamp when image was received
  textTimestamp?: number; // Timestamp when text was received
};

const DEBOUNCE_MS = 800; // aggregation window for pairing text+image (reduced from 1200ms)
const IMMEDIATE_FLUSH_MS = 80; // tiny delay when both parts already present
const PAIRING_WINDOW_MS = 3000; // only pair messages within 3 seconds of each other

const pendingByConversation = new Map<string, PendingTurn>();
const lastProcessedByConversation = new Map<string, number>();

// Cleanup function to remove stale pending items
function cleanupStalePending() {
  const now = Date.now();
  const STALE_THRESHOLD = PAIRING_WINDOW_MS * 2; // 6 seconds
  
  for (const [convId, pending] of pendingByConversation.entries()) {
    const imageAge = pending.imageTimestamp ? now - pending.imageTimestamp : 0;
    const textAge = pending.textTimestamp ? now - pending.textTimestamp : 0;
    const maxAge = Math.max(imageAge, textAge);
    
    if (maxAge > STALE_THRESHOLD) {
      console.log(`Cleanup: Removing stale pending item for ${convId} (age: ${maxAge}ms)`);
      if (pending.timer) clearTimeout(pending.timer);
      pendingByConversation.delete(convId);
    }
  }
}

// Run cleanup every 30 seconds
setInterval(cleanupStalePending, 30000);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function flushPending(
  client: Client<any>,
  conversationId: string,
): Promise<void> {
  const pending = pendingByConversation.get(conversationId);
  if (!pending) {
    console.log(`flushPending: no pending for ${conversationId}`);
    return;
  }
  
  console.log(`flushPending: processing ${conversationId}, hasText=${!!pending.text}, hasImage=${!!pending.imageMeta}`);
  pendingByConversation.delete(conversationId);

  const conversation = await client.conversations.getConversationById(
    conversationId,
  );
  if (!conversation) {
    console.warn("flushPending: conversation not found", conversationId);
    return;
  }

  const messageText = pending.text || "Describe the image";
  const payload: any = {
    conversationId,
    sender: pending.senderInboxId,
    message: messageText,
    replyContext: pending.replyContext || null,
  };
  if (pending.imageMeta) {
    payload.meta = pending.imageMeta;
  }

  console.log(`XMTP: flushPending payload:`, JSON.stringify({
    ...payload,
    meta: payload.meta ? `[Image data: ${payload.meta.filename || 'unknown'}]` : undefined
  }, null, 2));

  const maxRetries = 3;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(agentEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(180000),
      });
      if (!res.ok) {
        throw new Error(`Agent API error: ${res.status} ${res.statusText}`);
      }
      const result = (await res.json()) as { response?: string };
      const responseText = String(result.response || "");
      console.log(
        `Agent API response received: ${responseText.substring(0, 100)}...`,
      );
      await conversation.send(responseText);
      // Mark as processed with current timestamp
      lastProcessedByConversation.set(conversationId, Date.now());
      return;
    } catch (error) {
      console.error(
        `flushPending: agent call failed (attempt ${attempt}/${maxRetries}):`,
        error,
      );
      if (attempt < maxRetries) {
        const backoffMs = Math.min(2000, 300 * 2 ** (attempt - 1));
        await sleep(backoffMs);
        continue;
      }
      // Final failure: apologize once
      await conversation.send(
        "Sorry, I encountered an error processing your message.",
      );
    }
  }
}

/**
 * Get the original message that is being replied to
 */
async function getReferencedMessage(conversation: any, messageId: string): Promise<string | null> {
  try {
    // Get all messages in the conversation
    const messages = await conversation.messages();
    
    // Find the message with the matching ID
    const referencedMessage = messages.find((msg: any) => msg.id === messageId);
    
    if (referencedMessage && referencedMessage.contentType?.typeId === "text") {
      return referencedMessage.content as string;
    }
    
    return null;
  } catch (error) {
    console.error("Error getting referenced message:", error);
    return null;
  }
}

/**
 * Call the Python agent API with exponential backoff retry
 */
async function callAgentAPI(conversationId: string, sender: string, message: string, replyContext?: string, retries = 2): Promise<string> {
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
          replyContext: replyContext || null,
        }),
        // 180 second timeout
        signal: AbortSignal.timeout(180000),
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
    codecs: [
      new ReactionCodec(),
      new ReplyCodec(),
      new AttachmentCodec(),
      new RemoteAttachmentCodec(),
    ],
  });

  void logAgentDetails(client as any);

  /* Sync the conversations from the network to update the local db */
  console.log("✓ Syncing conversations...");
  await client.conversations.sync();

  // Stream all messages for GPT responses
  const messageStream = async () => {
    console.log("Waiting for messages...");
    const stream = client.conversations.streamAllMessages();
    for await (const message of await stream) {
      /* Ignore messages from the same agent */
      if (message.senderInboxId.toLowerCase() === client.inboxId.toLowerCase()) {
        continue;
      }

      console.log("incoming message", message);

      const isText = message.contentType?.typeId === "text";
      const isReply = message.contentType?.sameAs(ContentTypeReply);
      const isRemoteAttachment =
        message.contentType?.typeId === "remoteStaticAttachment" ||
        message.contentType?.sameAs?.(ContentTypeRemoteAttachment);

      let messageContent: string = "";
      let replyContext: string | null = null;
      let imageMeta: ImageMeta | null = null;
      let isRecentTextForPairing = false;
      
      if (!isText && !isReply && !isRemoteAttachment) {
        // Not a supported message type; skip
        continue;
      }

      // Handle reply messages
      if (isReply) {
        const reply = message.content as Reply;
        messageContent = reply.content as string;
        
        console.log(
          `Received reply: "${messageContent}" by ${message.senderInboxId} (replying to message ID: ${reply.reference})`,
        );
        
        // Get the original message being replied to
        const conversation = await client.conversations.getConversationById(
          message.conversationId,
        );
        if (conversation) {
          replyContext = await getReferencedMessage(conversation, reply.reference);
          if (replyContext) {
            console.log(`Original message being replied to: "${replyContext}"`);
          }
        }
      } else if (isText) {
        // Regular text message
        messageContent = message.content as string;
        console.log(
          `Received message: ${messageContent} by ${message.senderInboxId}`,
        );
      } else if (isRemoteAttachment) {
        // Remote static attachment: download, decrypt, build data URL
        const conversation = await client.conversations.getConversationById(
          message.conversationId,
        );
        if (!conversation) {
          console.log("Unable to find conversation for attachment, skipping");
          continue;
        }

        const remote = message.content as RemoteAttachment;
        const decrypted = (await RemoteAttachmentCodec.load(
          remote,
          client,
        )) as { filename?: string; mimeType?: string; data: Uint8Array };

        // Optional integrity check against contentDigest
        if ((remote as any).contentDigest) {
          const digest = createHash("sha256")
            .update(Buffer.from(decrypted.data))
            .digest("hex");
          if (digest !== (remote as any).contentDigest) {
            console.warn("Attachment digest mismatch; proceeding but marking");
          }
        }

        const mime = decrypted.mimeType || "application/octet-stream";
        const dataUrl = `data:${mime};base64,${Buffer.from(
          decrypted.data,
        ).toString("base64")}`;

        imageMeta = {
          image_data_url: dataUrl,
          filename: decrypted.filename,
          mime_type: decrypted.mimeType,
          content_digest: (remote as any).contentDigest,
        };

        // For image attachments, always start with default text
        // We'll wait for a real text message to pair with this image
        messageContent = "Describe the image";
        isRecentTextForPairing = false;
        console.log(`Debug: Image processing - using default text, will wait for user text message to pair`);
      }

      /* Get the conversation from the local db */
      const conversation = await client.conversations.getConversationById(
        message.conversationId,
      );

      /* If the conversation is not found, skip the message */
      if (!conversation) {
        console.log("Unable to find conversation, skipping");
        continue;
      }

      try {
        /* Send a 👀 reaction to indicate message received and processing */
        console.log("Sending 👀 reaction to indicate message received...");
        
        // Send proper XMTP reaction using the official content type
        const reaction: Reaction = {
          reference: message.id,
          action: "added" as const,
          content: "👀",
          schema: "unicode" as const,
        };
        
        await conversation.send(reaction, ContentTypeReaction);
        console.log("👀 reaction sent successfully");

        // Simple approach: check if we processed something very recently to avoid duplicates
        const convId = message.conversationId;
        const lastProcessed = lastProcessedByConversation.get(convId) || 0;
        const timeSinceLastProcessed = Date.now() - lastProcessed;
        
        if (timeSinceLastProcessed < 2000) {
          console.log(`Skipping message due to recent processing (${timeSinceLastProcessed}ms ago)`);
          continue;
        }

        // Check for pending aggregation before processing text messages
        const existing = pendingByConversation.get(convId);
        
        // Debug log for pairing conditions
        console.log(`Debug: convId=${convId}, existing=${!!existing}, imageMeta=${!!existing?.imageMeta}, hasUserText=${existing?.hasUserText}, isText=${isText}, isReply=${isReply}`);
        
        // For text-only messages, check if there's a pending image to pair with
        if (isReply || isText) {
          // Check if there's a valid pending image to pair with (within time window)
          let shouldPair = false;
          if (existing && existing.imageMeta && !existing.hasUserText) {
            // Check if the pending image is recent enough for pairing (within 3 seconds)
            const now = Date.now();
            const pendingAge = now - (existing.imageTimestamp || 0);
            shouldPair = pendingAge <= PAIRING_WINDOW_MS;
            console.log(`Debug: Pending image age=${pendingAge}ms, shouldPair=${shouldPair} (window: ${PAIRING_WINDOW_MS}ms)`);
            
            // If the pending image is too old, clean it up
            if (!shouldPair) {
              console.log(`Cleaning up stale pending image (age: ${pendingAge}ms)`);
              if (existing.timer) clearTimeout(existing.timer);
              pendingByConversation.delete(convId);
            }
          }
          
          if (shouldPair) {
            // We have a recent pending image, update it with user text and flush
            console.log(`Pairing text with pending image for aggregation`);
            existing!.text = messageContent;
            existing!.replyContext = replyContext;
            existing!.hasUserText = true;
            if (existing!.timer) clearTimeout(existing!.timer);
            
            // Flush immediately with small delay since both parts are now present
            existing!.timer = setTimeout(() => {
              flushPending(client, convId).catch((e) =>
                console.error("flushPending failed", e),
              );
            }, IMMEDIATE_FLUSH_MS);
          } else {
            // No recent pending image to pair with
            // Create a pending text entry in case an image arrives soon
            console.log(`Creating pending text entry for pure text message: "${messageContent}"`);
            const pending: PendingTurn = {
              senderInboxId: message.senderInboxId,
              text: messageContent,
              imageMeta: null,
              replyContext: replyContext,
              timer: null,
              hasUserText: true,
              textTimestamp: Date.now(),
            };
            
            pendingByConversation.set(convId, pending);
            
            // Set a short timer to process text if no image arrives
            pending.timer = setTimeout(() => {
              // Check if we still have the same pending item (no image paired)
              const currentPending = pendingByConversation.get(convId);
              if (currentPending === pending && !currentPending.imageMeta) {
                console.log(`Text timeout - processing text-only message`);
                pendingByConversation.delete(convId);
                
                const payload: any = {
                  conversationId: convId,
                  sender: message.senderInboxId,
                  message: messageContent,
                  replyContext: replyContext || null,
                };
                
                console.log(`XMTP: Sending text-only payload:`, JSON.stringify(payload, null, 2));

                fetch(agentEndpoint, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(payload),
                  signal: AbortSignal.timeout(180000),
                }).then(async (res) => {
                  if (!res.ok) {
                    throw new Error(`Agent API error: ${res.status} ${res.statusText}`);
                  }
                  const result = await res.json();
                  const responseText = String(result.response || "");
                  console.log(`Text-only response: ${responseText.substring(0, 100)}...`);
                  await conversation.send(responseText);
                  lastProcessedByConversation.set(convId, Date.now());
                }).catch(async (error) => {
                  console.error("Error processing text-only message:", error);
                  await conversation.send("Sorry, I encountered an error processing your message.");
                });
              }
            }, DEBOUNCE_MS);
          }
        } else if (isRemoteAttachment) {
          // For attachments, check if there's recent pending text to pair with
          console.log(`Processing attachment, checking for pending text`);
          
          if (existing && existing.hasUserText && !existing.imageMeta) {
            // We have pending text, check if it's recent enough
            const now = Date.now();
            const textAge = now - (existing.textTimestamp || 0);
            if (textAge <= PAIRING_WINDOW_MS) {
              console.log(`Pairing image with pending text (age: ${textAge}ms)`);
              existing.imageMeta = imageMeta;
              existing.imageTimestamp = now;
              if (existing.timer) clearTimeout(existing.timer);
              
              // Process immediately since both parts are present
              existing.timer = setTimeout(() => {
                flushPending(client, convId).catch((e) =>
                  console.error("flushPending failed", e),
                );
              }, IMMEDIATE_FLUSH_MS);
              return; // Early return, don't continue with normal image processing
            } else {
              console.log(`Cleaning up stale pending text (age: ${textAge}ms)`);
              if (existing.timer) clearTimeout(existing.timer);
              pendingByConversation.delete(convId);
            }
          }
          
          // Normal image processing (no recent text to pair with)
          const pending: PendingTurn = {
            senderInboxId: message.senderInboxId,
            text: "Describe the image",
            imageMeta: imageMeta,
            replyContext: null,
            timer: null,
            hasUserText: false,
            imageTimestamp: Date.now(),
          };

          console.log(`Debug: Image processing - text="${pending.text}", hasUserText=${pending.hasUserText}, timestamp=${pending.imageTimestamp}`);
          pendingByConversation.set(convId, pending);

          pending.timer = setTimeout(() => {
            flushPending(client, convId).catch((e) =>
              console.error("flushPending failed", e),
            );
          }, DEBOUNCE_MS);
        }
      } catch (error) {
        console.error("Error getting agent response:", error);
        await conversation.send(
          "Sorry, I encountered an error processing your message.",
        );
      }
    }
  };

  // Start the message stream with error recovery
  while (true) {
    try {
      console.log("Starting message stream...");
      await messageStream();
      console.warn("Message stream ended unexpectedly, restarting in 5 seconds...");
      await sleep(5000);
    } catch (error) {
      console.error("Message stream error:", error);
      console.log("Restarting message stream in 10 seconds...");
      await sleep(10000);
    }
  }
}

main().catch(console.error);
