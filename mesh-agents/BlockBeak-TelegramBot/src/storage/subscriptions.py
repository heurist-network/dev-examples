#!/usr/bin/env python3

import os
import json
import time
import uuid
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubscriptionStorage:
    """Storage manager for user subscriptions using SQLite."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the subscription storage.
        
        Args:
            db_path: Optional path to the SQLite database file.
                     If None, uses {workspace_dir}/data/subscriptions.db
        """
        if db_path is None:
            # Default location is in the data directory
            workspace_dir = Path(__file__).parents[2]  # Go up to BlockBeak-TelegramBot
            data_dir = workspace_dir / "data"
            os.makedirs(data_dir, exist_ok=True)
            db_path = data_dir / "subscriptions.db"
        
        self.db_path = str(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize the database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create subscriptions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            chat_id INTEGER,
            query TEXT,
            name TEXT,
            frequency_hours INTEGER,
            last_run REAL,
            next_run REAL,
            created_at REAL,
            UNIQUE(user_id, query)
        )
        ''')
        
        # Create saved_queries table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_queries (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            name TEXT,
            query TEXT,
            created_at REAL,
            UNIQUE(user_id, name)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_subscription(self, user_id: int, chat_id: int, query: str, 
                         frequency_hours: int, name: Optional[str] = None) -> str:
        """Add a new subscription for a user.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            query: The query to run periodically
            frequency_hours: How often to run the query (in hours)
            name: Optional name for the subscription
            
        Returns:
            str: The subscription ID
        """
        subscription_id = str(uuid.uuid4())
        current_time = time.time()
        current_dt = datetime.fromtimestamp(current_time)
        
        # Calculate the next run time (now for immediate execution)
        next_run = current_time
        next_run_dt = datetime.fromtimestamp(next_run)
        
        logger.info(f"Adding subscription for user {user_id}: current_time={current_dt.strftime('%Y-%m-%d %H:%M:%S')} ({current_time})")
        logger.info(f"  -> next_run={next_run_dt.strftime('%Y-%m-%d %H:%M:%S')} ({next_run})")
        logger.info(f"  -> frequency={frequency_hours} hours")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO subscriptions 
            (id, user_id, chat_id, query, name, frequency_hours, last_run, next_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                subscription_id,
                user_id,
                chat_id,
                query,
                name,
                frequency_hours,
                0,  # last_run (0 means never run)
                next_run,  # next_run (run immediately)
                current_time
            ))
            conn.commit()
            logger.info(f"Added subscription {subscription_id} for user {user_id}")
            return subscription_id
        except sqlite3.IntegrityError:
            # User already has this exact query subscribed
            logger.info(f"User {user_id} already has subscription for query: {query}")
            cursor.execute('''
            SELECT id FROM subscriptions WHERE user_id = ? AND query = ?
            ''', (user_id, query))
            existing_id = cursor.fetchone()[0]
            
            # Update the frequency
            cursor.execute('''
            UPDATE subscriptions 
            SET frequency_hours = ?, next_run = ?
            WHERE id = ?
            ''', (frequency_hours, next_run, existing_id))
            conn.commit()
            return existing_id
        finally:
            conn.close()
    
    def remove_subscription(self, subscription_id: str) -> bool:
        """Remove a subscription.
        
        Args:
            subscription_id: The ID of the subscription to remove
            
        Returns:
            bool: True if successful, False if subscription not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            logger.info(f"Removed subscription {subscription_id}")
        else:
            logger.warning(f"Failed to remove subscription {subscription_id} - not found")
        
        return success
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all subscriptions for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of subscription dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM subscriptions WHERE user_id = ? ORDER BY next_run ASC
        ''', (user_id,))
        
        subscriptions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return subscriptions
    
    def get_due_subscriptions(self) -> List[Dict[str, Any]]:
        """Get all subscriptions that are due to run.
        
        Returns:
            List of subscription dictionaries
        """
        current_time = time.time()
        current_dt = datetime.fromtimestamp(current_time)
        logger.info(f"Checking for due subscriptions at: {current_dt.strftime('%Y-%m-%d %H:%M:%S')} (timestamp: {current_time})")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all subscriptions for debugging
        cursor.execute('SELECT id, next_run FROM subscriptions ORDER BY next_run')
        all_subs = cursor.fetchall()
        for sub in all_subs:
            sub_id = sub['id']
            next_run = sub['next_run']
            next_run_dt = datetime.fromtimestamp(next_run)
            due_status = "DUE" if next_run <= current_time else "NOT DUE"
            time_diff = abs(next_run - current_time)
            logger.info(f"Subscription {sub_id[:8]}: next_run={next_run_dt.strftime('%Y-%m-%d %H:%M:%S')} ({next_run}), {due_status}, diff={time_diff:.1f}s")
        
        # Get due subscriptions
        cursor.execute('''
        SELECT * FROM subscriptions WHERE next_run <= ?
        ''', (current_time,))
        
        subscriptions = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Found {len(subscriptions)} due subscriptions out of {len(all_subs)} total")
        conn.close()
        
        return subscriptions
    
    def update_subscription_time(self, subscription_id: str, last_run: float, next_run: float) -> bool:
        """Update the run times for a subscription.
        
        Args:
            subscription_id: The ID of the subscription to update
            last_run: Timestamp of when it was last run
            next_run: Timestamp of when it should run next
            
        Returns:
            bool: True if successful, False if subscription not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE subscriptions SET last_run = ?, next_run = ? WHERE id = ?
        ''', (last_run, next_run, subscription_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific subscription by ID.
        
        Args:
            subscription_id: The ID of the subscription
            
        Returns:
            Subscription dictionary or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
        row = cursor.fetchone()
        subscription = dict(row) if row else None
        conn.close()
        
        return subscription
    
    def save_query(self, user_id: int, name: str, query: str) -> str:
        """Save a query for a user.
        
        Args:
            user_id: Telegram user ID
            name: Name for the saved query
            query: The query text
            
        Returns:
            str: The saved query ID
        """
        query_id = str(uuid.uuid4())
        current_time = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO saved_queries (id, user_id, name, query, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (query_id, user_id, name, query, current_time))
            conn.commit()
            return query_id
        except sqlite3.IntegrityError:
            # Update existing saved query
            cursor.execute('''
            UPDATE saved_queries SET query = ?, created_at = ?
            WHERE user_id = ? AND name = ?
            ''', (query, current_time, user_id, name))
            conn.commit()
            
            cursor.execute('''
            SELECT id FROM saved_queries WHERE user_id = ? AND name = ?
            ''', (user_id, name))
            query_id = cursor.fetchone()[0]
            return query_id
        finally:
            conn.close()
    
    def get_saved_query(self, user_id: int, name: str) -> Optional[str]:
        """Get a saved query by name.
        
        Args:
            user_id: Telegram user ID
            name: Name of the saved query
            
        Returns:
            The query text or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT query FROM saved_queries WHERE user_id = ? AND name = ?
        ''', (user_id, name))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def get_user_saved_queries(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all saved queries for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of saved query dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, name, query, created_at FROM saved_queries WHERE user_id = ?
        ORDER BY name ASC
        ''', (user_id,))
        
        queries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return queries 