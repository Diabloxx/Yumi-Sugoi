"""
Simple Bot Status Publisher for API Integration

This module allows the Discord bot to publish its status to Redis
so the API can display real-time bot statistics.
"""

import json
import redis
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class BotStatusPublisher:
    """Publishes bot status to Redis for API consumption"""
    
    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        self.redis_client = None
        self.redis_url = redis_url
        self.bot = None
        self.start_time = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("✓ Bot status publisher connected to Redis")
        except Exception as e:
            logger.warning(f"⚠ Redis connection failed: {e}")
            self.redis_client = None
    
    def set_bot_instance(self, bot_instance):
        """Set the bot instance for status updates"""
        self.bot = bot_instance
        # Set start time when bot instance is set
        if self.start_time is None:
            self.start_time = datetime.utcnow()
            logger.info(f"Bot start time recorded: {self.start_time.isoformat()}")
    
    def get_uptime_string(self):
        """Calculate and return formatted uptime string"""
        if not self.start_time:
            return "Unknown"
        
        uptime_delta = datetime.utcnow() - self.start_time
        
        # Calculate days, hours, minutes
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        # Format the uptime string
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:            return f"{minutes}m"
    
    def update_bot_status(self):
        """Update bot status in Redis"""
        if not self.redis_client or not self.bot:
            return
        
        try:
            # Basic bot status
            status_data = {
                'connected': self.bot.is_ready() if hasattr(self.bot, 'is_ready') else True,
                'latency': round(self.bot.latency * 1000) if hasattr(self.bot, 'latency') and self.bot.latency else None,
                'uptime': self.get_uptime_string(),
                'uptime_seconds': int((datetime.utcnow() - self.start_time).total_seconds()) if self.start_time else 0,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'last_update': datetime.utcnow().isoformat()
            }
            
            # Guild count
            guild_count = len(self.bot.guilds) if hasattr(self.bot, 'guilds') and self.bot.guilds else 0
            
            # Update Redis
            self.redis_client.setex('bot:status', 300, json.dumps(status_data))  # Expire in 5 minutes
            self.redis_client.setex('bot:guilds', 300, str(guild_count))
            
            logger.debug(f"Updated bot status: {guild_count} guilds, latency: {status_data['latency']}ms, uptime: {status_data['uptime']}")
            
        except Exception as e:
            logger.error(f"Failed to update bot status: {e}")
    
    def update_periodic(self, interval: int = 30):
        """Start periodic status updates"""
        if not self.redis_client:
            return
        
        import threading
        import time
        
        def update_loop():
            while True:
                try:
                    self.update_bot_status()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Error in status update loop: {e}")
                    time.sleep(interval)
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
        logger.info(f"Started periodic status updates every {interval} seconds")

# Global instance
status_publisher = None

def initialize_status_publisher(bot_instance, redis_url: str = 'redis://localhost:6379'):
    """Initialize the status publisher with bot instance"""
    global status_publisher
    status_publisher = BotStatusPublisher(redis_url)
    status_publisher.set_bot_instance(bot_instance)
    status_publisher.update_bot_status()
    status_publisher.update_periodic(30)  # Update every 30 seconds
    return status_publisher

def get_status_publisher():
    """Get the global status publisher instance"""
    return status_publisher

def update_bot_status():
    """Quick function to update bot status"""
    if status_publisher:
        status_publisher.update_bot_status()
