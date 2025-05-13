#!/usr/bin/env python3

import logging
import asyncio
import telebot
from src.core.agent import create_agent_manager
from src.config.settings import Settings

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBotHandler:
    def __init__(self):
        # Force reload settings to ensure we have the latest environment variables
        self.settings = Settings(force_reload=True)
        
        telegram_cfg = self.settings.get_telegram_config()
        self.token = telegram_cfg["token"]
        self.chat_id = telegram_cfg["chat_id"]
        
        logger.info(f"TelegramBotHandler initialized with chat IDs: {self.chat_id}")
        
        if not self.settings.is_telegram_configured():
            raise ValueError("Telegram bot token or chat ID not found. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file.")
        
        self.agent_manager = create_agent_manager()
        
        self.active_users = {}
        
        self.bot = telebot.TeleBot(self.token)
        self.register_handlers()
        self.setup_commands()
    
    def setup_commands(self):
        """Set up bot commands that will show up in the Telegram UI"""
        commands = [
            telebot.types.BotCommand("help", "Show help message"),
            telebot.types.BotCommand("model", "Show current AI model settings"),
            telebot.types.BotCommand("ask", "Ask me a question")
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
    
    def get_or_create_user_session(self, user_id, first_name, username):
        """Get or create a user session, centralizing the initialization logic"""
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": first_name,
                "username": username,
                "history": []
            }
        return self.active_users[user_id]
    
    def extract_entities(self, message):
        """Extract entities (like hyperlinks) from a message and format them for better processing"""
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
    
    def extract_command(self, text):
        """Extract the command from a message text, handling commands with bot username"""
        if not text:
            return None
            
        # Split the text by the first space
        parts = text.split(' ', 1)
        command = parts[0]
        
        # Remove the bot username suffix if present
        if '@' in command:
            command = command.split('@', 1)[0]
            
        return command
    
    def register_handlers(self):
        """Register message handlers"""

        
        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            if not self.is_authorized_chat(message):
                return
                
            self.bot.reply_to(
                message,
                "Here are the available commands:\n"
                "/help - Show this help message\n"
                "/model - Show the current AI model\n"
                "/ask - Ask me a question (e.g., /ask What's the weather like?)"
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
        
        @self.bot.message_handler(commands=['ask'])
        def ask_command(message):
            logger.debug(f"Received /ask command in chat {message.chat.id}")
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} attempted to use /ask command")
                return
            
            logger.debug(f"Authorization passed for /ask command in chat {message.chat.id}")    
            user_id = message.from_user.id
            logger.info(f"Processing /ask command from user {message.from_user.username or user_id}, text: '{message.text}'")
            
            self.get_or_create_user_session(
                user_id, 
                message.from_user.first_name, 
                message.from_user.username
            )
            
            # Extract the question from the message (remove /ask)
            if ' ' in message.text:
                question = message.text.split(' ', 1)[1]
                logger.info(f"Question extracted: '{question}'")
            else:
                logger.warning("Empty question in /ask command")
                self.bot.reply_to(message, "Please provide a question after /ask")
                return

            try:
                logger.debug("Calling process_message with question")
                self.process_message(message, question)
            except Exception as e:
                logger.error(f"Error in ask_command handler: {str(e)}", exc_info=True)
                try:
                    self.bot.reply_to(message, "Sorry, there was an error processing your question. Please try again.")
                except Exception as send_error:
                    logger.error(f"Failed to send error reply: {send_error}")
    
    def process_message(self, message, question_text):
        logger.info(f"Processing message for user {message.from_user.username or message.from_user.id}, text: '{question_text[:50]}...'")
        
        self.settings = Settings.reload()
        user_id = message.from_user.id
        
        if hasattr(message, 'entities') and message.entities:
            question_text = self.extract_entities(message)
            logger.debug(f"Processed entities, resulting text: '{question_text[:50]}...'")
        
        self.active_users[user_id]["history"].append({"role": "user", "content": question_text})
        self.agent_manager = create_agent_manager()
        
        logger.debug(f"Sending typing action to chat {message.chat.id}")
        self.bot.send_chat_action(message.chat.id, 'typing')
        
        waiting_msg = self.bot.reply_to(message, "Processing your request...")
        logger.debug(f"Sent waiting message with ID: {waiting_msg.message_id}")
        
        try:
            # Set up event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            start_time = loop.time()
            response = loop.run_until_complete(self.agent_manager.process_message(
                message=question_text,
                streaming=False
            ))
            logger.info(f"Agent processing completed in {loop.time() - start_time:.2f} seconds")

            # TODO: refactor this to use a new response format
            if "View trace:" in response:
                parts = response.split("\n\n", 1)
                trace_url = parts[0] if len(parts) > 0 else ""
                logger.debug(f"Trace URL: {trace_url}")
                # Keep only the actual response part
                response = parts[1] if len(parts) > 1 else ""
            
            # Store response in history (without trace URL)
            self.active_users[user_id]["history"].append({"role": "assistant", "content": response})
            
            # Delete waiting message and send response
            try:
                logger.debug(f"Deleting waiting message: {waiting_msg.message_id}")
                self.bot.delete_message(message.chat.id, waiting_msg.message_id)
            except Exception as e:
                logger.warning(f"Failed to delete waiting message: {e}")

            logger.debug(f"Response preview: {response[:100]}...")
            self.bot.reply_to(message, response)
            
        except Exception as e:
            logger.error(f"Error in process_message: {type(e).__name__}: {str(e)}", exc_info=True)
            error_message = str(e)
            
            if hasattr(e, 'details'):
                error_details = e.details
                if error_details.get('type') == 'OpenAIError':
                    error_message = (
                        f"OpenAI API Error:\n"
                        f"Message: {error_details.get('message')}\n"
                        f"Request ID: {error_details.get('request_id')}\n"
                    )
            
            self.bot.reply_to(message, f"Sorry, an error occurred: {error_message[:200]}")
    
    def run(self):
        """Run the Telegram bot."""
        try:
            asyncio.get_event_loop()
        except Exception as e:
            logger.error(f"Error checking event loop: {e}")
        
        self.bot.infinity_polling()

def main():
    try:
        settings = Settings(force_reload=True)

        agent_config = settings.get_openai_config()

        logger.info("Telegram bot configuration:")
        logger.info(f"Bot token present: {bool(settings.telegram_token)}")
        logger.info(f"Authorized chat IDs: {settings.telegram_chat_id}")
        logger.info(f"Agent model: {agent_config.get('model', 'unknown')}")
        
        bot_handler = TelegramBotHandler()
        logger.info("TelegramBotHandler created successfully")

        logger.info("Starting bot polling...")
        bot_handler.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 