#!/usr/bin/env python3

import logging
import asyncio
import telebot
import re

# Apply robust IPv4-only fix for systems with broken IPv6
try:
    import fix_ipv6_robust
    fix_ipv6_robust.apply_ipv4_fix()
except ImportError:
    # Fallback to simple fix
    try:
        import fix_ipv6
        fix_ipv6.apply_ipv4_fix()
    except ImportError:
        pass  # No fix available, continue anyway

from src.core.agent import create_agent_manager
from src.config.settings import Settings
from src.core.session.manager import get_session_manager, SessionType

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBotHandler:
    def __init__(self):
        self.settings = Settings(force_reload=True)
        
        telegram_cfg = self.settings.get_telegram_config()
        self.token = telegram_cfg["token"]
        self.chat_id = telegram_cfg["chat_id"]
        
        logger.info(f"TelegramBotHandler initialized with chat IDs: {self.chat_id}")
        
        if not self.settings.is_telegram_configured():
            raise ValueError("Telegram bot token or chat ID not found. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file.")
        
        self.agent_manager = create_agent_manager()
        self.debug_mode = self.settings.debug_mode
        
        # Initialize session manager
        self.session_manager = get_session_manager()
        # Note: cleanup task will be started when bot runs (in run method)
        
        # Keep minimal state for backward compatibility
        # Track conversation threads: message_id -> conversation_context
        self.conversation_threads = {}
        
        self.bot = telebot.TeleBot(self.token)
        self.register_handlers()
        self.setup_commands()
    
    def setup_commands(self):
        """Set up bot commands that will show up in the Telegram UI"""
        commands = [
            telebot.types.BotCommand("help", "Show help message"),
            telebot.types.BotCommand("model", "Show current AI model settings"),
            telebot.types.BotCommand("ask", "Ask me a question"),
            telebot.types.BotCommand("clear", "Clear conversation history")
        ]
        self.bot.set_my_commands(commands)
    
    def is_authorized_chat(self, message):
        """Check if the message is from an authorized chat"""
        if self.chat_id is None:
            logger.info("No authorized chat IDs configured")
            return False
        
        msg_chat_id = int(message.chat.id)

        logger.debug(f"AUTH CHECK: Message chat_id: {msg_chat_id}, Authorized IDs: {self.chat_id}")
        logger.debug(f"AUTH CHECK: Type of message chat_id: {type(msg_chat_id)}")
        logger.debug(f"AUTH CHECK: Types in authorized list: {[type(id) for id in self.chat_id]}")
        
        is_authorized = msg_chat_id in self.chat_id
        
        logger.debug(f"AUTH CHECK: Is authorized: {is_authorized}")
        
        if not is_authorized:
            logger.warning(f"Unauthorized chat {msg_chat_id} attempted access")
            
        return is_authorized
    
    async def _get_session_id(self, message):
        """Get session ID for a message"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        if chat_id < 0:  # Group chat
            return self.session_manager.get_session_id(
                SessionType.TELEGRAM_GROUP,
                chat_id=chat_id,
                user_id=user_id
            )
        else:  # Private chat
            return self.session_manager.get_session_id(
                SessionType.TELEGRAM_USER,
                user_id=user_id
            )
    
    def extract_entities(self, message):
        """Extract entities (like hyperlinks) from a user input message in TG and format them to texts for better processing"""
        if not hasattr(message, 'entities') or not message.entities:
            return message.text
            
        text = message.text
        formatted_text = ""
        last_position = 0
        
        # Sort entities by position to process them in order
        sorted_entities = sorted(message.entities, key=lambda e: e.offset)
        
        for entity in sorted_entities:
            # Add text before current entity
            formatted_text += text[last_position:entity.offset]
            
            # Extract the entity text
            entity_text = text[entity.offset:entity.offset + entity.length]
            
            # Handle different entity types
            if entity.type == 'url':
                formatted_text += f"[{entity_text}]({entity_text})"
            elif entity.type == 'text_link':
                formatted_text += f"[{entity_text}]({entity.url})"
            elif entity.type in ['bold', 'italic', 'code', 'pre']:
                formatted_text += entity_text  # Keep as is for now
            else:
                formatted_text += entity_text
                
            # Update last position
            last_position = entity.offset + entity.length
            
        # Add remaining text
        formatted_text += text[last_position:]
        
        return formatted_text
    
    def register_handlers(self):
        """Register message handlers"""
        
        # Handler for replies to bot messages
        @self.bot.message_handler(func=lambda message: message.reply_to_message is not None and 
                                                      message.reply_to_message.from_user.id == self.bot.get_me().id)
        def handle_reply(message):
            if not self.is_authorized_chat(message):
                return
            
            user_id = message.from_user.id
            logger.info(f"Processing reply from user {message.from_user.username or user_id}")
            
            # Check if this is a reply to a known bot message
            replied_msg_id = message.reply_to_message.message_id
            if replied_msg_id in self.conversation_threads:
                thread_info = self.conversation_threads[replied_msg_id]
                # Verify the user is the same as the original conversation
                if thread_info["user_id"] == user_id:
                    try:
                        self.process_message(message, is_reply=True)
                    except Exception as e:
                        logger.error(f"Error in reply handler: {str(e)}", exc_info=True)
                        error_msg = self.format_error_message(e, "Sorry, there was an error processing your follow-up question.")
                        self.send_error_reply(message, error_msg)
                else:
                    logger.warning(f"User {user_id} tried to reply to another user's conversation")
                    self.bot.reply_to(message, "You can only continue your own conversations.")
            else:
                # This is a reply to an older message, still process it as a follow-up
                try:
                    self.process_message(message, is_reply=True)
                except Exception as e:
                    logger.error(f"Error in reply handler: {str(e)}", exc_info=True)
                    error_msg = self.format_error_message(e, "Sorry, there was an error processing your follow-up question.")
                    self.send_error_reply(message, error_msg)

        
        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            if not self.is_authorized_chat(message):
                return
                
            self.bot.reply_to(
                message,
                "Here are the available commands:\n"
                "/help - Show this help message\n"
                "/model - Show the current AI model\n"
                "/ask - Ask me a question (e.g., /ask Any bullish news about ETH?)\n"
                "/clear - Clear your conversation history\n\n"
                "💡 Tip: You can reply to any of my messages to continue the conversation!"
            )
        
        @self.bot.message_handler(commands=['model'])
        def model_command(message):
            if not self.is_authorized_chat(message):
                return
                
            self.bot.reply_to(
                message,
                f"Current model: {self.agent_manager.model}\n"
                f"Temperature: {self.agent_manager.temperature}\n"
                f"Max tokens: {self.agent_manager.max_tokens}"
            )
        
        @self.bot.message_handler(commands=['clear'])
        def clear_command(message):
            if not self.is_authorized_chat(message):
                return
                
            # Clear session using async function
            async def clear_session_async():
                session_id = await self._get_session_id(message)
                session = await self.session_manager.get_or_create_session(session_id)
                await session.clear_session()
                
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(clear_session_async())
                self.bot.reply_to(message, "✅ Your conversation history has been cleared.")
                logger.info(f"Cleared session for message from {message.from_user.id}")
            except Exception as e:
                logger.error(f"Error clearing session: {e}")
                self.bot.reply_to(message, "❌ Error clearing conversation history.")
            finally:
                loop.close()
        
        @self.bot.message_handler(commands=['ask'])
        def ask_command(message):
            logger.debug(f"Received /ask command in chat {message.chat.id}")
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} attempted to use /ask command")
                return
            
            logger.debug(f"Authorization passed for /ask command in chat {message.chat.id}")    
            user_id = message.from_user.id
            logger.info(f"Processing /ask command from user {message.from_user.username or user_id}, text: '{message.text}'")
            
            # Reject empty questions
            if ' ' not in message.text or len(message.text) < 5:
                logger.warning("Empty question in /ask command")
                self.bot.reply_to(message, "Please provide a question after /ask")
                return

            try:
                self.process_message(message)
            except Exception as e:
                logger.error(f"Error in ask_command handler: {str(e)}", exc_info=True)
                error_msg = self.format_error_message(e, "Sorry, there was an error processing your question. Please try again.")
                self.send_error_reply(message, error_msg)
    
    async def process_question_async(self, question_text, session, chat_id=None):
        """Process question using session for history management"""
        # Session handles all history automatically, just pass the message
        agent_response_data = await self.agent_manager.process_message(
            message=question_text,
            streaming=False,
            session=session,
            chat_id=chat_id
        )
        return agent_response_data

    def process_message(self, message, is_reply=False):
        user_id = message.from_user.id

        # Handle entities if present
        if hasattr(message, 'entities') and message.entities:
            question_text = self.extract_entities(message)
        else:
            question_text = message.text
        
        # Remove the "/ask" command from the message if it's not a reply
        if not is_reply:
            question_text = re.sub(r'^\/ask\s+', '', question_text)
        
        logger.info(f"Question extracted: '{question_text}' (is_reply: {is_reply})")
        
        waiting_msg = self.bot.reply_to(message, "Processing your request...")
        self.bot.send_chat_action(message.chat.id, 'typing')

        async def process_with_session():
            # Get session for this user/chat
            session_id = await self._get_session_id(message)
            session = await self.session_manager.get_or_create_session(session_id)
            
            # Process message with session
            return await self.process_question_async(
                question_text,
                session=session,
                chat_id=message.chat.id
            )

        loop = asyncio.new_event_loop()
        try:
            agent_response_data = loop.run_until_complete(process_with_session())
            
            actual_output = agent_response_data["output"]
            trace_url = agent_response_data.get("trace_url")

            if trace_url:
                logger.debug(f"Trace URL: {trace_url}")
            
            try:
                self.bot.delete_message(message.chat.id, waiting_msg.message_id)
            except Exception as e:
                logger.warning(f"Failed to delete waiting message: {e}")

            logger.debug(f"Response preview: {actual_output[:100]}...")
            
            # Format response based on whether trace URL is included for this chat
            if trace_url:
                response_with_trace = f"{actual_output}\n\n🔍 View trace: {trace_url}"
                bot_reply = self.bot.reply_to(
                    message,
                    response_with_trace,
                    disable_web_page_preview=True
                )
            else:
                bot_reply = self.bot.reply_to(message, actual_output)
            
            # Store the conversation thread
            self.conversation_threads[bot_reply.message_id] = {
                "user_id": user_id,
                "chat_id": message.chat.id,
                "timestamp": bot_reply.date
            }
            
        except Exception as e:
            logger.error(f"Error in process_message: {type(e).__name__}: {str(e)}", exc_info=True)
            
            # Format error message with trace URL if available
            error_message = self.format_error_message(e)
            self.send_error_reply(message, error_message)
        finally:
            loop.close()
    
    def format_error_message(self, error: Exception, base_message: str = None) -> str:
        """Format error message with trace URL if available and debug mode is enabled."""
        from src.core.agent import AgentError
        
        # Use base message or generate from error
        if base_message:
            error_msg = base_message
        else:
            error_msg = f"Sorry, an error occurred: {str(error)[:200]}"
        
        # Check if this is an AgentError with trace_url in details
        if isinstance(error, AgentError) and hasattr(error, 'details') and error.details:
            trace_url = error.details.get('trace_url')
            if trace_url:
                error_msg += f"\n\n🔍 Debug trace: {trace_url}"
                logger.info(f"Including trace URL in error message: {trace_url}")
        
        return error_msg
    
    def send_error_reply(self, message, error_text):
        try:
            self.bot.reply_to(message, error_text)
        except Exception as send_error:
            logger.error(f"Failed to send error reply: {send_error}")
    
    def run(self):
        """Run the Telegram bot."""
        # Start the cleanup task in a separate thread with its own event loop
        import threading
        
        def run_cleanup_task():
            """Run cleanup task in a separate thread with its own event loop"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.session_manager.start_cleanup_task())
                # Keep the loop running for the cleanup task
                loop.run_forever()
            except Exception as e:
                logger.error(f"Error in cleanup task thread: {e}")
            finally:
                loop.close()
        
        # Start cleanup task in background thread
        cleanup_thread = threading.Thread(target=run_cleanup_task, daemon=True)
        cleanup_thread.start()
        logger.info("Started session cleanup task in background thread")
        
        # Run the bot with its own event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception as e:
            logger.error(f"Error with event loop: {e}")
            asyncio.set_event_loop(asyncio.new_event_loop())
        
        self.bot.infinity_polling()

def main():
    try:
        bot_handler = TelegramBotHandler()
        
        agent_config = bot_handler.settings.get_openai_config()
        logger.info("Telegram bot configuration:")
        logger.info(f"Bot token present: {bool(bot_handler.settings.telegram_token)}")
        logger.info(f"Authorized chat IDs: {bot_handler.settings.telegram_chat_id}")
        logger.info(f"Agent model: {agent_config.get('model', 'unknown')}")
        
        logger.info("Starting bot polling...")
        bot_handler.run()
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 
