"""
API Integration Module for Yumi Sugoi Discord Bot

This module handles communication between the Discord bot and the Flask API
dashboard, including real-time updates, command execution, and data synchronization.
"""

import asyncio
import json
import redis
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BotAPIIntegration:
    """Handles integration between bot and API dashboard"""
    
    def __init__(self, bot_instance, redis_url: str = 'redis://localhost:6379'):
        self.bot = bot_instance
        self.redis_client = None
        self.redis_url = redis_url
        self.is_running = False
        self.command_handlers = {}
        
        # Initialize Redis connection
        self._init_redis()
        
        # Setup command handlers
        self._setup_command_handlers()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis.from_url(self.redis_url)
            self.redis_client.ping()
            logger.info("✓ Bot API integration connected to Redis")
        except Exception as e:
            logger.warning(f"⚠ Redis connection failed: {e}")
            self.redis_client = None
    
    def _setup_command_handlers(self):
        """Setup handlers for different command types from API"""
        self.command_handlers = {
            'restart_bot': self._handle_restart_bot,
            'reload_modules': self._handle_reload_modules,
            'activate_persona_global': self._handle_activate_persona_global,
            'set_server_persona': self._handle_set_server_persona,
            'lock_channel': self._handle_lock_channel,
            'clear_user_data': self._handle_clear_user_data,
            'clear_user_memory': self._handle_clear_user_memory,
            'bulk_server_update': self._handle_bulk_server_update,
            'maintenance_mode': self._handle_maintenance_mode,
            'config_update': self._handle_config_update,
            'user_memory_updated': self._handle_user_memory_updated,
            'user_preferences_updated': self._handle_user_preferences_updated,
            'qa_pair_added': self._handle_qa_pair_added,
            'qa_pair_updated': self._handle_qa_pair_updated,
            'qa_pair_deleted': self._handle_qa_pair_deleted,
            'persona_created': self._handle_persona_created,
            'persona_updated': self._handle_persona_updated,
            'persona_deleted': self._handle_persona_deleted
        }
    
    def start(self):
        """Start the API integration"""
        if not self.redis_client:
            logger.warning("Cannot start API integration without Redis")
            return
        
        self.is_running = True
        
        # Start Redis listener thread
        listener_thread = threading.Thread(target=self._redis_listener, daemon=True)
        listener_thread.start()
        
        logger.info("✓ Bot API integration started")
    
    def stop(self):
        """Stop the API integration"""
        self.is_running = False
        logger.info("Bot API integration stopped")
    
    def _redis_listener(self):
        """Listen for commands from the API via Redis"""
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(['bot_commands'])
        
        logger.info("Listening for API commands...")
        
        for message in pubsub.listen():
            if not self.is_running:
                break
                
            if message['type'] == 'message':
                try:
                    command_data = json.loads(message['data'])
                    command_type = command_data.get('type')
                    
                    if command_type in self.command_handlers:
                        logger.info(f"Executing command: {command_type}")
                        asyncio.run_coroutine_threadsafe(
                            self.command_handlers[command_type](command_data),
                            self.bot.loop
                        )
                    else:
                        logger.warning(f"Unknown command type: {command_type}")
                        
                except Exception as e:
                    logger.error(f"Error processing command: {e}")
    
    def publish_event(self, channel: str, event_data: Dict[str, Any]):
        """Publish an event to the API via Redis"""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.publish(channel, json.dumps(event_data))
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
    
    # Bot event publishers
    def publish_bot_status(self, status: str, **kwargs):
        """Publish bot status update"""
        event_data = {
            'type': 'status_update',
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        self.publish_event('bot_events', event_data)
    
    def publish_command_used(self, user_id: str, guild_id: str, command: str, **kwargs):
        """Publish command usage event"""
        event_data = {
            'type': 'command_used',
            'user_id': user_id,
            'guild_id': guild_id,
            'command': command,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        self.publish_event('bot_events', event_data)
    
    def publish_server_event(self, guild_id: str, event_type: str, **kwargs):
        """Publish server-specific event"""
        event_data = {
            'type': event_type,
            'guild_id': guild_id,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        self.publish_event('server_events', event_data)
    
    def publish_user_event(self, user_id: str, event_type: str, **kwargs):
        """Publish user-specific event"""
        event_data = {
            'type': event_type,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        self.publish_event('user_events', event_data)
    
    # Command handlers
    async def _handle_restart_bot(self, data: Dict[str, Any]):
        """Handle bot restart command"""
        logger.info("Restart command received from API")
        self.publish_bot_status('restarting', requested_by=data.get('requested_by'))
        
        # Gracefully shutdown and restart
        await self.bot.close()
        # The actual restart would be handled by the process manager
    
    async def _handle_reload_modules(self, data: Dict[str, Any]):
        """Handle module reload command"""
        modules = data.get('modules', ['all'])
        logger.info(f"Reloading modules: {modules}")
        
        try:
            # Reload specific modules
            if 'all' in modules or 'commands' in modules:
                # Reload command modules
                pass  # Implement based on your bot structure
            
            self.publish_bot_status('modules_reloaded', modules=modules)
        except Exception as e:
            logger.error(f"Failed to reload modules: {e}")
            self.publish_bot_status('reload_failed', error=str(e))
    
    async def _handle_activate_persona_global(self, data: Dict[str, Any]):
        """Handle global persona activation"""
        persona_name = data.get('persona_name')
        logger.info(f"Activating persona globally: {persona_name}")
        
        try:
            # Import and use the persona module
            from . import persona
            await persona.set_persona_mode('global', persona_name)
            
            self.publish_bot_status('persona_activated', persona=persona_name)
        except Exception as e:
            logger.error(f"Failed to activate persona: {e}")
    
    async def _handle_set_server_persona(self, data: Dict[str, Any]):
        """Handle server-specific persona change"""
        guild_id = data.get('guild_id')
        persona_name = data.get('persona_name')
        
        try:
            from . import persona
            await persona.set_persona_mode(guild_id, persona_name)
            
            self.publish_server_event(guild_id, 'persona_changed', persona=persona_name)
        except Exception as e:
            logger.error(f"Failed to set server persona: {e}")
    
    async def _handle_lock_channel(self, data: Dict[str, Any]):
        """Handle channel lock/unlock"""
        guild_id = data.get('guild_id')
        channel_id = data.get('channel_id')
        locked = data.get('locked', False)
        
        try:
            # Update locked channels
            from .main import LOCKED_CHANNELS
            if locked:
                LOCKED_CHANNELS.add(int(channel_id))
            else:
                LOCKED_CHANNELS.discard(int(channel_id))
            
            self.publish_server_event(guild_id, 'channel_lock_changed', 
                                    channel_id=channel_id, locked=locked)
        except Exception as e:
            logger.error(f"Failed to lock/unlock channel: {e}")
    
    async def _handle_clear_user_data(self, data: Dict[str, Any]):
        """Handle user data clearing"""
        user_id = data.get('user_id')
        
        try:
            # Clear user data from bot memory
            from .main import USER_FACTS, USER_XP
            USER_FACTS.pop(user_id, None)
            USER_XP.pop(user_id, None)
            
            self.publish_user_event(user_id, 'data_cleared')
        except Exception as e:
            logger.error(f"Failed to clear user data: {e}")
    
    async def _handle_clear_user_memory(self, data: Dict[str, Any]):
        """Handle user memory clearing"""
        user_id = data.get('user_id')
        
        try:
            from .main import USER_FACTS
            USER_FACTS.pop(user_id, None)
            
            self.publish_user_event(user_id, 'memory_cleared')
        except Exception as e:
            logger.error(f"Failed to clear user memory: {e}")
    
    async def _handle_bulk_server_update(self, data: Dict[str, Any]):
        """Handle bulk server operations"""
        operation = data.get('operation')
        server_ids = data.get('server_ids', [])
        
        logger.info(f"Bulk operation '{operation}' on {len(server_ids)} servers")
        
        for guild_id in server_ids:
            self.publish_server_event(guild_id, 'bulk_update', operation=operation)
    
    async def _handle_maintenance_mode(self, data: Dict[str, Any]):
        """Handle maintenance mode toggle"""
        enabled = data.get('enabled', False)
        message = data.get('message', 'Bot is under maintenance')
        
        # Store maintenance status
        if self.redis_client:
            self.redis_client.set('bot_maintenance', json.dumps({
                'enabled': enabled,
                'message': message,
                'timestamp': datetime.utcnow().isoformat()
            }))
        
        self.publish_bot_status('maintenance_mode_changed', enabled=enabled, message=message)
    
    async def _handle_config_update(self, data: Dict[str, Any]):
        """Handle server configuration update"""
        guild_id = data.get('guild_id')
        config = data.get('config', {})
        
        self.publish_server_event(guild_id, 'config_updated', config=config)
    
    async def _handle_user_memory_updated(self, data: Dict[str, Any]):
        """Handle user memory update from dashboard"""
        user_id = data.get('user_id')
        updated_fields = data.get('updated_fields', [])
        
        self.publish_user_event(user_id, 'memory_updated_via_dashboard', fields=updated_fields)
    
    async def _handle_user_preferences_updated(self, data: Dict[str, Any]):
        """Handle user preferences update"""
        user_id = data.get('user_id')
        preferences = data.get('preferences', {})
        
        self.publish_user_event(user_id, 'preferences_updated', preferences=preferences)
    
    async def _handle_qa_pair_added(self, data: Dict[str, Any]):
        """Handle new Q&A pair addition"""
        qa_pair = data.get('qa_pair', {})
        
        # Reload Q&A data in bot if needed
        self.publish_bot_status('qa_pair_added', question=qa_pair.get('question'))
    
    async def _handle_qa_pair_updated(self, data: Dict[str, Any]):
        """Handle Q&A pair update"""
        qa_pair = data.get('qa_pair', {})
        
        self.publish_bot_status('qa_pair_updated', id=qa_pair.get('id'))
    
    async def _handle_qa_pair_deleted(self, data: Dict[str, Any]):
        """Handle Q&A pair deletion"""
        pair_id = data.get('pair_id')
        question = data.get('question')
        
        self.publish_bot_status('qa_pair_deleted', id=pair_id, question=question)
    
    async def _handle_persona_created(self, data: Dict[str, Any]):
        """Handle custom persona creation"""
        persona = data.get('persona', {})
        
        # Add to bot's persona system
        self.publish_bot_status('custom_persona_created', name=persona.get('name'))
    
    async def _handle_persona_updated(self, data: Dict[str, Any]):
        """Handle custom persona update"""
        persona = data.get('persona', {})
        
        self.publish_bot_status('custom_persona_updated', name=persona.get('name'))
    
    async def _handle_persona_deleted(self, data: Dict[str, Any]):
        """Handle custom persona deletion"""
        persona_name = data.get('persona_name')
        
        self.publish_bot_status('custom_persona_deleted', name=persona_name)


# Global instance
api_integration = None

def initialize_api_integration(bot_instance):
    """Initialize the API integration"""
    global api_integration
    api_integration = BotAPIIntegration(bot_instance)
    api_integration.start()
    return api_integration

def get_api_integration():
    """Get the API integration instance"""
    return api_integration
