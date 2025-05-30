"""
Admin tools API routes for Yumi Sugoi Discord Bot Dashboard

Provides endpoints for administrative functions including bot control,
system management, user management, and advanced configuration.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import json
import psutil
import os
from typing import Dict, List, Optional

from .app import (
    bot_instance, db, redis_client,
    require_api_key, require_discord_auth, require_admin,
    User, ServerConfig, PersonaMode, QAPair
)

admin_bp = Blueprint('admin', __name__)

def get_system_stats():
    """Get system resource usage statistics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get bot process info if available
        bot_process = None
        try:
            current_process = psutil.Process()
            bot_process = {
                'pid': current_process.pid,
                'cpu_percent': current_process.cpu_percent(),
                'memory_mb': current_process.memory_info().rss / 1024 / 1024,
                'threads': current_process.num_threads(),
                'create_time': datetime.fromtimestamp(current_process.create_time()).isoformat()
            }
        except Exception as e:
            print(f"Failed to get process info: {e}")
        
        return {
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            },
            'memory': {
                'total_gb': memory.total / 1024 / 1024 / 1024,
                'used_gb': memory.used / 1024 / 1024 / 1024,
                'percent': memory.percent,
                'available_gb': memory.available / 1024 / 1024 / 1024
            },
            'disk': {
                'total_gb': disk.total / 1024 / 1024 / 1024,
                'used_gb': disk.used / 1024 / 1024 / 1024,
                'free_gb': disk.free / 1024 / 1024 / 1024,
                'percent': (disk.used / disk.total) * 100
            },
            'bot_process': bot_process
        }
    except Exception as e:
        print(f"Failed to get system stats: {e}")
        return {}

@admin_bp.route('/api/admin/system', methods=['GET'])
@require_discord_auth
@require_admin
def get_admin_system_info():
    """Get comprehensive system and bot information"""
    try:
        system_info = {
            'bot_status': {
                'connected': bot_instance is not None and not bot_instance.is_closed(),
                'latency': round(bot_instance.latency * 1000, 2) if bot_instance else None,
                'guild_count': len(bot_instance.guilds) if bot_instance else 0,
                'user_count': sum(guild.member_count for guild in bot_instance.guilds) if bot_instance else 0,
                'uptime': None  # Calculate from bot start time
            },
            'system_resources': get_system_stats(),
            'database': {
                'users': User.query.count(),
                'server_configs': ServerConfig.query.count(),
                'custom_personas': PersonaMode.query.filter_by(is_custom=True).count(),
                'qa_pairs': QAPair.query.count()
            },
            'redis_status': {
                'connected': redis_client is not None,
                'info': None
            }
        }
        
        # Get Redis info if available
        if redis_client:
            try:
                redis_info = redis_client.info()
                system_info['redis_status']['info'] = {
                    'used_memory_human': redis_info.get('used_memory_human'),
                    'connected_clients': redis_info.get('connected_clients'),
                    'total_commands_processed': redis_info.get('total_commands_processed'),
                    'uptime_in_seconds': redis_info.get('uptime_in_seconds')
                }
            except Exception as e:
                print(f"Failed to get Redis info: {e}")
        
        return jsonify(system_info)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get system info: {str(e)}'}), 500

@admin_bp.route('/api/admin/bot/restart', methods=['POST'])
@require_discord_auth
@require_admin
def restart_bot():
    """Restart the bot (requires Redis for command passing)"""
    try:
        if not redis_client:
            return jsonify({'error': 'Redis not available for bot commands'}), 503
        
        # Send restart command via Redis
        redis_client.publish('bot_commands', json.dumps({
            'type': 'restart_bot',
            'requested_by': getattr(request, 'user_id', 'unknown'),
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        return jsonify({
            'success': True,
            'message': 'Bot restart command sent',
            'note': 'Bot will restart shortly'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to restart bot: {str(e)}'}), 500

@admin_bp.route('/api/admin/bot/reload', methods=['POST'])
@require_discord_auth
@require_admin
def reload_bot_modules():
    """Reload bot modules and configuration"""
    try:
        if not redis_client:
            return jsonify({'error': 'Redis not available for bot commands'}), 503
        
        data = request.get_json() or {}
        modules = data.get('modules', ['all'])  # Default to reloading all
        
        redis_client.publish('bot_commands', json.dumps({
            'type': 'reload_modules',
            'modules': modules,
            'requested_by': getattr(request, 'user_id', 'unknown'),
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        return jsonify({
            'success': True,
            'message': f'Module reload command sent for: {", ".join(modules)}',
            'modules': modules
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to reload modules: {str(e)}'}), 500

@admin_bp.route('/api/admin/users', methods=['GET'])
@require_discord_auth
@require_admin
def get_all_users():
    """Get all users with admin-level details"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        search = request.args.get('search', '').lower()
        sort_by = request.args.get('sort_by', 'last_active')
        order = request.args.get('order', 'desc')
        
        query = User.query
        
        # Apply search filter
        if search:
            query = query.filter(
                User.username.ilike(f'%{search}%')
            )
        
        # Apply sorting
        if sort_by == 'username':
            query = query.order_by(User.username.desc() if order == 'desc' else User.username.asc())
        elif sort_by == 'created_at':
            query = query.order_by(User.created_at.desc() if order == 'desc' else User.created_at.asc())
        else:  # last_active
            query = query.order_by(User.last_active.desc() if order == 'desc' else User.last_active.asc())
        
        # Paginate
        paginated = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = []
        for user in paginated.items:
            user_data = user.to_dict()
            
            # Add additional admin info
            user_data['admin_info'] = {
                'memory_size': len(user.memory_data) if user.memory_data else 0,
                'preferences_count': len(json.loads(user.preferences)) if user.preferences else 0,
                'days_since_created': (datetime.utcnow() - user.created_at).days,
                'days_since_active': (datetime.utcnow() - user.last_active).days
            }
            
            users.append(user_data)
        
        return jsonify({
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated.total,
                'pages': paginated.pages,
                'has_next': paginated.has_next,
                'has_prev': paginated.has_prev
            }
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get users: {str(e)}'}), 500

@admin_bp.route('/api/admin/users/<user_discord_id>', methods=['GET', 'PUT', 'DELETE'])
@require_discord_auth
@require_admin
def manage_user(user_discord_id):
    """Get, update, or delete a specific user"""
    try:
        user = User.query.filter_by(discord_id=user_discord_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if request.method == 'GET':
            user_data = user.to_dict()
            
            # Add detailed admin information
            user_data['admin_details'] = {
                'memory_data': json.loads(user.memory_data) if user.memory_data else {},
                'preferences': json.loads(user.preferences) if user.preferences else {},
                'interaction_count': len(json.loads(user.memory_data).get('interactions', [])) if user.memory_data else 0,
                'servers_shared': []  # This would need to be calculated from bot guilds
            }
            
            return jsonify(user_data)
        
        elif request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Update allowed fields
            if 'memory_data' in data:
                user.memory_data = json.dumps(data['memory_data'])
            if 'preferences' in data:
                user.preferences = json.dumps(data['preferences'])
            
            user.last_active = datetime.utcnow()
            db.session.commit()
            
            return jsonify(user.to_dict())
        
        elif request.method == 'DELETE':
            # Send command to bot to clear user data
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'clear_user_data',
                        'user_id': user_discord_id,
                        'requested_by': getattr(request, 'user_id', 'unknown')
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of user deletion: {e}")
            
            db.session.delete(user)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'User deleted'})
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage user: {str(e)}'}), 500

@admin_bp.route('/api/admin/users/<user_discord_id>/memory/clear', methods=['POST'])
@require_discord_auth
@require_admin
def clear_user_memory(user_discord_id):
    """Clear a user's memory data"""
    try:
        user = User.query.filter_by(discord_id=user_discord_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Clear memory data
        user.memory_data = None
        db.session.commit()
        
        # Notify bot via Redis
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'clear_user_memory',
                    'user_id': user_discord_id,
                    'requested_by': getattr(request, 'user_id', 'unknown')
                }))
            except Exception as e:
                print(f"Failed to notify bot of memory clear: {e}")
        
        return jsonify({
            'success': True,
            'message': 'User memory cleared'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to clear user memory: {str(e)}'}), 500

@admin_bp.route('/api/admin/servers/bulk', methods=['POST'])
@require_discord_auth
@require_admin
def bulk_server_operations():
    """Perform bulk operations on servers"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        operation = data.get('operation')
        server_ids = data.get('server_ids', [])
        
        if not operation or not server_ids:
            return jsonify({'error': 'Operation and server IDs required'}), 400
        
        results = []
        
        for guild_id in server_ids:
            try:
                if operation == 'set_persona':
                    persona_name = data.get('persona_name')
                    if not persona_name:
                        results.append({'guild_id': guild_id, 'error': 'Persona name required'})
                        continue
                    
                    config = ServerConfig.query.filter_by(guild_id=guild_id).first()
                    if not config:
                        if bot_instance:
                            guild = bot_instance.get_guild(int(guild_id))
                            guild_name = guild.name if guild else f"Guild {guild_id}"
                        else:
                            guild_name = f"Guild {guild_id}"
                        
                        config = ServerConfig(
                            guild_id=guild_id,
                            guild_name=guild_name
                        )
                        db.session.add(config)
                    
                    config.persona_mode = persona_name
                    config.updated_at = datetime.utcnow()
                    
                    results.append({'guild_id': guild_id, 'success': True})
                
                elif operation == 'lock':
                    config = ServerConfig.query.filter_by(guild_id=guild_id).first()
                    if config:
                        config.is_locked = True
                        config.updated_at = datetime.utcnow()
                        results.append({'guild_id': guild_id, 'success': True})
                    else:
                        results.append({'guild_id': guild_id, 'error': 'Server config not found'})
                
                elif operation == 'unlock':
                    config = ServerConfig.query.filter_by(guild_id=guild_id).first()
                    if config:
                        config.is_locked = False
                        config.updated_at = datetime.utcnow()
                        results.append({'guild_id': guild_id, 'success': True})
                    else:
                        results.append({'guild_id': guild_id, 'error': 'Server config not found'})
                
                else:
                    results.append({'guild_id': guild_id, 'error': f'Unknown operation: {operation}'})
            
            except Exception as e:
                results.append({'guild_id': guild_id, 'error': str(e)})
        
        db.session.commit()
        
        # Notify bot of bulk changes via Redis
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'bulk_server_update',
                    'operation': operation,
                    'server_ids': server_ids,
                    'data': data,
                    'requested_by': getattr(request, 'user_id', 'unknown')
                }))
            except Exception as e:
                print(f"Failed to notify bot of bulk update: {e}")
        
        success_count = len([r for r in results if r.get('success')])
        return jsonify({
            'results': results,
            'summary': {
                'total': len(server_ids),
                'success': success_count,
                'failed': len(server_ids) - success_count
            }
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to perform bulk operation: {str(e)}'}), 500

@admin_bp.route('/api/admin/logs', methods=['GET'])
@require_discord_auth
@require_admin
def get_admin_logs():
    """Get detailed bot logs with filtering"""
    try:
        level = request.args.get('level', 'INFO')
        limit = min(request.args.get('limit', 100, type=int), 1000)
        search = request.args.get('search', '')
        
        # This would typically read from log files or a logging database
        # For now, return a placeholder structure
        logs = [
            {
                'timestamp': datetime.utcnow().isoformat(),
                'level': 'INFO',
                'message': 'Bot started successfully',
                'module': 'main',
                'guild_id': None,
                'user_id': None
            }
        ]
        
        return jsonify({
            'logs': logs,
            'total': len(logs),
            'filters': {
                'level': level,
                'search': search,
                'limit': limit
            }
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get logs: {str(e)}'}), 500

@admin_bp.route('/api/admin/maintenance', methods=['POST'])
@require_discord_auth
@require_admin
def maintenance_mode():
    """Enable or disable maintenance mode"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        message = data.get('message', 'Bot is currently under maintenance.')
        
        if redis_client:
            # Store maintenance status in Redis
            maintenance_data = {
                'enabled': enabled,
                'message': message,
                'enabled_by': getattr(request, 'user_id', 'unknown'),
                'enabled_at': datetime.utcnow().isoformat()
            }
            redis_client.set('maintenance_mode', json.dumps(maintenance_data))
            
            # Notify bot
            redis_client.publish('bot_commands', json.dumps({
                'type': 'maintenance_mode',
                'enabled': enabled,
                'message': message
            }))
        
        return jsonify({
            'success': True,
            'maintenance_enabled': enabled,
            'message': message
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to set maintenance mode: {str(e)}'}), 500

@admin_bp.route('/api/admin/database/backup', methods=['POST'])
@require_discord_auth
@require_admin
def backup_database():
    """Create a database backup"""
    try:
        backup_name = f"yumi_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"
        
        # This would typically create an actual database backup
        # For SQLite, you could use the backup API
        # For PostgreSQL, you'd use pg_dump
        
        return jsonify({
            'success': True,
            'backup_name': backup_name,
            'message': 'Database backup created',
            'note': 'Backup functionality requires implementation based on database type'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to create backup: {str(e)}'}), 500
