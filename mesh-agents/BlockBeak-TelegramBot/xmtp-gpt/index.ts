import {
  createSigner,
  createUser,
  getEncryptionKeyFromHex,
  logAgentDetails,
  validateEnvironment,
} from "./helpers/client.js";
import { Client, Group, type XmtpEnv } from "@xmtp/node-sdk";
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
import { ContentTypeText } from "@xmtp/content-type-text";
import {
  AttachmentCodec,
  RemoteAttachmentCodec,
  ContentTypeRemoteAttachment,
  type RemoteAttachment,
} from "@xmtp/content-type-remote-attachment";
import { Semaphore } from "./concurrency.js";

// Load environment variables
const { WALLET_KEY, ENCRYPTION_KEY, XMTP_ENV, AGENT_ENDPOINT } =
  validateEnvironment([
    "WALLET_KEY",
    "ENCRYPTION_KEY",
    "XMTP_ENV",
    "AGENT_ENDPOINT",
  ]);

const optionalEnv = (() => {
  try {
    return validateEnvironment(["BOT_MENTION_ALIASES"]);
  } catch {
    return { BOT_MENTION_ALIASES: "" };
  }
})();
const BOT_MENTION_ALIASES = optionalEnv.BOT_MENTION_ALIASES || process.env.BOT_MENTION_ALIASES || "";

const agentEndpoint = AGENT_ENDPOINT || "http://127.0.0.1:8000/inbox";
const DEBUG_MODE = process.env.DEBUG_MODE?.toLowerCase() === 'true';

// Per-conversation chaining configuration (Option 2)
const MAX_CONCURRENCY = Math.max(1, Number(process.env.AGENT_CONCURRENCY || 8));
const AGENT_REQUEST_TIMEOUT = Number(process.env.AGENT_REQUEST_TIMEOUT || 180000);

// Per-conversation task chains
const convoTails = new Map<string, Promise<void>>();

const globalSemaphore = new Semaphore(MAX_CONCURRENCY);

/**
 * Enqueue a task for a specific conversation, ensuring serialization per conversation
 * @param convoId The conversation ID
 * @param task The async task to execute
 */
function enqueueByConversation(convoId: string, task: () => Promise<void>) {
  const prev = convoTails.get(convoId) || Promise.resolve();
  const next = prev
    .then(task)
    .catch(err => console.error(`❌ Error in conversation ${convoId}:`, err))
    .finally(() => {
      // Clean up the tail if it's still the current one
      if (convoTails.get(convoId) === next) {
        convoTails.delete(convoId);
      }
    });
  convoTails.set(convoId, next);
  console.log(`📥 Enqueued task for conversation ${convoId.slice(0, 8)}... (${convoTails.size} active conversations)`);
}

// 简单的睡眠函数
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// 在启动时构建所有mention模式 - 不要在运行时重复计算
let botMentionPatterns: Set<string> = new Set();

function initializeMentions(client: any) {
  const address = (client.accountIdentifier?.identifier || "").toLowerCase();
  if (!address) return;
  
  const with0x = address.startsWith("0x") ? address : `0x${address}`;
  
  // add all address formats
  botMentionPatterns.add(`@${with0x}`);
  botMentionPatterns.add(`@${with0x.slice(0, 6)}…${with0x.slice(-4)}`);
  botMentionPatterns.add(`@${with0x.slice(0, 6)}...${with0x.slice(-4)}`);
  
  // add aliases
  const aliases = (process.env.BOT_MENTION_ALIASES || BOT_MENTION_ALIASES || "")
    .split(/[,\s]+/)
    .filter(Boolean)
    .map(s => `@${s.replace(/^@+/, "").toLowerCase()}`);
  
  aliases.forEach(alias => botMentionPatterns.add(alias));
  
  console.log("Bot will respond to:", Array.from(botMentionPatterns));
}

function isMentioned(text: string): boolean {
  const lowerText = text.toLowerCase();
  return Array.from(botMentionPatterns).some(pattern => lowerText.includes(pattern));
}

function cleanBotMention(text: string): string {
  let cleanedText = text;
  
  for (const pattern of botMentionPatterns) {
    const regex = new RegExp(`@${pattern.replace('@', '')}\\s*`, 'gi');
    cleanedText = cleanedText.replace(regex, '');
    
    const addressPattern = pattern.replace('@', '');
    if (addressPattern.includes('…') || addressPattern.includes('...')) {
      const shortPattern = addressPattern.replace(/[….]/g, '');
      const shortRegex = new RegExp(`@${shortPattern}\\s*`, 'gi');
      cleanedText = cleanedText.replace(shortRegex, '');
    }
  }
  
  cleanedText = cleanedText.trim();
  
  console.log(`  🧹 Cleaned text: "${text}" -> "${cleanedText}"`);
  return cleanedText;
}

async function getReplyContext(conversation: any, messageId: string): Promise<string | null> {
  try {
    const messages = await conversation.messages();
    const original = messages.find((m: any) => m.id === messageId);
    return original?.content || null;
  } catch (e) {
    return null;
  }
}

async function loadRemoteImage(attachment: RemoteAttachment, client: any) {
  try {
    console.log(`  🔍 Loading remote image: filename=${(attachment as any).filename}, size=${(attachment as any).contentLength || 'unknown'}`);
    
    const decrypted = await RemoteAttachmentCodec.load(attachment, client) as any;
    
    console.log(`  📊 Decrypted: mimeType=${decrypted.mimeType}, dataSize=${decrypted.data?.length || 'unknown'}`);
    
    if (!decrypted.data || decrypted.data.length === 0) {
      console.error("  ❌ Decrypted data is empty");
      return null;
    }
    
    const dataSizeMB = decrypted.data.length / 1024 / 1024;
    if (dataSizeMB > 5) {
      console.warn(`  ⚠️ Image data is very large: ${dataSizeMB.toFixed(2)} MB`);
      
      if (dataSizeMB > 10) {
        console.error("  ❌ Image too large (>10MB), rejecting");
        return null;
      }
    }
    
    const mime = decrypted.mimeType || "application/octet-stream";
    if (!mime.startsWith("image/")) {
      console.warn(`  ⚠️ Unexpected MIME type: ${mime}`);
    }
    
    const base64Data = Buffer.from(decrypted.data).toString("base64");
    console.log(`  🔄 Base64 conversion: ${base64Data.length} chars`);
    
    const dataUrl = `data:${mime};base64,${base64Data}`;
    
    console.log(`  ✅ Image loaded successfully: ${mime}, ${dataSizeMB.toFixed(2)} MB`);
    
    return {
      image_data_url: dataUrl,
      filename: decrypted.filename,
      mime_type: mime,
    };
  } catch (e) {
    console.error("  ❌ Failed to load image:", e);
    return null;
  }
}

// match image and text
const recentMessages = new Map<string, { text?: string; imageData?: any; timestamp: number }>();

// clean expired messages
setInterval(() => {
  const now = Date.now();
  for (const [key, value] of recentMessages.entries()) {
    if (now - value.timestamp > 5000) { // 5 seconds later
      recentMessages.delete(key);
    }
  }
}, 10000); // 10 seconds later



// send message to openai agent to process
// All message sending (reactions, waiting messages, replies) happens in the per-conversation task
async function sendToAgent(sender: string, text: string, imageData?: any, replyContext?: string, messageId?: string, conversationId?: string) {
  console.log(`\n🤖 Calling agent:`);
  console.log(`  - Text: "${text.slice(0, 100)}..."`);
  console.log(`  - Has image: ${!!imageData}`);
  console.log(`  - Has reply context: ${!!replyContext}`);
  
  try {
    
    // Process message with agent
    console.log(`  📤 Processing message with agent...`);
    
    const payload: any = {
      conversationId: conversationId,
      sender,
      message: text,
      id: messageId,  // Include message ID for server-side deduplication
    };
    
    if (replyContext) {
      payload.replyContext = replyContext;
    }
    
    if (imageData) {
      payload.meta = imageData;
      
      // check image data size
      const imageSizeKB = (JSON.stringify(imageData).length / 1024);
      console.log(`  - Image data size: ${imageSizeKB.toFixed(1)} KB`);
      
      if (imageSizeKB > 5000) { // 5MB
        console.warn(`  ⚠️ Image data is very large (${imageSizeKB.toFixed(1)} KB), this might cause issues`);
      }
    }
    
    const requestBody = JSON.stringify(payload);
    const totalSizeKB = requestBody.length / 1024;
    console.log(`  - Total request size: ${totalSizeKB.toFixed(1)} KB`);
    
    // if request is too large, give warning
    if (totalSizeKB > 10000) { // 10MB
      console.error(`  ❌ Request too large (${totalSizeKB.toFixed(1)} KB), this will likely fail`);
      throw new Error(`Request too large: ${totalSizeKB.toFixed(1)} KB`);
    }
    
    console.log(`  📤 Sending request to ${agentEndpoint}...`);
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      console.log(`  ⏰ Request timeout after ${AGENT_REQUEST_TIMEOUT / 1000} seconds, aborting...`);
      controller.abort();
    }, AGENT_REQUEST_TIMEOUT); // Configurable timeout
    
    try {
      const response = await fetch(agentEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: requestBody,
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      console.log(`  📥 Response received: ${response.status} ${response.statusText}`);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`  ❌ Agent returned ${response.status}: ${errorText.slice(0, 200)}`);
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      const responseText = data.response || String(data);
      console.log(`  ✅ Agent responded: "${responseText.slice(0, 100)}..."`);
      
      // Return the response and detected mode
      return { responseText, detectedMode: null };
      
    } catch (error: any) {
      clearTimeout(timeoutId);
      
      if (error.name === 'AbortError') {
        console.error(`  ❌ Request timed out after ${AGENT_REQUEST_TIMEOUT / 1000} seconds`);
        return { 
          responseText: `Sorry, the request timed out after ${AGENT_REQUEST_TIMEOUT / 1000} seconds. Please try again.`,
          isError: true 
        };
      } else {
        console.error(`  ❌ Network error:`, error);
        return { 
          responseText: "Sorry, I encountered a network error. Please try again.",
          isError: true 
        };
      }
    }
    
  } catch (error) {
    console.error("  ❌ Agent error:", error);
    return { 
      responseText: "Sorry, I encountered an error processing your request.",
      isError: true 
    };
  }
}

function cleanupExpiredMessages() {
  const now = Date.now();
  const EXPIRY_TIME = 60000; // 60 seconds later
  
  for (const [key, value] of recentMessages.entries()) {
    if (now - value.timestamp > EXPIRY_TIME) {
      console.log(`  🧹 Cleaning up expired message for key: ${key}`);
      recentMessages.delete(key);
    }
  }
}

// main message processing loop
async function processMessages(client: Client<any>) {
  console.log("Waiting for messages...");
  console.log(`🚀 Per-conversation chaining initialized with max concurrency: ${MAX_CONCURRENCY}`);
  
  // clean expired messages
  setInterval(cleanupExpiredMessages, 30000); // 30 seconds later
  
  // print status
  setInterval(() => {
    console.log(`📊 Active conversations: ${convoTails.size}`);
  }, 30000);
  
  const stream = await client.conversations.streamAllMessages();
  
  for await (const message of stream) {
    // ignore messages from the same agent
    if (message.senderInboxId.toLowerCase() === client.inboxId.toLowerCase()) {
      continue;
    }
    
    console.log(`\n📨 Incoming message from ${message.senderInboxId.slice(0,8)}...`);
    
    // skip system messages like read receipts, reactions, etc.
    const systemMessageTypes = ['readReceipt', 'reaction', 'groupUpdated', 'groupMembershipChange'];
    if (message.contentType?.typeId && systemMessageTypes.includes(message.contentType.typeId)) {
      console.log(`  ⏭️  Skipping system message: ${message.contentType.typeId}`);
      continue;
    }
    
    const conversation = await client.conversations.getConversationById(message.conversationId);
    if (!conversation) continue;
    
    // Use the official metadata approach to determine conversation type
    let isDm = false;
    let isGroup = false;
    
    try {
      const meta = await conversation.metadata();
      isDm = meta.conversationType === 'dm';
      isGroup = meta.conversationType === 'group';
      console.log(`  ℹ️ Detected as ${meta.conversationType.toUpperCase()}`);
    } catch (error) {
      // If metadata is not available, fall back to instanceof check
      console.log(`  ⚠️ Could not determine conversation type from metadata, falling back to type check`);
      isGroup = conversation instanceof Group;
      isDm = !isGroup;
      console.log(`  ℹ️ Type check result: ${isGroup ? 'Group' : 'DM'}`);
    }
    // Check for text messages - handle case where contentType might be undefined for plain text
    const isText = !message.contentType || message.contentType?.typeId === "text";
    const isReply = message.contentType?.sameAs(ContentTypeReply);
    const isImage = message.contentType?.sameAs(ContentTypeRemoteAttachment) || 
                    message.contentType?.typeId === "remoteStaticAttachment";
    
    // Skip unsupported message types
    if (!isText && !isReply && !isImage) {
      console.log(`  ⏭️  Skipping unsupported message type: ${message.contentType?.typeId || 'undefined'}`);
      continue;
    }
    
    console.log(`  Type: ${isText ? 'TEXT' : isReply ? 'REPLY' : isImage ? 'IMAGE' : 'UNKNOWN'}, ${isDm ? 'DM' : isGroup ? 'Group' : 'Unknown'}`);
    
    // full senderInboxId for attribution and rate limiting
    const senderAddress = message.senderInboxId;
    
    // process text message (including reply)
    if (isText || isReply) {
      const text = isReply ? ((message.content as Reply).content as string) : (message.content as string);
      const replyContext = isReply ? await getReplyContext(conversation, (message.content as Reply).reference as string) : null;
      
      // group need to check mention
      if (isGroup && !isMentioned(text)) {
        console.log(`  ❌ Group message without mention: "${text.slice(0, 50)}..."`);
        continue;
      }
      
      console.log(`  ✅ Processing message: "${text.slice(0, 50)}..."`);
      
      // check if there is a waiting image
      const key = `${message.conversationId}:${message.senderInboxId}`;
      const recent = recentMessages.get(key);
      
      // if there is a waiting image, process together
      if (recent && recent.imageData && !recent.text) {
        console.log(`  🎯 Found waiting image, processing together`);
        recentMessages.delete(key);
        const cleanedText = cleanBotMention(text);
        
        // use per-conversation chaining to process message
        enqueueByConversation(message.conversationId, async () => {
          const release = await globalSemaphore.acquire();
          try {
            // Send reaction first, in-order
            if (message.id) {
              try {
                const reaction: Reaction = {
                  reference: message.id,
                  action: "added",
                  content: "👀",
                  schema: "unicode"
                };
                await conversation.send(reaction, ContentTypeReaction);
                console.log(`  ✅ Sent reaction to message ${message.id.slice(0, 8)}...`);
              } catch (reactionError) {
                console.warn(`  ⚠️ Failed to send reaction:`, reactionError);
              }
            }
            
            // Detect mode and send wait message if deep mode
            let detectedMode = null;
            try {
              const detectModeEndpoint = agentEndpoint.replace('/inbox', '/detect-mode');
              const modeResponse = await fetch(detectModeEndpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: cleanedText }),
                signal: AbortSignal.timeout(10000)
              });
              
              if (modeResponse.ok) {
                const modeData = await modeResponse.json();
                detectedMode = modeData.mode;
                console.log(`  ✅ Mode detected: ${detectedMode}`);
                
                if (detectedMode === "deep" && message.id) {
                  console.log(`  🧠 Deep mode activated, sending waiting message...`);
                  const waitingMessage = "🧠 Deep analysis mode activated. Conducting comprehensive research...";
                  const reply: Reply = {
                    reference: message.id,
                    contentType: ContentTypeText,
                    content: waitingMessage,
                  };
                  await conversation.send(reply, ContentTypeReply);
                }
              }
            } catch (modeError) {
              console.warn(`  ⚠️ Mode detection error:`, modeError);
            }
            
            // Call the agent
            const result = await sendToAgent(senderAddress, cleanedText, recent.imageData, replyContext || undefined, message.id, message.conversationId);
            
            // Send final reply
            if (message.id) {
              const reply: Reply = {
                reference: message.id,
                contentType: ContentTypeText,
                content: result.responseText,
              };
              await conversation.send(reply, ContentTypeReply);
            } else {
              await conversation.send(result.responseText);
            }
          } finally {
            release();
          }
        });
      } else {
        // process text message
        const cleanedText = cleanBotMention(text);
        
        // use per-conversation chaining to process message
        enqueueByConversation(message.conversationId, async () => {
          const release = await globalSemaphore.acquire();
          try {
            // Send reaction first, in-order
            if (message.id) {
              try {
                const reaction: Reaction = {
                  reference: message.id,
                  action: "added",
                  content: "👀",
                  schema: "unicode"
                };
                await conversation.send(reaction, ContentTypeReaction);
                console.log(`  ✅ Sent reaction to message ${message.id.slice(0, 8)}...`);
              } catch (reactionError) {
                console.warn(`  ⚠️ Failed to send reaction:`, reactionError);
              }
            }
            
            // Detect mode and send wait message if deep mode
            let detectedMode = null;
            try {
              const detectModeEndpoint = agentEndpoint.replace('/inbox', '/detect-mode');
              const modeResponse = await fetch(detectModeEndpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: cleanedText }),
                signal: AbortSignal.timeout(10000)
              });
              
              if (modeResponse.ok) {
                const modeData = await modeResponse.json();
                detectedMode = modeData.mode;
                console.log(`  ✅ Mode detected: ${detectedMode}`);
                
                if (detectedMode === "deep" && message.id) {
                  console.log(`  🧠 Deep mode activated, sending waiting message...`);
                  const waitingMessage = "🧠 Deep analysis mode activated. Conducting comprehensive research...";
                  const reply: Reply = {
                    reference: message.id,
                    contentType: ContentTypeText,
                    content: waitingMessage,
                  };
                  await conversation.send(reply, ContentTypeReply);
                }
              }
            } catch (modeError) {
              console.warn(`  ⚠️ Mode detection error:`, modeError);
            }
            
            // Call the agent
            const result = await sendToAgent(senderAddress, cleanedText, undefined, replyContext || undefined, message.id, message.conversationId);
            
            // Send final reply
            if (message.id) {
              const reply: Reply = {
                reference: message.id,
                contentType: ContentTypeText,
                content: result.responseText,
              };
              await conversation.send(reply, ContentTypeReply);
            } else {
              await conversation.send(result.responseText);
            }
          } finally {
            release();
          }
        });
      }
    }
    
    //  process image message
    else if (isImage) {
      const imageData = await loadRemoteImage(message.content as RemoteAttachment, client);
      if (!imageData) continue;
      
      const key = `${message.conversationId}:${message.senderInboxId}`;
      
      // in group or dm, try to pair text and image
      // because user may send text and image together
      console.log(`  🖼️ Image received in ${isDm ? 'DM' : 'group'}, storing and waiting for text...`);
      
      // save image, waiting for text
      recentMessages.set(key, { imageData, timestamp: Date.now() });
      
      await sleep(2000); // wait 2 seconds, give dm more time
      
      // check if there is text
      const current = recentMessages.get(key);
      if (current && current.text && current.imageData === imageData) {
        // text already processed this image
        console.log(`  ✅ Text already processed this image`);
      } else if (current && current.imageData === imageData) {
        // still only image
        if (isDm) {
          // wait longer in dm, if no text, use default description
          console.log(`  ⏱️ No text arrived in DM, waiting a bit more...`);
          await sleep(1500); // wait 1.5 seconds
          
          const finalCheck = recentMessages.get(key);
          if (finalCheck && !finalCheck.text && finalCheck.imageData === imageData) {
            console.log(`  📤 Processing image with default text in DM`);
            recentMessages.delete(key);
            
            // use per-conversation chaining to process message
            enqueueByConversation(message.conversationId, async () => {
              const release = await globalSemaphore.acquire();
              try {
                // Send reaction first, in-order
                if (message.id) {
                  try {
                    const reaction: Reaction = {
                      reference: message.id,
                      action: "added",
                      content: "👀",
                      schema: "unicode"
                    };
                    await conversation.send(reaction, ContentTypeReaction);
                    console.log(`  ✅ Sent reaction to message ${message.id.slice(0, 8)}...`);
                  } catch (reactionError) {
                    console.warn(`  ⚠️ Failed to send reaction:`, reactionError);
                  }
                }
                
                // Call the agent
                const result = await sendToAgent(senderAddress, "analyze this image", imageData, undefined, message.id, message.conversationId);
                
                // Send final reply
                if (message.id) {
                  const reply: Reply = {
                    reference: message.id,
                    contentType: ContentTypeText,
                    content: result.responseText,
                  };
                  await conversation.send(reply, ContentTypeReply);
                } else {
                  await conversation.send(result.responseText);
                }
              } finally {
                release();
              }
            });
          }
        } else {
          // keep image in queue for later
          console.log(`  ⏱️ No text arrived, keeping image in queue for later`);
        }
      }
    }
  }
}

// graceful shutdown
async function gracefulShutdown(signal: string) {
  console.log(`\n⚠️ Received ${signal}, initiating graceful shutdown...`);
  
  // wait for all conversation chains to complete
  if (convoTails.size > 0) {
    console.log(`⏳ Waiting for ${convoTails.size} conversation chains to complete...`);
    try {
      await Promise.race([
        Promise.all(Array.from(convoTails.values())),
        new Promise(resolve => setTimeout(resolve, 15000)) // 15 second timeout
      ]);
    } catch (error) {
      console.error("Error during shutdown:", error);
    }
  }
  
  console.log("👋 Shutdown complete");
  process.exit(0);
}

// main function
async function main() {
  const user = createUser(WALLET_KEY);
  const signer = createSigner(user.key);

  const client = await Client.create(signer, {
    env: (XMTP_ENV as XmtpEnv) || "production",
    dbEncryptionKey: getEncryptionKeyFromHex(ENCRYPTION_KEY),
    codecs: [
      new ReactionCodec(),
      new ReplyCodec(),
      new AttachmentCodec(),
      new RemoteAttachmentCodec(),
    ],
  });

  // initialize mention patterns
  initializeMentions(client);
  
  // test backend health at startup
  try {
    console.log(`🔍 Testing backend connection at startup...`);
    const healthResponse = await fetch(`${agentEndpoint.replace('/inbox', '')}/health`, { 
      method: 'GET',
      signal: AbortSignal.timeout(5000)
    });
    console.log(`✅ Backend health check passed: ${healthResponse.status}`);
  } catch (e) {
    console.error(`❌ Backend health check failed at startup:`, e);
    console.error(`Please ensure the backend is running at ${agentEndpoint}`);
  }
  
  // shutdown handler
  process.on('SIGINT', () => gracefulShutdown('SIGINT'));
  process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));

  await logAgentDetails(client as any);
  await client.conversations.sync();

  console.log("\n🚀 Bot configuration:");
  console.log(`  - Agent endpoint: ${agentEndpoint}`);
  console.log(`  - Debug mode: ${DEBUG_MODE}`);
  console.log(`  - Mention aliases: ${BOT_MENTION_ALIASES || '(none)'}`);
  console.log(`  - Max concurrency: ${MAX_CONCURRENCY}`);
  console.log("\n");
  
  // start processing messages
  await processMessages(client);
}

// error handler
main().catch(error => {
  console.error("Fatal error:", error);
  process.exit(1);
});