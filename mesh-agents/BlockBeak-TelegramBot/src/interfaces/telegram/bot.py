#!/usr/bin/env python3

import os
import logging
import telebot
from dotenv import load_dotenv
from src.core.agent import AgentManager
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
        self.agent_config = self.settings.get_agent_config()
        
        logger.info(f"TelegramBotHandler initialized with chat IDs: {self.settings.telegram_chat_id}")
        
        if not self.settings.is_telegram_configured():
            raise ValueError("Telegram bot token or chat ID not found. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file.")
        
        self.token = self.settings.telegram_token
        self.chat_id = self.settings.telegram_chat_id
        
        # Create agent manager
        self.agent_manager = AgentManager(**self.agent_config)
        
        # Store active users and their conversations
        self.active_users = {}
        
        # Initialize the telebot
        self.bot = telebot.TeleBot(self.token)
        self.register_handlers()
        
        # Set up commands
        self.setup_commands()
    
    def setup_commands(self):
        """Set up bot commands that will show up in the Telegram UI"""
        commands = [
            telebot.types.BotCommand("start", "Start the conversation"),
            telebot.types.BotCommand("help", "Show help message"),
            telebot.types.BotCommand("model", "Show current AI model settings"),
            telebot.types.BotCommand("stats", "Show your usage statistics"),
            telebot.types.BotCommand("ask", "Ask me a question")
        ]
        self.bot.set_my_commands(commands)
    
    def is_authorized_chat(self, message):
        """Check if the message is from an authorized chat"""
        # If chat_id is None, don't authorize any chats
        if self.chat_id is None:
            logger.info(f"No authorized chat IDs configured")
            return False
        
        msg_chat_id = int(message.chat.id)
        # Debug the types and values
        logger.info(f"Authorization check - Message chat_id: {msg_chat_id} (type: {type(msg_chat_id)})")
        logger.info(f"Authorization check - Allowed chat_ids: {self.chat_id} (type: {type(self.chat_id)})")
        
        # Check each chat ID individually for debugging
        for allowed_id in self.chat_id:
            logger.info(f"Comparing {msg_chat_id} with allowed ID {allowed_id} (type: {type(allowed_id)}): {msg_chat_id == allowed_id}")
        
        is_authorized = msg_chat_id in self.chat_id
        logger.info(f"Final authorization result for chat {msg_chat_id}: {is_authorized}")
        return is_authorized
    
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
    
    def handle_command(self, message, command_text):
        """Generic handler for commands, including those with bot username"""
        # Extract the base command (remove bot username if present)
        command = self.extract_command(command_text)
        if not command:
            return False  # Not a command
            
        # Remove the leading slash
        command = command[1:] if command.startswith('/') else command
        
        # Handle each command
        if command == 'start':
            self.handle_start_command(message)
            return True
        elif command == 'help':
            self.handle_help_command(message)
            return True
        elif command == 'model':
            self.handle_model_command(message)
            return True
        elif command == 'stats':
            self.handle_stats_command(message)
            return True
        elif command == 'ask':
            self.handle_ask_command(message)
            return True
            
        return False  # Command not recognized
        
    def handle_start_command(self, message):
        """Handle the /start command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /start command")
            return
            
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Initialize user session if not exists
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": message.from_user.first_name,
                "username": message.from_user.username,
                "history": []
            }
        
        self.bot.reply_to(
            message, 
            f"Hello {message.from_user.first_name}! I'm an AI assistant powered by OpenAI.\n"
            f"Use /ask followed by your question to interact with me.\n"
            f"Type /help to see all available commands."
        )
        
    def handle_help_command(self, message):
        """Handle the /help command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /help command")
            return
            
        self.bot.reply_to(
            message,
            "Here are the available commands:\n"
            "/start - Start the conversation\n"
            "/help - Show this help message\n"
            "/model - Show the current AI model\n"
            "/stats - Show your usage statistics\n"
            "/ask - Ask me a question (e.g., /ask What's the weather like?)"
        )
        
    def handle_model_command(self, message):
        """Handle the /model command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /model command")
            return
            
        self.bot.reply_to(
            message,
            f"Current model: {self.agent_config['model']}\n"
            f"Temperature: {self.agent_config['temperature']}\n"
            f"Max tokens: {self.agent_config['max_tokens']}"
        )
        
    def handle_stats_command(self, message):
        """Handle the /stats command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /stats command")
            return
            
        user_id = message.from_user.id
        
        if user_id in self.active_users:
            user_data = self.active_users[user_id]
            message_count = len(user_data["history"])
            self.bot.reply_to(
                message,
                f"Your statistics:\n"
                f"Messages sent: {message_count}"
            )
        else:
            self.bot.reply_to(
                message,
                "No statistics available. Start a conversation first with /ask."
            )
            
    def handle_ask_command(self, message):
        """Handle the /ask command"""
        if not self.is_authorized_chat(message):
            logger.warning(f"Unauthorized chat {message.chat.id} tried to use /ask command")
            return
            
        user_id = message.from_user.id
        
        # Initialize user session if not exists
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "name": message.from_user.first_name,
                "username": message.from_user.username,
                "history": []
            }
        
        # Extract the question from the message (remove /ask)
        if ' ' in message.text:
            question = message.text.split(' ', 1)[1]
        else:
            self.bot.reply_to(message, "Please provide a question after /ask")
            return
        
        # Process the question
        self.process_message(message, question)
    
    def register_handlers(self):
        """Register message handlers"""
        # Debug handler to log all incoming messages
        @self.bot.message_handler(func=lambda message: True, content_types=['text'])
        def debug_handler(message):
            try:
                logger.info(f"Received message '{message.text}' in chat {message.chat.id} ({message.chat.type}) from {message.from_user.username or message.from_user.id}")
                
                # Try to handle as a command if it starts with /
                if message.text and message.text.startswith('/'):
                    if self.handle_command(message, message.text):
                        return
                    
            except Exception as e:
                logger.error(f"Error in debug_handler: {str(e)}", exc_info=True)
                
            # Let other handlers process the message
            pass
            
        @self.bot.message_handler(commands=['start'])
        def start_command(message):
            logger.info(f"Received /start command in chat {message.chat.id}")
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /start command")
                return
                
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": []
                }
            
            self.bot.reply_to(
                message, 
                f"Hello {message.from_user.first_name}! I'm an AI assistant powered by OpenAI.\n"
                f"Use /ask followed by your question to interact with me.\n"
                f"Type /help to see all available commands."
            )
        
        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /help command")
                return
                
            self.bot.reply_to(
                message,
                "Here are the available commands:\n"
                "/start - Start the conversation\n"
                "/help - Show this help message\n"
                "/model - Show the current AI model\n"
                "/stats - Show your usage statistics\n"
                "/ask - Ask me a question (e.g., /ask What's the weather like?)"
            )
        
        @self.bot.message_handler(commands=['model'])
        def model_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /model command")
                return
                
            self.bot.reply_to(
                message,
                f"Current model: {self.agent_config['model']}\n"
                f"Temperature: {self.agent_config['temperature']}\n"
                f"Max tokens: {self.agent_config['max_tokens']}"
            )
        
        @self.bot.message_handler(commands=['stats'])
        def stats_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /stats command")
                return
                
            user_id = message.from_user.id
            
            if user_id in self.active_users:
                user_data = self.active_users[user_id]
                message_count = len(user_data["history"])
                self.bot.reply_to(
                    message,
                    f"Your statistics:\n"
                    f"Messages sent: {message_count}"
                )
            else:
                self.bot.reply_to(
                    message,
                    "No statistics available. Start a conversation first with /ask."
                )

        @self.bot.message_handler(commands=['ask'])
        def ask_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /ask command")
                return
                
            user_id = message.from_user.id
            
            # Initialize user session if not exists
            if user_id not in self.active_users:
                self.active_users[user_id] = {
                    "name": message.from_user.first_name,
                    "username": message.from_user.username,
                    "history": []
                }
            
            # Extract the question from the message (remove /ask)
            if ' ' in message.text:
                question = message.text.split(' ', 1)[1]
            else:
                self.bot.reply_to(message, "Please provide a question after /ask")
                return
            
            # Process the question
            self.process_message(message, question)
    
    def process_message(self, message, question_text):
        """Process user messages through the agent manager"""
        # Reload environment variables before each request using Settings singleton
        self.settings = Settings.reload()
        
        user_id = message.from_user.id
        
        # Process entities if present in the original message
        if hasattr(message, 'entities') and message.entities:
            question_text = self.extract_entities(message)
        
        # Store the question in history
        self.active_users[user_id]["history"].append({"role": "user", "content": question_text})
        
        # Reinitialize agent manager with fresh settings
        self.agent_config = self.settings.get_agent_config()
        self.agent_manager = AgentManager(**self.agent_config)
        
        # Send "typing" action
        self.bot.send_chat_action(message.chat.id, 'typing')
        
        try:
            # Show a waiting message
            waiting_msg = self.bot.reply_to(message, "Processing your request...")
            
            # Process message through agent (async call in a sync context)
            import asyncio
            # Use robust message processing with retries and fallbacks
            response = asyncio.run(self.agent_manager.process_message_robust(
                message=question_text,
                streaming=False  # Non-streaming mode
            ))
            
            # Remove trace URL from the response if present
            if "View trace:" in response:
                parts = response.split("\n\n", 1)
                # Keep only the actual response part
                response = parts[1] if len(parts) > 1 else ""
            
            # Store response in history (without trace URL)
            self.active_users[user_id]["history"].append({"role": "assistant", "content": response})
            
            # Delete waiting message and send response
            self.bot.delete_message(message.chat.id, waiting_msg.message_id)
            self.bot.reply_to(message, response)
            
        except Exception as e:
            error_message = str(e)
            error_details = getattr(e, 'details', None)
            
            if error_details:
                if error_details.get('type') == 'OpenAIError':
                    error_message = (
                        f"OpenAI API Error:\n"
                        f"Message: {error_details.get('message')}\n"
                        f"Request ID: {error_details.get('request_id')}\n"
                        f"Status Code: {error_details.get('status_code')}"
                    )
                else:
                    error_message = (
                        f"Error Type: {error_details.get('type')}\n"
                        f"Message: {error_details.get('message')}"
                    )
            
            logger.error(f"Error processing message: {error_message}", exc_info=True)
            
            try:
                # Try to delete the waiting message if it exists
                self.bot.delete_message(message.chat.id, waiting_msg.message_id)
            except:
                pass
            
            self.bot.reply_to(
                message,
                f"Sorry, there was an error processing your request:\n\n{error_message}\n\n"
                "You can try:\n"
                "1. Rephrasing your question\n"
                "2. Waiting a few moments and trying again\n"
                "3. Using /model to check current settings"
            )
    
    def run(self):
        """Run the Telegram bot."""
        logger.info("Starting Telegram bot using pyTelegramBotAPI in non-streaming mode")
        self.bot.infinity_polling()

def main():
    """Entry point for the Telegram interface."""
    try:
        bot_handler = TelegramBotHandler()
        bot_handler.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 