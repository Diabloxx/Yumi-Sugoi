"""
Server management API routes for Yumi Sugoi Discord Bot Dashboard

Provides endpoints for managing Discord servers/guilds that the bot is in,
including configuration, member stats, and server-specific settings.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional

from .app import (
    bot_instance, db, redis_client, 
    require_api_key, require_discord_auth, require_admin,
    ServerConfig, User
)

servers_bp = Blueprint('servers', __name__)

def get_server_stats(guild_id: str) -> Dict:
    """Get comprehensive server statistics"""
    if not bot_instance:
        return {}
    
    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        return {}
    
    # Basic guild info
    stats = {
        'id': str(guild.id),
        'name': guild.name,
        'icon': str(guild.icon.url) if guild.icon else None,
        'member_count': guild.member_count,
        'owner_id': str(guild.owner_id),
        'created_at': guild.created_at.isoformat(),
        'premium_tier': guild.premium_tier,
        'boost_count': guild.premium_subscription_count,
        'features': guild.features,
        'verification_level': str(guild.verification_level),
        'nsfw_level': str(guild.nsfw_level),
        'channels': {
            'total': len(guild.channels),
            'text': len(guild.text_channels),
            'voice': len(guild.voice_channels),
            'categories': len(guild.categories)
        },
        'roles': len(guild.roles),
        'emojis': len(guild.emojis),
        'stickers': len(guild.stickers)
    }
    
    # Member statistics
    if guild.members:
        bots = sum(1 for member in guild.members if member.bot)
        humans = guild.member_count - bots
        online = sum(1 for member in guild.members if member.status != discord.Status.offline)
        
        stats['member_stats'] = {
            'total': guild.member_count,
            'humans': humans,
            'bots': bots,
            'online': online,
            'offline': guild.member_count - online
        }
    
    # Activity data from Redis cache
    if redis_client:
        try:
            activity_key = f"server_activity:{guild_id}"
            activity_data = redis_client.get(activity_key)
            if activity_data:
                stats['activity'] = json.loads(activity_data)
        except Exception as e:
            print(f"Failed to get activity data: {e}")
    
    return stats

@servers_bp.route('/api/servers', methods=['GET'])
@require_discord_auth
def get_servers():
    """Get list of all servers the bot is in"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not connected'}), 503
        
        servers = []
        for guild in bot_instance.guilds:
            # Check if user has access to this server
            user_id = getattr(request, 'user_id', None)
            if user_id:
                member = guild.get_member(int(user_id))
                if not member:
                    continue  # User not in this server
            
            server_data = get_server_stats(str(guild.id))
            
            # Get server config from database
            config = ServerConfig.query.filter_by(guild_id=str(guild.id)).first()
            if config:
                server_data['config'] = config.to_dict()
            
            servers.append(server_data)
        
        return jsonify({
            'servers': servers,
            'total_count': len(servers)
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get servers: {str(e)}'}), 500

@servers_bp.route('/api/servers/<guild_id>', methods=['GET'])
@require_discord_auth
def get_server(guild_id):
    """Get detailed information about a specific server"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not connected'}), 503
        
        guild = bot_instance.get_guild(int(guild_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        # Check if user has access to this server
        user_id = getattr(request, 'user_id', None)
        if user_id:
            member = guild.get_member(int(user_id))
            if not member:
                return jsonify({'error': 'Access denied'}), 403
        
        server_data = get_server_stats(guild_id)
        
        # Get detailed channel information
        channels = []
        for channel in guild.channels:
            channel_data = {
                'id': str(channel.id),
                'name': channel.name,
                'type': str(channel.type),
                'position': channel.position,
                'created_at': channel.created_at.isoformat()
            }
            
            if hasattr(channel, 'topic'):
                channel_data['topic'] = channel.topic
            if hasattr(channel, 'nsfw'):
                channel_data['nsfw'] = channel.nsfw
            if hasattr(channel, 'slowmode_delay'):
                channel_data['slowmode_delay'] = channel.slowmode_delay
                
            channels.append(channel_data)
        
        server_data['channels_detailed'] = channels
        
        # Get server configuration
        config = ServerConfig.query.filter_by(guild_id=guild_id).first()
        if config:
            server_data['config'] = config.to_dict()
        else:
            server_data['config'] = {
                'persona_mode': 'normal',
                'admin_users': [],
                'custom_settings': {},
                'is_locked': False
            }
        
        return jsonify(server_data)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get server: {str(e)}'}), 500

@servers_bp.route('/api/servers/<guild_id>/config', methods=['GET', 'PUT'])
@require_discord_auth
def server_config(guild_id):
    """Get or update server configuration"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not connected'}), 503
        
        guild = bot_instance.get_guild(int(guild_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        # Check admin permissions
        user_id = getattr(request, 'user_id', None)
        if user_id:
            member = guild.get_member(int(user_id))
            if not member or not member.guild_permissions.administrator:
                return jsonify({'error': 'Admin permissions required'}), 403
        
        if request.method == 'GET':
            config = ServerConfig.query.filter_by(guild_id=guild_id).first()
            if config:
                return jsonify(config.to_dict())
            else:
                # Return default configuration
                return jsonify({
                    'guild_id': guild_id,
                    'guild_name': guild.name,
                    'persona_mode': 'normal',
                    'admin_users': [],
                    'custom_settings': {},
                    'is_locked': False
                })
        
        elif request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            config = ServerConfig.query.filter_by(guild_id=guild_id).first()
            if not config:
                config = ServerConfig(
                    guild_id=guild_id,
                    guild_name=guild.name
                )
                db.session.add(config)
            
            # Update configuration
            if 'persona_mode' in data:
                config.persona_mode = data['persona_mode']
            if 'admin_users' in data:
                config.admin_users = json.dumps(data['admin_users'])
            if 'custom_settings' in data:
                config.custom_settings = json.dumps(data['custom_settings'])
            if 'is_locked' in data:
                config.is_locked = data['is_locked']
            
            config.updated_at = datetime.utcnow()
            config.guild_name = guild.name  # Update guild name
            
            db.session.commit()
            
            # Notify bot of configuration change via Redis
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'config_update',
                        'guild_id': guild_id,
                        'config': config.to_dict()
                    }))
                except Exception as e:
                    print(f"Failed to publish config update: {e}")
            
            return jsonify(config.to_dict())
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage server config: {str(e)}'}), 500

@servers_bp.route('/api/servers/<guild_id>/members', methods=['GET'])
@require_discord_auth
def get_server_members(guild_id):
    """Get server member list with stats"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not connected'}), 503
        
        guild = bot_instance.get_guild(int(guild_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        # Check if user has access
        user_id = getattr(request, 'user_id', None)
        if user_id:
            member = guild.get_member(int(user_id))
            if not member:
                return jsonify({'error': 'Access denied'}), 403
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        search = request.args.get('search', '').lower()
        
        members = []
        for member in guild.members:
            if search and search not in member.display_name.lower():
                continue
            
            member_data = {
                'id': str(member.id),
                'username': member.name,
                'display_name': member.display_name,
                'discriminator': member.discriminator,
                'avatar': str(member.avatar.url) if member.avatar else None,
                'bot': member.bot,
                'status': str(member.status),
                'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                'roles': [role.name for role in member.roles if role.name != '@everyone'],
                'top_role': member.top_role.name if member.top_role.name != '@everyone' else None,
                'permissions': {
                    'administrator': member.guild_permissions.administrator,
                    'manage_server': member.guild_permissions.manage_guild,
                    'manage_channels': member.guild_permissions.manage_channels,
                    'manage_messages': member.guild_permissions.manage_messages,
                    'kick_members': member.guild_permissions.kick_members,
                    'ban_members': member.guild_permissions.ban_members
                }
            }
            
            # Add user interaction data if available
            user_db = User.query.filter_by(discord_id=str(member.id)).first()
            if user_db:
                member_data['interaction_stats'] = {
                    'last_active': user_db.last_active.isoformat(),
                    'has_memory': bool(user_db.memory_data)
                }
            
            members.append(member_data)
        
        # Sort and paginate
        members.sort(key=lambda x: x['display_name'].lower())
        total = len(members)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_members = members[start:end]
        
        return jsonify({
            'members': paginated_members,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get server members: {str(e)}'}), 500

@servers_bp.route('/api/servers/<guild_id>/activity', methods=['GET'])
@require_discord_auth
def get_server_activity(guild_id):
    """Get server activity and engagement metrics"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not connected'}), 503
        
        guild = bot_instance.get_guild(int(guild_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        # Get time range
        days = request.args.get('days', 7, type=int)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        activity_data = {
            'time_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            },
            'message_activity': [],
            'user_activity': [],
            'channel_activity': [],
            'bot_interactions': {
                'total_commands': 0,
                'unique_users': 0,
                'popular_commands': []
            }
        }
        
        # Try to get cached activity data from Redis
        if redis_client:
            try:
                cache_key = f"server_activity:{guild_id}:{days}d"
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    cached = json.loads(cached_data)
                    # Check if cache is recent (within 1 hour)
                    cache_time = datetime.fromisoformat(cached['generated_at'])
                    if datetime.utcnow() - cache_time < timedelta(hours=1):
                        return jsonify(cached['data'])
            except Exception as e:
                print(f"Failed to get cached activity: {e}")
        
        # Generate activity data (this would normally come from message logs)
        # For now, return simulated data structure
        activity_data['message_activity'] = [
            {'date': (start_date + timedelta(days=i)).isoformat()[:10], 'count': 0}
            for i in range(days)
        ]
        
        # Cache the result
        if redis_client:
            try:
                cache_data = {
                    'data': activity_data,
                    'generated_at': datetime.utcnow().isoformat()
                }
                redis_client.setex(cache_key, 3600, json.dumps(cache_data))  # 1 hour cache
            except Exception as e:
                print(f"Failed to cache activity data: {e}")
        
        return jsonify(activity_data)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get server activity: {str(e)}'}), 500

@servers_bp.route('/api/servers/<guild_id>/channels/<channel_id>/lock', methods=['POST'])
@require_discord_auth
@require_admin
def lock_channel(guild_id, channel_id):
    """Lock or unlock a channel for bot interactions"""
    try:
        data = request.get_json()
        locked = data.get('locked', False)
        
        # Send command to bot via Redis
        if redis_client:
            command_data = {
                'type': 'lock_channel',
                'guild_id': guild_id,
                'channel_id': channel_id,
                'locked': locked
            }
            redis_client.publish('bot_commands', json.dumps(command_data))
        
        return jsonify({
            'success': True,
            'channel_id': channel_id,
            'locked': locked
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to lock/unlock channel: {str(e)}'}), 500
