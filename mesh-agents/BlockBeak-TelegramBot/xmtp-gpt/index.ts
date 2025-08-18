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
import {
  AttachmentCodec,
  RemoteAttachmentCodec,
  ContentTypeRemoteAttachment,
  type RemoteAttachment,
} from "@xmtp/content-type-remote-attachment";
import { createHash } from "node:crypto";

// Load environment variables - 一次性加载，不要重复读文件
const { WALLET_KEY, ENCRYPTION_KEY, XMTP_ENV, AGENT_ENDPOINT } =
  validateEnvironment([
    "WALLET_KEY",
    "ENCRYPTION_KEY",
    "XMTP_ENV",
    "AGENT_ENDPOINT",
  ]);

// 可选的别名配置 - 使用 validateEnvironment 以确保从 .env 加载
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

// 简单的睡眠函数
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// 在启动时构建所有mention模式 - 不要在运行时重复计算
let botMentionPatterns: Set<string> = new Set();

function initializeMentions(client: any) {
  const address = (client.accountIdentifier?.identifier || "").toLowerCase();
  if (!address) return;
  
  const with0x = address.startsWith("0x") ? address : `0x${address}`;
  
  // 添加地址的各种格式
  botMentionPatterns.add(`@${with0x}`);
  botMentionPatterns.add(`@${with0x.slice(0, 6)}…${with0x.slice(-4)}`);
  botMentionPatterns.add(`@${with0x.slice(0, 6)}...${with0x.slice(-4)}`);
  
  // 添加别名
  const aliases = (process.env.BOT_MENTION_ALIASES || BOT_MENTION_ALIASES || "")
    .split(/[,\s]+/)
    .filter(Boolean)
    .map(s => `@${s.replace(/^@+/, "").toLowerCase()}`);
  
  aliases.forEach(alias => botMentionPatterns.add(alias));
  
  console.log("Bot will respond to:", Array.from(botMentionPatterns));
}

// 简化的mention检测 - 一行搞定
function isMentioned(text: string): boolean {
  const lowerText = text.toLowerCase();
  return Array.from(botMentionPatterns).some(pattern => lowerText.includes(pattern));
}

// 清理文本中的bot mention，只保留实际内容
function cleanBotMention(text: string): string {
  let cleanedText = text;
  
  // 移除所有bot mention模式
  for (const pattern of botMentionPatterns) {
    // 移除@开头的mention
    const regex = new RegExp(`@${pattern.replace('@', '')}\\s*`, 'gi');
    cleanedText = cleanedText.replace(regex, '');
    
    // 也移除不带@的地址格式
    const addressPattern = pattern.replace('@', '');
    if (addressPattern.includes('…') || addressPattern.includes('...')) {
      const shortPattern = addressPattern.replace(/[….]/g, '');
      const shortRegex = new RegExp(`@${shortPattern}\\s*`, 'gi');
      cleanedText = cleanedText.replace(shortRegex, '');
    }
  }
  
  // 清理多余的空白字符
  cleanedText = cleanedText.trim();
  
  console.log(`  🧹 Cleaned text: "${text}" -> "${cleanedText}"`);
  return cleanedText;
}

// 获取被回复的消息
async function getReplyContext(conversation: any, messageId: string): Promise<string | null> {
  try {
    const messages = await conversation.messages();
    const original = messages.find((m: any) => m.id === messageId);
    return original?.content || null;
  } catch (e) {
    return null;
  }
}

// 加载远程图片
async function loadRemoteImage(attachment: RemoteAttachment, client: any) {
  try {
    console.log(`  🔍 Loading remote image: filename=${(attachment as any).filename}, size=${(attachment as any).contentLength || 'unknown'}`);
    
    const decrypted = await RemoteAttachmentCodec.load(attachment, client) as any;
    
    console.log(`  📊 Decrypted: mimeType=${decrypted.mimeType}, dataSize=${decrypted.data?.length || 'unknown'}`);
    
    // 验证解密后的数据
    if (!decrypted.data || decrypted.data.length === 0) {
      console.error("  ❌ Decrypted data is empty");
      return null;
    }
    
    // 检查数据大小是否合理（超过5MB的图片可能有问题）
    const dataSizeMB = decrypted.data.length / 1024 / 1024;
    if (dataSizeMB > 5) {
      console.warn(`  ⚠️ Image data is very large: ${dataSizeMB.toFixed(2)} MB`);
      
      // 如果图片太大，尝试压缩或拒绝
      if (dataSizeMB > 10) {
        console.error("  ❌ Image too large (>10MB), rejecting");
        return null;
      }
    }
    
    // 验证MIME类型
    const mime = decrypted.mimeType || "application/octet-stream";
    if (!mime.startsWith("image/")) {
      console.warn(`  ⚠️ Unexpected MIME type: ${mime}`);
    }
    
    // 转换为base64
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

// 消息配对机制 - 支持文本和图片的双向等待
const recentMessages = new Map<string, { text?: string; imageData?: any; timestamp: number }>();

// 清理过期消息
setInterval(() => {
  const now = Date.now();
  for (const [key, value] of recentMessages.entries()) {
    if (now - value.timestamp > 5000) { // 5秒后过期
      recentMessages.delete(key);
    }
  }
}, 10000); // 每10秒清理一次



// 发送消息到Agent
async function sendToAgent(conversation: any, sender: string, text: string, imageData?: any, replyContext?: string, messageId?: string) {
  console.log(`\n🤖 Sending to agent:`);
  console.log(`  - Text: "${text.slice(0, 100)}..."`);
  console.log(`  - Has image: ${!!imageData}`);
  console.log(`  - Has reply context: ${!!replyContext}`);
  
  try {
    // Phase 1: Detect mode first
    console.log(`  🔍 Phase 1: Detecting agent mode...`);
    const detectModeEndpoint = agentEndpoint.replace('/inbox', '/detect-mode');
    
    try {
      const modeResponse = await fetch(detectModeEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
        signal: AbortSignal.timeout(10000) // 10 second timeout for mode detection
      });
      
      if (modeResponse.ok) {
        const modeData = await modeResponse.json();
        const detectedMode = modeData.mode;
        console.log(`  ✅ Mode detected: ${detectedMode}`);
        
        // If deep mode, send waiting message
        if (detectedMode === "deep") {
          console.log(`  🧠 Deep mode activated, sending waiting message...`);
          await conversation.send("🧠 Deep analysis mode activated. Conducting comprehensive research...");
        }
      } else {
        console.warn(`  ⚠️ Mode detection failed: ${modeResponse.status}, continuing with normal flow`);
      }
    } catch (modeError) {
      console.warn(`  ⚠️ Mode detection error:`, modeError, `continuing with normal flow`);
    }

    // 发送反应表情（如果有消息ID）
    if (messageId) {
      try {
        const reaction: Reaction = {
          reference: messageId,
          action: "added",
          content: "👀",
          schema: "unicode"
        };
        await conversation.send(reaction, ContentTypeReaction);
        console.log(`  ✅ Sent reaction to message ${messageId.slice(0, 8)}...`);
      } catch (reactionError) {
        console.warn(`  ⚠️ Failed to send reaction:`, reactionError);
        // 继续处理，即使反应失败
      }
    }
    
    // Phase 2: Process message with agent
    console.log(`  📤 Phase 2: Processing message with agent...`);
    
    const payload: any = {
      conversationId: conversation.id,
      sender,
      message: text,
    };
    
    if (replyContext) {
      payload.replyContext = replyContext;
    }
    
    if (imageData) {
      payload.meta = imageData;
      
      // 检查图片数据大小
      const imageSizeKB = (JSON.stringify(imageData).length / 1024);
      console.log(`  - Image data size: ${imageSizeKB.toFixed(1)} KB`);
      
      if (imageSizeKB > 5000) { // 5MB
        console.warn(`  ⚠️ Image data is very large (${imageSizeKB.toFixed(1)} KB), this might cause issues`);
      }
    }
    
    const requestBody = JSON.stringify(payload);
    const totalSizeKB = requestBody.length / 1024;
    console.log(`  - Total request size: ${totalSizeKB.toFixed(1)} KB`);
    
    // 如果请求太大，给出警告
    if (totalSizeKB > 10000) { // 10MB
      console.error(`  ❌ Request too large (${totalSizeKB.toFixed(1)} KB), this will likely fail`);
      throw new Error(`Request too large: ${totalSizeKB.toFixed(1)} KB`);
    }
    
    console.log(`  📤 Sending request to ${agentEndpoint}...`);
    
    // 先测试后端连接
    try {
      console.log(`  🔍 Testing backend connection...`);
      const testResponse = await fetch(`${agentEndpoint.replace('/inbox', '')}/health`, { 
        method: 'GET',
        signal: AbortSignal.timeout(5000) // 5秒测试
      });
      console.log(`  ✅ Backend health check: ${testResponse.status}`);
    } catch (e) {
      console.warn(`  ⚠️ Backend health check failed:`, e);
    }
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      console.log(`  ⏰ Request timeout after 60 seconds, aborting...`);
      controller.abort();
    }, 60000); // 60秒超时
    
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
      await conversation.send(responseText);
      
    } catch (error: any) {
      clearTimeout(timeoutId);
      
      if (error.name === 'AbortError') {
        console.error(`  ❌ Request timed out after 60 seconds`);
        await conversation.send("Sorry, the request timed out. Please try again with a smaller image.");
      } else {
        console.error(`  ❌ Network error:`, error);
        await conversation.send("Sorry, I encountered a network error. Please try again.");
      }
      throw error; // 重新抛出错误以便上层处理
    }
    
  } catch (error) {
    console.error("  ❌ Agent error:", error);
    await conversation.send("Sorry, I encountered an error processing your request.");
  }
}

// 主消息处理循环 - 简化版本
async function processMessages(client: Client<any>) {
  console.log("Waiting for messages...");
  
  const stream = client.conversations.streamAllMessages();
  
  for await (const message of await stream) {
    // 忽略自己的消息
    if (message.senderInboxId.toLowerCase() === client.inboxId.toLowerCase()) {
      continue;
    }
    
    console.log(`\n📨 Incoming message from ${message.senderInboxId.slice(0,8)}...`);
    
    // Skip system messages like read receipts, reactions, etc.
    const systemMessageTypes = ['readReceipt', 'reaction', 'groupUpdated', 'groupMembershipChange'];
    if (message.contentType?.typeId && systemMessageTypes.includes(message.contentType.typeId)) {
      console.log(`  ⏭️  Skipping system message: ${message.contentType.typeId}`);
      continue;
    }
    
    const conversation = await client.conversations.getConversationById(message.conversationId);
    if (!conversation) continue;
    
    const isGroup = conversation instanceof Group;
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
    
    console.log(`  Type: ${isText ? 'TEXT' : isReply ? 'REPLY' : isImage ? 'IMAGE' : 'UNKNOWN'}, Group: ${isGroup}`);
    
    // 提取发送者地址
    const senderAddress = message.senderInboxId.slice(0, 6) + "..." + message.senderInboxId.slice(-4);
    
    // 处理文本消息（包括回复）
    if (isText || isReply) {
      const text = isReply ? ((message.content as Reply).content as string) : (message.content as string);
      const replyContext = isReply ? await getReplyContext(conversation, (message.content as Reply).reference as string) : null;
      
      // 群组需要检查mention
      if (isGroup && !isMentioned(text)) {
        console.log(`  ❌ Group message without mention: "${text.slice(0, 50)}..."`);
        continue;
      }
      
      console.log(`  ✅ Processing message: "${text.slice(0, 50)}..."`);
      
      // 检查是否有等待配对的图片
      const key = `${message.conversationId}:${message.senderInboxId}`;
      const recent = recentMessages.get(key);
      
      if (recent && recent.imageData && !recent.text) {
        // 找到了等待的图片，配对处理
        console.log(`  🎯 Found waiting image, processing together`);
        recentMessages.delete(key);
        const cleanedText = cleanBotMention(text);
        await sendToAgent(conversation, senderAddress, cleanedText, recent.imageData, replyContext || undefined, message.id);
      } else {
        // 没有等待的图片，只处理文本
        const cleanedText = cleanBotMention(text);
        await sendToAgent(conversation, senderAddress, cleanedText, undefined, replyContext || undefined, message.id);
      }
    }
    
    // 处理图片消息
    else if (isImage) {
      const imageData = await loadRemoteImage(message.content as RemoteAttachment, client);
      if (!imageData) continue;
      
      const key = `${message.conversationId}:${message.senderInboxId}`;
      
      // 在群组中，需要配对文本
      if (isGroup) {
        console.log(`  🖼️ Image in group, storing and waiting for text...`);
        
        // 保存图片，等待文本
        recentMessages.set(key, { imageData, timestamp: Date.now() });
        
        // 给文本一个机会到达
        await sleep(1500); // 等待1.5秒
        
        // 检查是否有文本到达
        const current = recentMessages.get(key);
        if (current && current.text && current.imageData === imageData) {
          // 文本已经到达并处理了图片，什么都不用做
          console.log(`  ✅ Text already processed this image`);
        } else if (current && current.imageData === imageData) {
          // 还是只有图片，没有文本
          console.log(`  ⏱️ No text arrived, keeping image in queue for later`);
        }
      } else {
        // 私聊中直接处理图片
        await sendToAgent(conversation, senderAddress, "Describe this image", imageData, undefined, message.id);
      }
    }
  }
}

// 主函数 - 简化启动流程
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

  // 初始化mention模式
  initializeMentions(client);

  await logAgentDetails(client as any);
  await client.conversations.sync();

  console.log("\n🚀 Bot configuration:");
  console.log(`  - Agent endpoint: ${agentEndpoint}`);
  console.log(`  - Debug mode: ${DEBUG_MODE}`);
  console.log(`  - Mention aliases: ${BOT_MENTION_ALIASES || '(none)'}`);
  console.log("\n");
  
  // 开始处理消息
  await processMessages(client);
}

// 错误处理
main().catch(error => {
  console.error("Fatal error:", error);
  process.exit(1);
});