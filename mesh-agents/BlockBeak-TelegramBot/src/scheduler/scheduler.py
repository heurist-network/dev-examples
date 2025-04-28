#!/usr/bin/env python3

import os
import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

from ..storage.subscriptions import SubscriptionStorage
from ..core.agent import AgentManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubscriptionScheduler:
    """Scheduler for managing and running subscription queries."""
    
    def __init__(self, bot_handler, storage: Optional[SubscriptionStorage] = None):
        """Initialize the subscription scheduler.
        
        Args:
            bot_handler: Telegram bot handler for sending messages
            storage: Optional SubscriptionStorage instance
        """
        self.bot_handler = bot_handler
        self.storage = storage or SubscriptionStorage()
        self.running = False
        self.scheduler_task = None
        self.running_tasks = {}  # Track currently running subscription tasks
    
    async def start(self):
        """Start the scheduler."""
        if not self.running:
            self.running = True
            self.scheduler_task = asyncio.create_task(self.scheduler_loop())
            logger.info("Subscription scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
            self.scheduler_task = None
        
        # Cancel any running subscription tasks
        for task in self.running_tasks.values():
            task.cancel()
        
        await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
        self.running_tasks.clear()
        logger.info("Subscription scheduler stopped")
    
    async def scheduler_loop(self):
        """Main scheduler loop that checks for due subscriptions."""
        while self.running:
            try:
                # Get current time for logging and comparison
                current_time = time.time()
                current_dt = datetime.fromtimestamp(current_time)
                logger.info(f"Scheduler check at: {current_dt.strftime('%Y-%m-%d %H:%M:%S')} (timestamp: {current_time})")
                
                # Get subscriptions that are due
                due_subscriptions = self.storage.get_due_subscriptions()
                
                if due_subscriptions:
                    logger.info(f"Found {len(due_subscriptions)} due subscriptions")
                    # Log details about the due subscriptions
                    for sub in due_subscriptions:
                        next_run = datetime.fromtimestamp(sub['next_run'])
                        logger.info(f"Due subscription: {sub['id'][:8]}, next_run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}, timestamp: {sub['next_run']}")
                
                # Process each due subscription
                for subscription in due_subscriptions:
                    subscription_id = subscription['id']
                    
                    # Skip if already running
                    if subscription_id in self.running_tasks and not self.running_tasks[subscription_id].done():
                        logger.info(f"Subscription {subscription_id} is already running, skipping")
                        continue
                    
                    # Start a new task to run the subscription
                    logger.info(f"Creating task to process subscription {subscription_id[:8]}")
                    task = asyncio.create_task(self.process_subscription(subscription))
                    self.running_tasks[subscription_id] = task
                    logger.info(f"Task created for subscription {subscription_id[:8]}")
                
                # Clean up completed tasks and check for errors
                for sub_id in list(self.running_tasks.keys()):
                    task = self.running_tasks[sub_id]
                    if task.done():
                        try:
                            # Get result to prevent exceptions from being lost
                            result = task.result()
                            logger.info(f"Task for subscription {sub_id[:8]} completed successfully")
                        except asyncio.CancelledError:
                            logger.warning(f"Task for subscription {sub_id[:8]} was cancelled")
                        except Exception as e:
                            logger.error(f"Error in subscription task {sub_id[:8]}: {str(e)}", exc_info=True)
                        # Remove the task from running_tasks
                        del self.running_tasks[sub_id]
            
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}", exc_info=True)
            
            # Sleep for a bit before checking again
            await asyncio.sleep(60)  # Check every minute
    
    async def process_subscription(self, subscription: Dict[str, Any]):
        """Process a single subscription.
        
        Args:
            subscription: The subscription dictionary
        """
        # Log immediately upon entering the method
        logger.info("==== STARTING SUBSCRIPTION PROCESSING ====")
        
        try:
            subscription_id = subscription['id']
            logger.info(f"Processing subscription ID: {subscription_id}")
            
            user_id = subscription['user_id']
            chat_id = subscription['chat_id']
            query = subscription['query']
            frequency_hours = subscription['frequency_hours']
            
            logger.info(f"Processing subscription {subscription_id} for user {user_id}")
            logger.info(f"Query: '{query}', chat_id: {chat_id}, frequency: {frequency_hours}h")
            
            try:
                # Send a notification that the query is running
                logger.info(f"Sending initial notification to chat_id {chat_id}")
                try:
                    self.bot_handler.bot.send_message(
                        chat_id, 
                        f"🔄 Running your scheduled query: \"{query}\"..."
                    )
                    logger.info("Initial notification sent successfully")
                except Exception as msg_error:
                    logger.error(f"Error sending initial notification: {str(msg_error)}")
                
                # Run the query through the agent
                result = await self.run_subscription_query(query)
                
                # Update subscription times
                current_time = time.time()
                next_run = current_time + (frequency_hours * 3600)
                
                # Log the update for debugging
                logger.info(f"Updating subscription {subscription_id} times: last_run={current_time}, next_run={next_run}")
                logger.info(f"  -> Last run: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"  -> Next run: {datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')}")
                
                self.storage.update_subscription_time(subscription_id, current_time, next_run)
                
                # Format next run time
                next_run_dt = datetime.fromtimestamp(next_run)
                # Ensure year is current if it looks wrong
                current_year = datetime.now().year
                if next_run_dt.year > current_year + 1:
                    logger.warning(f"Fixing incorrect year in next_run: {next_run_dt.year} -> {current_year}")
                    next_run_dt = next_run_dt.replace(year=current_year)
                
                next_run_time = next_run_dt.strftime("%Y-%m-%d %H:%M:%S")
                
                # Send the result to the user
                self.bot_handler.bot.send_message(
                    chat_id,
                    f"📊 Scheduled query result:\n\n"
                    f"\"{query}\"\n\n"
                    f"{result}\n\n"
                    f"Next update: {next_run_time}"
                )
                
                logger.info(f"Successfully processed subscription {subscription_id}")
                
            except Exception as e:
                logger.error(f"Error processing subscription {subscription_id}: {str(e)}", exc_info=True)
                
                # Update subscription times even on error
                current_time = time.time()
                next_run = current_time + (frequency_hours * 3600)
                self.storage.update_subscription_time(subscription_id, current_time, next_run)
                
                # Calculate frequency display
                frequency_display = ""
                if frequency_hours < 1:
                    minutes = int(frequency_hours * 60)
                    frequency_display = f"{minutes} minutes"
                else:
                    hours = int(frequency_hours)
                    frequency_display = f"{hours} hours"
                
                # Send error message to user
                try:
                    self.bot_handler.bot.send_message(
                        chat_id,
                        f"❌ Error processing your scheduled query: \"{query}\"\n\n"
                        f"Error: {str(e)}\n\n"
                        f"The query will run again in {frequency_display}."
                    )
                except Exception as msg_error:
                    logger.error(f"Error sending error message: {str(msg_error)}")
        except Exception as outer_error:
            logger.error(f"Critical error in process_subscription: {str(outer_error)}", exc_info=True)
            logger.error(f"Subscription data: {subscription}")
        finally:
            logger.info("==== FINISHED SUBSCRIPTION PROCESSING ====")
    
    async def run_subscription_query(self, query: str) -> str:
        """Run a query through the agent manager.
        
        Args:
            query: The query to process
            
        Returns:
            str: The agent's response
        """
        try:
            logger.info(f"Creating agent manager for query: '{query}'")
            
            # Debug output of agent_config
            if hasattr(self.bot_handler, 'agent_config'):
                logger.info(f"Bot handler has agent_config: {self.bot_handler.agent_config}")
            else:
                logger.error("Bot handler does not have agent_config attribute")
                # Use Settings as a fallback
                from ..config.settings import Settings
                settings = Settings()
                agent_config = settings.get_agent_config()
                logger.info(f"Using fallback agent_config from Settings: {agent_config}")
            
            # Create a new agent manager with the same config as the bot
            try:
                agent_manager = AgentManager(**self.bot_handler.agent_config)
                logger.info("Successfully created AgentManager instance")
            except Exception as e:
                logger.error(f"Error creating AgentManager: {str(e)}")
                from ..config.settings import Settings
                settings = Settings()
                agent_config = settings.get_agent_config()
                logger.info(f"Trying fallback agent_config: {agent_config}")
                agent_manager = AgentManager(**agent_config)
                logger.info("Successfully created AgentManager instance with fallback config")
            
            logger.info(f"Processing message through agent manager")
            # Process message without streaming
            response = await agent_manager.process_message_robust(
                message=query,
                streaming=False
            )
            
            logger.info(f"Agent response received, length: {len(response)} characters")
            
            # Remove trace URL from the response if present
            if "View trace:" in response:
                parts = response.split("\n\n", 1)
                response = parts[1] if len(parts) > 1 else response
                logger.info("Removed trace URL from response")
            
            return response
        except Exception as e:
            logger.error(f"Error in run_subscription_query: {str(e)}", exc_info=True)
            return f"Error processing query: {str(e)}"
    
    def add_subscription(self, user_id: int, chat_id: int, query: str, 
                        frequency_hours: int, name: Optional[str] = None) -> str:
        """Add a new subscription.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            query: The query to run periodically
            frequency_hours: How often to run the query (in hours)
            name: Optional name for the subscription
            
        Returns:
            str: The subscription ID
        """
        return self.storage.add_subscription(user_id, chat_id, query, frequency_hours, name)
    
    def remove_subscription(self, subscription_id: str) -> bool:
        """Remove a subscription.
        
        Args:
            subscription_id: The subscription ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.storage.remove_subscription(subscription_id)
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all subscriptions for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of subscription dictionaries
        """
        return self.storage.get_user_subscriptions(user_id)
    
    def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get a subscription by ID.
        
        Args:
            subscription_id: The subscription ID
            
        Returns:
            The subscription dictionary or None if not found
        """
        return self.storage.get_subscription(subscription_id)
    
    def save_query(self, user_id: int, name: str, query: str) -> str:
        """Save a query for a user.
        
        Args:
            user_id: Telegram user ID
            name: Name for the saved query
            query: The query text
            
        Returns:
            str: The saved query ID
        """
        return self.storage.save_query(user_id, name, query)
    
    def get_saved_query(self, user_id: int, name: str) -> Optional[str]:
        """Get a saved query by name.
        
        Args:
            user_id: Telegram user ID
            name: Name for the saved query
            
        Returns:
            The query text or None if not found
        """
        return self.storage.get_saved_query(user_id, name)
    
    def get_user_saved_queries(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all saved queries for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of saved query dictionaries
        """
        return self.storage.get_user_saved_queries(user_id) 