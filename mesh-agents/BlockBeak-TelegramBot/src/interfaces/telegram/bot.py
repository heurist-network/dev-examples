#!/usr/bin/env python3

import os
import logging
import telebot
import re
from datetime import datetime
from dotenv import load_dotenv
from src.core.agent import AgentManager
from src.config.settings import Settings
from src.scheduler.scheduler import SubscriptionScheduler
from src.storage.subscriptions import SubscriptionStorage
import asyncio
import concurrent.futures

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
        
        # Initialize subscription storage and scheduler
        self.storage = SubscriptionStorage()
        self.scheduler = SubscriptionScheduler(self, self.storage)
        
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
            telebot.types.BotCommand("ask", "Ask me a question"),
            telebot.types.BotCommand("subscribe", "Subscribe to recurring query: /subscribe \"query\" [time]"),
            telebot.types.BotCommand("unsubscribe", "Remove subscription: /unsubscribe id"),
            telebot.types.BotCommand("subscriptions", "List your active subscriptions"),
            telebot.types.BotCommand("save_query", "Save a query for later use: /save_query name \"query\""),
            telebot.types.BotCommand("saved_queries", "List your saved queries")
        ]
        self.bot.set_my_commands(commands)
    
    def is_authorized_chat(self, message):
        """Check if the message is from an authorized chat"""
        # If chat_id is None, don't authorize any chats
        if self.chat_id is None:
            logger.info(f"DEBUG: No authorized chat IDs configured, rejecting all")
            return False
        
        msg_chat_id = int(message.chat.id)
        
        # For debugging purposes, dump all related data
        logger.info(f"DEBUG: Authorization check - Message from user: {message.from_user.username or message.from_user.id}")
        logger.info(f"DEBUG: Authorization check - Message chat_id: {msg_chat_id} (type: {type(msg_chat_id).__name__})")
        logger.info(f"DEBUG: Authorization check - Allowed chat_ids: {self.chat_id} (type: {type(self.chat_id).__name__})")
        
        # Check each chat ID individually for debugging
        for allowed_id in self.chat_id:
            logger.info(f"DEBUG: Comparing {msg_chat_id} with allowed ID {allowed_id} (type: {type(allowed_id).__name__}): {msg_chat_id == allowed_id}")
        
        is_authorized = msg_chat_id in self.chat_id
        logger.info(f"DEBUG: Final authorization result for chat {msg_chat_id}: {is_authorized}")
        
        # If not authorized, try checking as a string just in case
        if not is_authorized and str(msg_chat_id) in [str(id) for id in self.chat_id]:
            logger.warning(f"DEBUG: Auth passed as string but failed as int. Fix your chat_id config to use integers.")
            return True
            
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
            logger.debug("extract_command: text is empty")
            return None
            
        logger.info(f"DEBUG: extract_command processing: '{text}'")
            
        # Split the text by the first space
        parts = text.split(' ', 1)
        command = parts[0]
        
        # Remove the bot username suffix if present
        if '@' in command:
            original = command
            command = command.split('@', 1)[0]
            logger.info(f"DEBUG: extract_command: stripped username from '{original}' to '{command}'")
        
        logger.info(f"DEBUG: extract_command result: '{command}'")
        return command
    
    def handle_command(self, message, command_text):
        """Generic handler for commands, including those with bot username"""
        # Extract the base command (remove bot username if present)
        command = self.extract_command(command_text)
        if not command:
            return False  # Not a command
            
        # Remove the leading slash
        command = command[1:] if command.startswith('/') else command
        
        logger.debug(f"handle_command processing: {command}")
        
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
        elif command.startswith('subscribe'):
            logger.info(f"DEBUG: handle_command detected subscribe command but is not handling it")
            # The dedicated handler should handle this
            return False
            
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
            self.bot.reply_to(message, "You are not authorized to use this bot.")
            return
            
        self.bot.reply_to(
            message,
            "🤖 *BlockBeak Bot Commands*\n\n"
            "*Basic Commands:*\n"
            "/start - Start the conversation\n"
            "/help - Show this help message\n"
            "/model - Show the current AI model\n"
            "/stats - Show your usage statistics\n"
            "/ask - Ask a question (e.g., /ask What's the weather like?)\n\n"
            
            "*Subscription Commands:*\n"
            "/subscribe \"query\" [time] - Subscribe to a recurring query (e.g., 30m, 2h)\n"
            "/unsubscribe id - Remove a subscription\n"
            "/subscriptions - List your active subscriptions\n\n"
            
            "*Saved Query Commands:*\n"
            "/save_query name \"query\" - Save a query for later use\n"
            "/saved_queries - List your saved queries\n"
            "/subscribe_saved name [time] - Subscribe to a saved query\n\n"
            
            "*Command Format Examples:*\n"
            "/subscribe \"analyze token 0x1234abcd\" 12h\n"
            "/subscribe \"check price of ETH\" 30m\n"
            "/save_query eth_price \"check current ethereum price\"\n"
            "/subscribe_saved eth_price 6h"
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
    
    def register_specific_handlers(self):
        """Register specific command handlers first"""
        
        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /help command")
                self.bot.reply_to(message, "You are not authorized to use this bot.")
                return
                
            self.bot.reply_to(
                message,
                "🤖 *BlockBeak Bot Commands*\n\n"
                "*Basic Commands:*\n"
                "/start - Start the conversation\n"
                "/help - Show this help message\n"
                "/model - Show the current AI model\n"
                "/stats - Show your usage statistics\n"
                "/ask - Ask a question (e.g., /ask What's the weather like?)\n\n"
                
                "*Subscription Commands:*\n"
                "/subscribe \"query\" [time] - Subscribe to a recurring query (e.g., 30m, 2h)\n"
                "/unsubscribe id - Remove a subscription\n"
                "/subscriptions - List your active subscriptions\n\n"
                
                "*Saved Query Commands:*\n"
                "/save_query name \"query\" - Save a query for later use\n"
                "/saved_queries - List your saved queries\n"
                "/subscribe_saved name [time] - Subscribe to a saved query\n\n"
                
                "*Command Format Examples:*\n"
                "/subscribe \"analyze token 0x1234abcd\" 12h\n"
                "/subscribe \"check price of ETH\" 30m\n"
                "/save_query eth_price \"check current ethereum price\"\n"
                "/subscribe_saved eth_price 6h"
            )
        
        @self.bot.message_handler(commands=['subscribe'])
        def subscribe_command(message):
            logger.info(f"DEBUG: subscribe_command handler called for message: {message.text}")
            
            # Always inform unauthorized users (don't silently fail)
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /subscribe command")
                try:
                    self.bot.reply_to(message, "You are not authorized to use this bot.")
                    logger.info(f"DEBUG: Sent unauthorized message to chat {message.chat.id}")
                except Exception as e:
                    logger.error(f"DEBUG: Failed to send unauthorized message: {str(e)}", exc_info=True)
                return
            
            logger.info(f"DEBUG: Chat {message.chat.id} is authorized")
            
            # Extract command text and handle empty command
            command_text = message.text[10:].strip() if len(message.text) > 10 else ""
            
            if not command_text:
                try:
                    self.bot.reply_to(
                        message,
                        "Please provide a query to subscribe to.\n\n"
                        "Format: /subscribe \"your query\" [time]\n\n"
                        "Examples:\n"
                        "/subscribe \"analyze token 0x1234abcd\" 12h\n"
                        "/subscribe \"check @elonmusk recent tweets\" 30m"
                    )
                    logger.info(f"DEBUG: Sent empty command help message")
                except Exception as e:
                    logger.error(f"DEBUG: Failed to send empty command help: {str(e)}", exc_info=True)
                return
            
            try:
                # Parse query in quotes and optional frequency
                match = re.search(r'"([^"]*)"(?:\s+([0-9]+[hm]?))?', command_text)
                logger.info(f"DEBUG: Regex match result: {match is not None}")
                
                if not match:
                    # User didn't use quotes correctly, inform them clearly without guessing
                    try:
                        self.bot.reply_to(
                            message,
                            "⚠️ Your command format is incorrect.\n\n"
                            "The query must be enclosed in double quotes (\")\n\n"
                            "Correct format: /subscribe \"your query\" [time]\n\n"
                            f"You sent: {message.text}\n\n"
                            "Example: /subscribe \"check price of ETH\" 30m"
                        )
                        logger.info(f"DEBUG: Sent format guidance message")
                    except Exception as e:
                        logger.error(f"DEBUG: Failed to send format guidance: {str(e)}", exc_info=True)
                    return
                    
                query = match.group(1)
                frequency_str = match.group(2) if match.group(2) else "24h"
                
                # Parse the frequency string to extract value and unit
                if frequency_str.endswith('m'):
                    # Minutes format
                    try:
                        frequency_minutes = int(frequency_str[:-1])
                        frequency_hours = frequency_minutes / 60
                    except ValueError:
                        self.bot.reply_to(
                            message, 
                            f"Invalid minutes value: {frequency_str}.\n\n"
                            "Example: /subscribe \"your query\" 30m"
                        )
                        return
                    
                    if frequency_minutes < 5:
                        self.bot.reply_to(
                            message, 
                            "Frequency must be at least 5 minutes.\n\n"
                            "Example: /subscribe \"your query\" 5m"
                        )
                        return
                    frequency_display = f"{frequency_minutes} minutes"
                elif frequency_str.endswith('h'):
                    # Hours format
                    try:
                        frequency_hours = int(frequency_str[:-1])
                    except ValueError:
                        self.bot.reply_to(
                            message, 
                            f"Invalid hours value: {frequency_str}.\n\n"
                            "Example: /subscribe \"your query\" 2h"
                        )
                        return
                    
                    if frequency_hours < 1:
                        self.bot.reply_to(
                            message, 
                            "Frequency must be at least 1 hour.\n\n"
                            "Example: /subscribe \"your query\" 1h"
                        )
                        return
                    frequency_display = f"{frequency_hours} hours"
                else:
                    # Default to interpreting as hours
                    try:
                        frequency_hours = int(frequency_str)
                        frequency_display = f"{frequency_hours} hours"
                    except ValueError:
                        self.bot.reply_to(
                            message, 
                            f"Invalid time format: {frequency_str}.\n\n"
                            "Use format like 30m for minutes or 2h for hours.\n"
                            "Example: /subscribe \"your query\" 30m"
                        )
                        return
                
                if not query:
                    self.bot.reply_to(
                        message, 
                        "The query inside quotes cannot be empty.\n\n"
                        "Example: /subscribe \"analyze token 0x1234abcd\" 12h"
                    )
                    return
                
                # Add subscription
                user_id = message.from_user.id
                chat_id = message.chat.id
                
                subscription_id = self.scheduler.add_subscription(
                    user_id=user_id,
                    chat_id=chat_id,
                    query=query,
                    frequency_hours=frequency_hours
                )
                
                # Get short version of ID for display
                short_id = subscription_id[:8]
                
                self.bot.reply_to(
                    message,
                    f"✅ Subscribed to: \"{query}\"\n\n"
                    f"📋 Subscription ID: {short_id}\n"
                    f"⏱️ Frequency: Every {frequency_display}\n\n"
                    f"The first update will run shortly."
                )
            except Exception as e:
                logger.error(f"DEBUG: Error in subscribe command: {str(e)}", exc_info=True)
                self.bot.reply_to(
                    message,
                    f"❌ Error processing your subscription: {str(e)}\n\n"
                    f"Please use the correct format:\n"
                    f"/subscribe \"your query\" [time]"
                )
        
        @self.bot.message_handler(commands=['start'])
        def start_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /start command")
                self.bot.reply_to(message, "You are not authorized to use this bot.")
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
        
        # Add other command handlers that were previously in handle_command method
        @self.bot.message_handler(commands=['model'])
        def model_command(message):
            self.handle_model_command(message)
        
        @self.bot.message_handler(commands=['stats'])
        def stats_command(message):
            self.handle_stats_command(message)
        
        @self.bot.message_handler(commands=['ask'])
        def ask_command(message):
            self.handle_ask_command(message)
        
        # Add the remaining command handlers here
        # Example: /unsubscribe, /subscriptions, /save_query, etc.
        @self.bot.message_handler(commands=['unsubscribe'])
        def unsubscribe_command(message):
            # Always inform unauthorized users
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /unsubscribe command")
                self.bot.reply_to(message, "You are not authorized to use this bot.")
                return
            
            try:
                # Extract subscription ID
                parts = message.text.split(maxsplit=1)
                if len(parts) < 2:
                    self.bot.reply_to(
                        message,
                        "Please provide a subscription ID: /unsubscribe id\n\n"
                        "Example: /unsubscribe abc123\n\n"
                        "Use /subscriptions to see your active subscriptions."
                    )
                    return
                
                subscription_id_prefix = parts[1].strip()
                
                # Get all user subscriptions
                user_id = message.from_user.id
                subscriptions = self.scheduler.get_user_subscriptions(user_id)
                
                if not subscriptions:
                    self.bot.reply_to(
                        message,
                        "You don't have any active subscriptions to remove.\n\n"
                        "Use /subscribe \"your query\" [time] to create one."
                    )
                    return
                
                # Find subscriptions that match the prefix
                matching_subscriptions = [
                    sub for sub in subscriptions
                    if sub['id'].startswith(subscription_id_prefix)
                ]
                
                if not matching_subscriptions:
                    # Show available subscriptions for ease of use
                    response = f"❌ No subscription found with ID starting with '{subscription_id_prefix}'.\n\n"
                    response += "Your active subscriptions:\n\n"
                    
                    for sub in subscriptions:
                        response += f"ID: {sub['id'][:8]} - \"{sub['query']}\"\n"
                    
                    response += "\nUse /unsubscribe ID to remove a specific subscription."
                    self.bot.reply_to(message, response)
                    return
                
                if len(matching_subscriptions) > 1:
                    # Multiple matches, ask for clarification
                    response = "⚠️ Multiple subscriptions match that ID. Please be more specific:\n\n"
                    for sub in matching_subscriptions:
                        response += f"ID: {sub['id'][:8]} - \"{sub['query']}\"\n"
                    self.bot.reply_to(message, response)
                    return
                
                # We have exactly one match
                subscription = matching_subscriptions[0]
                subscription_id = subscription['id']
                
                # Remove the subscription
                success = self.scheduler.remove_subscription(subscription_id)
                
                if success:
                    self.bot.reply_to(
                        message,
                        f"✅ Successfully unsubscribed from query:\n\"{subscription['query']}\"\n\n"
                        f"You can always subscribe again with:\n"
                        f"/subscribe \"{subscription['query']}\" [time]"
                    )
                else:
                    self.bot.reply_to(
                        message,
                        f"❌ Failed to remove subscription. It may have been already removed."
                    )
            except Exception as e:
                logger.error(f"Error in unsubscribe command: {str(e)}", exc_info=True)
                self.bot.reply_to(
                    message,
                    f"❌ Error removing subscription: {str(e)}\n\n"
                    f"Please use the correct format:\n"
                    f"/unsubscribe id"
                )
        
        @self.bot.message_handler(commands=['subscriptions'])
        def list_subscriptions_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /subscriptions command")
                return
            
            user_id = message.from_user.id
            subscriptions = self.scheduler.get_user_subscriptions(user_id)
            
            if not subscriptions:
                self.bot.reply_to(
                    message,
                    "You don't have any active subscriptions.\n"
                    "Use /subscribe \"your query\" [time] to create one."
                )
                return
            
            response = "📋 Your active subscriptions:\n\n"
            
            for sub in subscriptions:
                # Format next run time
                next_run_time = datetime.fromtimestamp(sub['next_run']).strftime("%Y-%m-%d %H:%M:%S")
                
                # For debugging, add raw timestamp
                logger.info(f"DEBUG: Subscription {sub['id'][:8]} next_run timestamp: {sub['next_run']}")
                
                # Fix timestamp display issue if year appears incorrect
                current_year = datetime.now().year
                display_time = datetime.fromtimestamp(sub['next_run'])
                
                # If the displayed year is more than 1 year in the future, likely an error
                if display_time.year > current_year + 1:
                    logger.warning(f"Fixing incorrect year in next_run timestamp: {display_time.year} -> {current_year}")
                    # Create a corrected time string with the current year
                    display_time = display_time.replace(year=current_year)
                    next_run_time = display_time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Format frequency display
                if sub['frequency_hours'] < 1:
                    minutes = int(sub['frequency_hours'] * 60)
                    frequency_display = f"Every {minutes} minutes"
                else:
                    frequency_display = f"Every {sub['frequency_hours']} hours"
                
                # Add subscription details to response
                response += f"ID: {sub['id'][:8]}\n"
                response += f"Query: \"{sub['query']}\"\n"
                response += f"Frequency: {frequency_display}\n"
                response += f"Next update: {next_run_time}\n\n"
            
            response += "To remove a subscription, use:\n/unsubscribe id"
            
            self.bot.reply_to(message, response)
        
        @self.bot.message_handler(commands=['save_query'])
        def save_query_command(message):
            # Always inform unauthorized users
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /save_query command")
                self.bot.reply_to(message, "You are not authorized to use this bot.")
                return
            
            # Extract command text safely
            command_text = message.text[11:].strip() if len(message.text) > 11 else ""
            
            if not command_text:
                self.bot.reply_to(
                    message,
                    "Please provide a name and query to save.\n\n"
                    "Format: /save_query name \"your query\"\n\n"
                    "Example: /save_query eth_price \"check current ethereum price\""
                )
                return
            
            try:
                # Parse name and query
                match = re.search(r'(\S+)\s+"([^"]*)"', command_text)
                
                if not match:
                    # Inform the user about the correct format without trying to guess their intent
                    self.bot.reply_to(
                        message,
                        "⚠️ Your command format is incorrect.\n\n"
                        "The name should be followed by the query in double quotes (\")\n\n"
                        "Correct format: /save_query name \"your query\"\n\n"
                        f"You sent: {message.text}\n\n"
                        "Example: /save_query eth_price \"check current ethereum price\""
                    )
                    return
                
                name = match.group(1)
                query = match.group(2)
                
                if not query:
                    self.bot.reply_to(
                        message, 
                        "The query inside quotes cannot be empty.\n\n"
                        "Example: /save_query eth_price \"check ethereum price and volume\""
                    )
                    return
                
                # Save the query
                user_id = message.from_user.id
                
                query_id = self.scheduler.save_query(user_id, name, query)
                
                self.bot.reply_to(
                    message,
                    f"✅ Saved query \"{query}\" as '{name}'.\n\n"
                    f"You can subscribe to it with:\n"
                    f"/subscribe \"{query}\" [time]\n"
                    f"or\n"
                    f"/subscribe_saved {name} [time]"
                )
            except Exception as e:
                logger.error(f"Error in save_query command: {str(e)}", exc_info=True)
                self.bot.reply_to(
                    message,
                    f"❌ Error saving query: {str(e)}\n\n"
                    f"Please use the correct format:\n"
                    f"/save_query name \"your query\""
                )
        
        @self.bot.message_handler(commands=['saved_queries'])
        def saved_queries_command(message):
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /saved_queries command")
                return
            
            user_id = message.from_user.id
            saved_queries = self.scheduler.get_user_saved_queries(user_id)
            
            if not saved_queries:
                self.bot.reply_to(
                    message,
                    "You don't have any saved queries.\n"
                    "Use /save_query name \"your query\" to create one."
                )
                return
            
            response = "📋 Your saved queries:\n\n"
            
            for query in saved_queries:
                response += f"Name: {query['name']}\n"
                response += f"Query: \"{query['query']}\"\n\n"
            
            response += "To subscribe to a saved query, use:\n/subscribe_saved name [time]"
            
            self.bot.reply_to(message, response)
        
        @self.bot.message_handler(commands=['subscribe_saved'])
        def subscribe_saved_command(message):
            # Always inform unauthorized users
            if not self.is_authorized_chat(message):
                logger.warning(f"Unauthorized chat {message.chat.id} tried to use /subscribe_saved command")
                self.bot.reply_to(message, "You are not authorized to use this bot.")
                return
            
            try:
                # Extract command text
                parts = message.text.split(maxsplit=2)
                
                if len(parts) < 2:
                    self.bot.reply_to(
                        message,
                        "Please provide a query name to subscribe to.\n\n"
                        "Format: /subscribe_saved name [time]\n\n"
                        "Example: /subscribe_saved eth_price 12h\n\n"
                        "Use /saved_queries to see your saved queries."
                    )
                    return
                
                name = parts[1]
                
                # Parse frequency
                frequency_hours = 24  # Default
                if len(parts) > 2:
                    frequency_str = parts[2]
                    
                    # Parse the frequency string
                    if frequency_str.endswith('m'):
                        # Minutes format
                        try:
                            frequency_minutes = int(frequency_str[:-1])
                            frequency_hours = frequency_minutes / 60
                            frequency_display = f"{frequency_minutes} minutes"
                        except ValueError:
                            self.bot.reply_to(
                                message,
                                f"Invalid minutes value: {frequency_str}.\n\n"
                                "Example: /subscribe_saved {name} 30m"
                            )
                            return
                        
                        if frequency_minutes < 5:
                            self.bot.reply_to(
                                message, 
                                "Frequency must be at least 5 minutes.\n\n"
                                f"Using minimum frequency of 5 minutes instead."
                            )
                            frequency_minutes = 5
                            frequency_hours = frequency_minutes / 60
                            frequency_display = f"{frequency_minutes} minutes"
                    elif frequency_str.endswith('h'):
                        # Hours format
                        try:
                            frequency_hours = int(frequency_str[:-1])
                            frequency_display = f"{frequency_hours} hours"
                        except ValueError:
                            self.bot.reply_to(
                                message,
                                f"'{frequency_str}' is not a valid time format.\n\n"
                                f"Format: /subscribe_saved {name} [time]\n\n"
                                f"Using default frequency of 24 hours instead."
                            )
                            frequency_hours = 24
                            frequency_display = "24 hours"
                    else:
                        # Default to hours
                        try:
                            frequency_hours = int(frequency_str)
                            frequency_display = f"{frequency_hours} hours"
                        except ValueError:
                            self.bot.reply_to(
                                message,
                                f"'{frequency_str}' is not a valid time format.\n\n"
                                f"Format: /subscribe_saved {name} [time]\n\n"
                                f"Using default frequency of 24 hours instead."
                            )
                            frequency_hours = 24
                            frequency_display = "24 hours"
                else:
                    frequency_display = "24 hours"
                
                if frequency_hours < 1 and frequency_hours > 0:
                    # This is fine, it's in minutes
                    pass
                elif frequency_hours < 1:
                    self.bot.reply_to(
                        message, 
                        "Frequency must be at least 1 hour.\n\n"
                        f"Using minimum frequency of 1 hour instead."
                    )
                    frequency_hours = 1
                    frequency_display = "1 hour"
                
                # Get the saved query
                user_id = message.from_user.id
                query = self.scheduler.get_saved_query(user_id, name)
                
                if not query:
                    # No saved query found - show helpful message with available queries
                    saved_queries = self.scheduler.get_user_saved_queries(user_id)
                    if saved_queries:
                        query_names = ", ".join([f"'{q['name']}'" for q in saved_queries])
                        self.bot.reply_to(
                            message,
                            f"❌ No saved query found with name '{name}'.\n\n"
                            f"Your saved queries are: {query_names}\n\n"
                            f"Use /saved_queries to see details of your saved queries."
                        )
                    else:
                        self.bot.reply_to(
                            message,
                            f"❌ No saved query found with name '{name}'.\n\n"
                            f"You don't have any saved queries yet.\n\n"
                            f"Save a query first with:\n"
                            f"/save_query {name} \"your query\""
                        )
                    return
                
                # Add subscription
                chat_id = message.chat.id
                
                subscription_id = self.scheduler.add_subscription(
                    user_id=user_id,
                    chat_id=chat_id,
                    query=query,
                    frequency_hours=frequency_hours,
                    name=name
                )
                
                # Get short version of ID for display
                short_id = subscription_id[:8]
                
                self.bot.reply_to(
                    message,
                    f"✅ Subscribed to saved query '{name}':\n\"{query}\"\n\n"
                    f"📋 Subscription ID: {short_id}\n"
                    f"⏱️ Frequency: {frequency_display}\n\n"
                    f"The first update will run shortly."
                )
            except Exception as e:
                logger.error(f"Error in subscribe_saved command: {str(e)}", exc_info=True)
                self.bot.reply_to(
                    message,
                    f"❌ Error processing your subscription: {str(e)}\n\n"
                    f"Please use the correct format:\n"
                    f"/subscribe_saved name [time]"
                )
    
    def register_catch_all_handler(self):
        """Register the catch-all handler AFTER all specific handlers"""
        
        @self.bot.message_handler(func=lambda message: True, content_types=['text'])
        def catch_all_handler(message):
            try:
                logger.info(f"DEBUG: Catch-all handler received message '{message.text}' in chat {message.chat.id} ({message.chat.type}) from {message.from_user.username or message.from_user.id}")
                
                # Special handling for /subscribe commands that should have been caught by the specific handler
                if message.text and message.text.startswith('/subscribe'):
                    logger.error(f"BUG: /subscribe command reached catch-all handler for message: {message.text}") # Log as error
                    
                    # Inform the user about an internal issue, not a format error
                    if self.is_authorized_chat(message):
                        try:
                            self.bot.reply_to(
                                message,
                                "⚙️ There was an internal issue processing the /subscribe command. "
                                "The developers have been notified. Please try again later."
                            )
                            logger.info(f"DEBUG: Sent internal error message for subscribe")
                        except Exception as reply_err:
                            logger.error(f"DEBUG: Failed to send internal error message: {str(reply_err)}", exc_info=True)
                    else:
                        logger.info(f"DEBUG: Not authorized, not sending internal error message")
                    return # Prevent falling through
                
                # Handle other unknown commands with a generic message
                if message.text and message.text.startswith('/'):
                    command = message.text.split()[0]
                    # Only reply if authorized
                    if self.is_authorized_chat(message):
                        self.bot.reply_to(
                            message,
                            f"Unknown command: {command}\n\n"
                            f"Type /help to see available commands."
                        )
                        logger.info(f"DEBUG: Sent 'unknown command' message for {command}")
                    else:
                        logger.info(f"DEBUG: Unauthorized user tried unknown command {command}")
                
            except Exception as e:
                logger.error(f"DEBUG: Error in catch_all_handler: {str(e)}", exc_info=True)
                # Only send error responses to authorized users
                if self.is_authorized_chat(message):
                    try:
                        self.bot.reply_to(
                            message,
                            f"Error processing your message: {str(e)}\n\n"
                            f"Please try again or contact the bot administrator."
                        )
                    except Exception as reply_err:
                        logger.error(f"DEBUG: Failed to send error message: {str(reply_err)}", exc_info=True)
    
    def register_handlers(self):
        """Register all message handlers"""
        # Register specific command handlers first
        self.register_specific_handlers()
        
        # Register catch-all handler last
        self.register_catch_all_handler()
    
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
            # This needs refactoring if process_message itself becomes async
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
    
    async def run(self):
        """Run the Telegram bot and scheduler concurrently."""
        logger.info("Starting Telegram bot and scheduler")
        
        loop = asyncio.get_running_loop()
        
        # Start the scheduler task
        scheduler_task = asyncio.create_task(self.scheduler.start())
        
        # Run the blocking bot polling in a separate thread
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        polling_future = loop.run_in_executor(
            executor, self.bot.infinity_polling
        )
        
        try:
            # Wait for either task to complete (polling might run forever)
            # Or wait specifically for the scheduler task if polling is background
            await asyncio.gather(scheduler_task, polling_future)
            
        except asyncio.CancelledError:
            logger.info("Main run task cancelled")
        except Exception as e:
            logger.error(f"Error in main run loop: {e}", exc_info=True)
        finally:
            logger.info("Stopping scheduler and bot polling...")
            # Stop the scheduler
            if scheduler_task and not scheduler_task.done():
                scheduler_task.cancel()
                await self.scheduler.stop() # Ensure proper cleanup
            
            # Stop the polling thread (Telebot doesn't have an explicit stop, 
            # but shutting down the executor might help)
            executor.shutdown(wait=False)
            # If infinity_polling doesn't stop gracefully, the thread might hang.
            # Consider using polling with non_stop=False in a loop for better control.
            logger.info("Shutdown complete")

def main(return_handler=False):
    """Entry point for the Telegram interface."""
    try:
        bot_handler = TelegramBotHandler()
        if return_handler:
            return bot_handler
        # Run the async run method
        asyncio.run(bot_handler.run()) 
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 