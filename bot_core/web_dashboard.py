import threading
from flask import Flask, jsonify, render_template, request, send_from_directory
import os
import json
import time
import psutil
import random
from datetime import datetime
from collections import defaultdict
from flask_socketio import SocketIO, emit

# --- Constants and File Paths ---
DASHBOARD_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'dashboard_data')
MESSAGE_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'message_stats.json')
COMMAND_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'command_stats.json')
SERVER_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'server_stats.json')
CHANNEL_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'channel_stats.json')
USER_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'user_stats.json')

# --- Helper Functions ---
def load_json_file(path, default=None):
    """Load JSON data from a file"""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
    return default if default is not None else {}

def save_json_file(path, data):
    """Save JSON data to a file"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {path}: {e}")

start_time = datetime.now()

def get_uptime():
    """Calculate bot uptime"""
    now = datetime.now()
    delta = now - start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def broadcast_analytics_update_periodic(socketio, app):
    """Periodically broadcast analytics updates"""
    while True:
        try:
            bot = app.config.get('bot')
            if bot:
                socketio.emit('analytics_update', {
                    'server_count': len(bot.guilds),
                    'total_users': sum(g.member_count for g in bot.guilds),
                    'uptime': get_uptime(),
                    'status': 'online'
                })
        except Exception as e:
            print(f"Error in periodic analytics broadcast: {e}")
        time.sleep(30)  # Update every 30 seconds

def create_dashboard_app(PERSONA_MODES=None, custom_personas=None, get_level=None, get_xp=None):
    """Create and configure the Flask dashboard application"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    # Create Flask app
    app = Flask('yumi_dashboard', 
               static_folder=static_dir,
               template_folder=template_dir)
      # Configure Socket.IO with CORS allowed
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        logger=True,
        engineio_logger=True,
        path='/socket.io'  # Match client's expected path
    )
      # Store provided data in app config
    app.config.update({
        'PERSONA_MODES': PERSONA_MODES or [],
        'custom_personas': custom_personas or {},
        'get_level': get_level or (lambda x: 1),
        'get_xp': get_xp or (lambda x: 0),
        'bot': None,  # Will be set later
        'socketio': socketio  # Store socketio instance
    })

    def set_bot(bot_instance):
        """Set the bot instance for the dashboard"""
        app.config['bot'] = bot_instance
    
    app.set_bot = set_bot  # Add setter method to app

    # --- Socket.IO Event Handlers ---    @socketio.on('connect')
    def handle_connect(auth):
        print('[Socket.IO] Client connected')
        emit('connected', {'status': 'connected'})
        try:
            bot = app.config.get('bot')
            if bot:
                emit('analytics_update', {
                    'server_count': len(bot.guilds),
                    'total_users': sum(g.member_count for g in bot.guilds),
                    'uptime': get_uptime(),
                    'status': 'online'
                })
        except Exception as e:
            print(f"Error sending initial analytics: {e}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print('[Socket.IO] Client disconnected')
        emit('disconnect', {'status': 'disconnected'}, broadcast=True)

    @socketio.on('error')
    def handle_error(error):
        print(f'[Socket.IO] Error: {error}')
        emit('error', {'error': str(error)}, broadcast=True)    @socketio.on('request_update')
    def handle_update_request():
        """Handle real-time update requests"""
        try:
            bot = app.config.get('bot')
            if not bot:
                emit('error', {'message': 'Bot not initialized'})
                return

            # Get analytics data
            emit('analytics_update', {
                'server_count': len(bot.guilds),
                'total_users': sum(g.member_count for g in bot.guilds),
                'uptime': get_uptime(),
                'status': 'online'
            })

        except Exception as e:
            print(f"Error sending update: {e}")
            emit('error', {'message': str(e)})

        try:
            # Get server stats
            servers = []
            for guild in bot.guilds:
                servers.append({
                    'id': str(guild.id),
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon_url': str(guild.icon.url) if guild.icon else '/static/img/default_server.png'
                })

            # Get analytics
            stats = {
                'uptime': get_uptime(),
                'servers': len(servers),
                'total_members': sum(s['member_count'] for s in servers),
                'commands_today': len(command_stats),
                'messages_today': sum(v for k, v in message_stats.items() if k.startswith('hour_'))
            }

            emit('stats_update', {
                'servers': servers,
                'stats': stats
            })

        except Exception as e:
            print(f'[Socket.IO] Error sending update: {e}')
            emit('error', {'message': str(e)})

    # --- Persona Management ---
    @app.route('/api/personas')
    def api_personas():
        # Convert the persona modes and custom personas into a consistent format
        all_personas = []
        
        # Add default personas
        for persona in app.config['PERSONA_MODES']:
            all_personas.append({
                'id': persona.lower(),
                'name': persona,
                'description': f'Default {persona} personality mode',
                'type': 'default',
                'messages_sent': 0  # This would need to be tracked in a real implementation
            })
          # Add custom personas
        for name, info in app.config['custom_personas'].items():
            all_personas.append({
                'id': name.lower(),
                'name': name,
                'description': info.get('description', 'Custom persona'),
                'type': 'custom',
                'creator': info.get('creator', 'unknown'),
                'messages_sent': 0  # This would need to be tracked in a real implementation
            })
        
        # Sort personas by type (default first) and then by name
        all_personas.sort(key=lambda x: (x['type'] != 'default', x['name']))
        
        return jsonify({'personas': all_personas})

    @app.route('/api/persona', methods=['POST'])
    def api_add_persona():
        from .main import custom_personas, save_json_file, CUSTOM_PERSONAS_FILE
        data = request.json
        name = data.get('name', '').strip().lower()
        if not name:
            return jsonify({'error': 'No name'}), 400
        if name in custom_personas:
            return jsonify({'error': 'Persona exists'}), 400
        custom_personas[name] = {'creator': 'dashboard', 'description': ''}
        save_json_file(CUSTOM_PERSONAS_FILE, custom_personas)        
        return jsonify({'success': True})

    @app.route('/api/persona/<name>', methods=['DELETE'])
    def api_delete_persona(name):
        from .main import custom_personas, save_json_file, CUSTOM_PERSONAS_FILE
        if name in custom_personas:
            del custom_personas[name]
            save_json_file(CUSTOM_PERSONAS_FILE, custom_personas)
            return jsonify({'success': True})
        return jsonify({'error': 'Not found'}), 404

    # --- Server and Channel Info (merged) ---
    @app.route('/api/servers')
    def api_servers():
        """Get list of servers the bot is in"""
        bot = app.config.get('bot')
        if not bot:
            return jsonify({'error': 'Bot not initialized'}), 503
            
        try:
            servers = []            
            for guild in bot.guilds:
                servers.append({
                    'id': str(guild.id),
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon': str(guild.icon.url) if guild.icon else '/static/img/default_server.svg',
                    'channels': [{'id': str(c.id), 'name': c.name} for c in guild.text_channels]
                })
            return jsonify({'servers': servers})
        except Exception as e:
            print(f"Error getting server list: {e}")
            return jsonify({'error': str(e)}), 500

    # --- Server Settings ---
    @app.route('/api/server/<int:server_id>/settings', methods=['GET', 'POST'])
    def api_server_settings(server_id):
        from .main import CONTEXT_MODES, LOCKED_CHANNELS, PERSONA_MODES, custom_personas, save_lockdown_channels
        OFFICIAL_SERVER_ID = 1375103404493373510
        if server_id != OFFICIAL_SERVER_ID:
            return jsonify({'error': 'Not allowed'}), 403
        all_modes = list(PERSONA_MODES) + list(custom_personas.keys())
        if request.method == 'GET':
            settings = {
                'mode': CONTEXT_MODES.get(f"guild_{server_id}", 'normal'),
                'locked_channels': list(LOCKED_CHANNELS.get(server_id, [])),
                'lockdown': bool(LOCKED_CHANNELS.get(server_id)),
                'all_modes': all_modes
            }
            return jsonify(settings)
        elif request.method == 'POST':
            data = request.json
            if 'mode' in data:
                CONTEXT_MODES[f"guild_{server_id}"] = data['mode']
            if 'locked_channels' in data:
                LOCKED_CHANNELS[server_id] = set(data['locked_channels'])
            if 'lockdown' in data:
                if data['lockdown'] and not LOCKED_CHANNELS.get(server_id):
                    LOCKED_CHANNELS[server_id] = set()
                if not data['lockdown']:
                    LOCKED_CHANNELS[server_id] = set()
            import json
            MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'yumi_modes.json')
            with open(MODE_FILE, 'w', encoding='utf-8') as f:
                json.dump(CONTEXT_MODES, f, ensure_ascii=False, indent=2)
            save_lockdown_channels()
            return jsonify({'success': True})

    # --- User Management (grouped) ---
    @app.route('/api/users/search')
    def api_user_search():
        """Search for users across all servers"""
        bot = app.config.get('bot')
        if not bot:
            return jsonify({'error': 'Bot not initialized'}), 503
            
        try:
            q = request.args.get('q', '').lower()
            users = []
            for guild in bot.guilds:
                for member in guild.members:
                    if q in member.name.lower() or q in str(member.id):
                        users.append({
                            'id': member.id,
                            'name': member.name,
                            'guild': guild.name,
                            'avatar_url': str(member.avatar.url) if member.avatar else None
                        })
            return jsonify(users)
        except Exception as e:
            print(f"Error in user search: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/user/<int:user_id>')
    def api_user_info(user_id):
        """Get detailed information about a user"""
        bot = app.config.get('bot')
        if not bot:
            return jsonify({'error': 'Bot not initialized'}), 503
            
        try:
            # Load user stats
            user_stats = load_json_file(USER_STATS_FILE, {}).get(str(user_id), {})
            
            # Find user in any guild
            user = None
            guild_data = None
            for guild in bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    user = member
                    guild_data = {
                        'id': guild.id,
                        'name': guild.name,
                        'joined_at': str(member.joined_at) if member.joined_at else None
                    }
                    break
                    
            if not user:
                return jsonify({'error': 'User not found'}), 404
                
            # Compile user info
            info = {
                'id': user.id,
                'name': user.name,
                'discriminator': user.discriminator if hasattr(user, 'discriminator') else None,
                'avatar_url': str(user.avatar.url) if user.avatar else None,
                'bot': user.bot,
                'created_at': str(user.created_at),
                'guild': guild_data,
                'stats': {
                    'messages': user_stats.get('messages', 0),
                    'commands': user_stats.get('commands', 0),
                    'last_active': user_stats.get('last_active')
                }
            }
            
            return jsonify(info)
        except Exception as e:
            print(f"Error getting user info: {e}")
            return jsonify({'error': str(e)}), 500

    # --- User Profile Management ---
    @app.route('/api/user/<user_id>')
    def api_get_user(user_id):
        """Get user profile data"""
        try:
            from .main import bot, user_xp, user_facts
            
            # Try to find the user
            user = None
            for guild in bot.guilds:
                member = guild.get_member(int(user_id))
                if member:
                    user = member
                    break
            
            if not user:
                # Try to fetch user info even if not in a guild
                try:
                    user = bot.get_user(int(user_id))
                except:
                    pass
            
            if not user:
                return jsonify({
                    'error': 'User not found'
                }), 404
            
            # Get user XP and level
            xp = user_xp.get(str(user_id), 0)
            level = get_level(xp)
            
            # Get user facts
            facts = user_facts.get(str(user_id), [])
            
            # Format joined_at date if available
            joined_at = "Unknown"
            if hasattr(user, 'joined_at') and user.joined_at:
                joined_at = user.joined_at.strftime('%Y-%m-%d %H:%M:%S')
            
            # Get user infractions (if available)
            infractions = []
            # This is a placeholder - implement actual infractions if available
            
            return jsonify({
                'id': str(user_id),
                'name': user.display_name if hasattr(user, 'display_name') else user.name,
                'username': user.name,
                'discriminator': user.discriminator if hasattr(user, 'discriminator') else '',
                'avatar_url': str(user.avatar.url) if user.avatar else '',
                'level': level,
                'xp': xp,
                'facts': facts,
                'joined_at': joined_at,
                'infractions': infractions,
                'roles': [str(role.id) for role in user.roles] if hasattr(user, 'roles') else []
            })
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return jsonify({
                'error': str(e)
            }), 500

    @app.route('/api/user/<user_id>', methods=['PUT', 'POST'])
    def api_update_user(user_id):
        """Update user profile data"""
        try:
            from .main import user_xp, user_facts, save_json_file, USER_XP_FILE, USER_FACTS_FILE
            
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Update user XP if provided
            if 'xp' in data:
                try:
                    xp = int(data['xp'])
                    user_xp[str(user_id)] = xp
                    save_json_file(USER_XP_FILE, user_xp)
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid XP value'}), 400
            
            # Update user facts if provided
            if 'facts' in data:
                if isinstance(data['facts'], list):
                    user_facts[str(user_id)] = data['facts']
                    save_json_file(USER_FACTS_FILE, user_facts)
                else:
                    return jsonify({'success': False, 'error': 'Facts must be a list'}), 400
            
            return jsonify({'success': True})
        except Exception as e:
            print(f"Error updating user profile: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # --- Scheduled Tasks ---
    @app.route('/api/scheduled/tasks', methods=['GET'])
    def api_scheduled_tasks():
        from .main import scheduled_announcements
        from datetime import datetime, timedelta
        
        # Use scheduled announcements or provide sample data
        tasks = []
        
        try:
            # Convert scheduled announcements to task format
            for idx, announcement in enumerate(scheduled_announcements):
                next_run = datetime.fromisoformat(announcement.get('next_run', datetime.now().isoformat()))
                tasks.append({
                    'id': str(idx + 1),
                    'name': announcement.get('name', 'Scheduled Announcement'),
                    'description': announcement.get('message', 'No description provided'),
                    'next_run': next_run.isoformat(),
                    'type': 'announcement',
                    'channel_id': announcement.get('channel_id')
                })
        except Exception:
            # Provide sample tasks if there's an error or no announcements
            now = datetime.now()
            tasks = [
                {
                    'id': '1',
                    'name': 'Daily Server Backup',
                    'description': 'Automated backup of server data and configurations',
                    'next_run': (now + timedelta(hours=12)).isoformat(),
                    'type': 'system'
                },
                {
                    'id': '2',
                    'name': 'Weekly Stats Report',
                    'description': 'Generate and post weekly engagement statistics',
                    'next_run': (now + timedelta(days=3)).isoformat(),
                    'type': 'report'
                },
                {
                    'id': '3',
                    'name': 'Server Event Reminder',
                    'description': 'Reminder for upcoming community game night',
                    'next_run': (now + timedelta(days=1, hours=6)).isoformat(),
                    'type': 'announcement'
                }
            ]
        
        return jsonify({'tasks': tasks})

    @app.route('/api/scheduled/<int:index>', methods=['DELETE', 'PUT'])
    def api_scheduled_edit(index):
        from .main import scheduled_announcements, save_json_file, SCHEDULED_ANNOUNCEMENTS_FILE
        if request.method == 'DELETE':
            if 0 <= index < len(scheduled_announcements):
                scheduled_announcements.pop(index)
                save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
                return jsonify({'success': True})
            return jsonify({'error': 'Not found'}), 404
        elif request.method == 'PUT':
            data = request.json
            if 0 <= index < len(scheduled_announcements):
                scheduled_announcements[index] = data
                save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
                return jsonify({'success': True})
            return jsonify({'error': 'Not found'}), 404

    # --- Moderation, Analytics, Audit Log, Chat Logs ---
    @app.route('/api/moderation/logs')
    def api_moderation_logs():
        import json
        from datetime import datetime, timedelta
        logs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'moderation_logs.json')
        try:
            with open(logs_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except Exception:
            # Provide sample moderation logs if file doesn't exist
            now = datetime.now()
            logs = [
                {
                    'timestamp': (now - timedelta(hours=2)).isoformat(),
                    'action': 'warn',
                    'user_name': 'ExampleUser1',
                    'user_id': '123456789',
                    'user_avatar': None,
                    'mod_name': 'Moderator1',
                    'mod_id': '987654321',
                    'mod_avatar': None,
                    'reason': 'First warning for spamming'
                },
                {
                    'timestamp': (now - timedelta(days=1)).isoformat(),
                    'action': 'mute',
                    'user_name': 'ExampleUser2',
                    'user_id': '234567890',
                    'user_avatar': None,
                    'mod_name': 'Moderator2',
                    'mod_id': '876543210',
                    'mod_avatar': None,
                    'reason': 'Repeated inappropriate behavior'
                },
                {
                    'timestamp': (now - timedelta(days=2)).isoformat(),
                    'action': 'ban',
                    'user_name': 'ExampleUser3',
                    'user_id': '345678901',
                    'user_avatar': None,
                    'mod_name': 'Moderator1',
                    'mod_id': '987654321',
                    'mod_avatar': None,
                    'reason': 'Severe violation of server rules'
                }
            ]
        
        # If logs is a dict, convert to list
        if isinstance(logs, dict):
            logs = list(logs.values())
        
        # Sort logs by timestamp, newest first
        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({'logs': logs})
        
    # --- Analytics and Dashboard Data ---    
    @app.route('/api/analytics')
    def api_analytics():
        """Main analytics endpoint"""
        try:
            bot = app.config.get('bot')
            if not bot:
                return jsonify({
                    'server_count': 0,
                    'total_users': 0,
                    'message_count': 0,
                    'persona_count': 0,
                    'uptime': get_uptime(),
                    'status': 'unavailable',
                    'message': 'Bot instance is not available'
                }), 503

            # Get message stats from file or memory
            try:
                with open(MESSAGE_STATS_FILE, 'r', encoding='utf-8') as f:
                    message_stats = json.load(f)
                total_messages = sum(int(message_stats.get(k, 0)) for k in message_stats if k.startswith('hour_'))
            except (FileNotFoundError, json.JSONDecodeError):
                total_messages = 0

            # Get persona count (both built-in and custom)
            persona_modes = app.config.get('PERSONA_MODES', [])
            custom_personas = app.config.get('custom_personas', {})
            total_personas = len(persona_modes or []) + len(custom_personas or {})

            analytics_data = {
                'server_count': len(bot.guilds) if hasattr(bot, 'guilds') else 0,
                'total_users': sum(g.member_count for g in bot.guilds) if hasattr(bot, 'guilds') else 0,
                'message_count': total_messages or 0,
                'persona_count': total_personas or 0,
                'uptime': get_uptime(),
                'status': 'online'
            }
            
            return jsonify(analytics_data)
        except Exception as e:
            print(f"Error in analytics endpoint: {e}")
            return jsonify({
                'server_count': 0,
                'total_users': 0,
                'message_count': 0,
                'persona_count': 0,
                'uptime': '0:00:00',
                'status': 'error',
                'error': str(e)
            }), 500

    @app.route('/api/analytics/activity/<period>')
    def api_activity(period):
        """Get activity data for a specific period"""
        from .main import message_count
        
        if period == 'day':
            # Get hourly data
            data = {
                'labels': [f"{h:02d}:00" for h in range(24)],
                'values': [message_count.get(f"hour_{h}", 0) for h in range(24)]
            }
        elif period == 'week':
            # Get daily data
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            data = {
                'labels': days,
                'values': [message_count.get(f"day_{i}", 0) for i in range(7)]
            }
        else:
            return jsonify({'error': 'Invalid period'}), 400
            
        return jsonify(data)

    @app.route('/api/analytics/stats')
    def api_analytics_stats():
        """Get detailed statistics for the analytics tab"""
        from .main import message_count, command_usage
        
        # Get command usage stats
        commands = sorted(command_usage.items(), key=lambda x: x[1], reverse=True)[:10]
        command_labels = [cmd for cmd, _ in commands]
        command_values = [val for _, val in commands]
        
        # Get message volume by hour
        message_labels = [f"{h:02d}:00" for h in range(24)]
        message_values = [message_count.get(f"hour_{h}", 0) for h in range(24)]
        
        return jsonify({
            'command_usage': {
                'labels': command_labels,
                'values': command_values
            },
            'message_volume': {
                'labels': message_labels,
                'values': message_values
            }
        })
    @app.route('/api/analytics/server-activity')
    def api_server_activity():
        """Get server activity data"""
        try:
            # Load stats from files
            message_stats = load_json_file(MESSAGE_STATS_FILE, {})
            command_stats = load_json_file(COMMAND_STATS_FILE, {})
            server_stats = load_json_file(SERVER_STATS_FILE, {})

            # Get hourly activity for last 24 hours
            hours = [f"{h:02d}:00" for h in range(24)]
            hourly_messages = [message_stats.get(f"hour_{h}", 0) for h in range(24)]
            hourly_commands = [command_stats.get(f"hour_{h}", 0) for h in range(24)]

            return jsonify({
                'hourly': {
                    'labels': hours,
                    'messages': hourly_messages,
                    'commands': hourly_commands
                },
                'servers': server_stats
            })
        except Exception as e:
            print(f"Error in server activity endpoint: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analytics/message-volume')
    def api_message_volume():
        """Get message volume statistics"""
        try:
            # Load message stats from file
            message_stats = load_json_file(MESSAGE_STATS_FILE, {})
            
            # Get daily totals for the last 7 days
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            daily_messages = [message_stats.get(f"day_{i}", 0) for i in range(7)]
            
            # Get total messages
            total_messages = sum(v for k, v in message_stats.items() if k.startswith('day_'))
            
            return jsonify({
                'daily': {
                    'labels': days,
                    'values': daily_messages
                },
                'total': total_messages
            })
        except Exception as e:
            print(f"Error in message volume endpoint: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analytics/command-usage')
    def api_command_usage():
        """Get command usage statistics"""
        try:
            # Load command stats from file
            command_stats = load_json_file(COMMAND_STATS_FILE, {})
            
            # Get the top 10 most used commands
            commands = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Split into labels and values for the chart
            labels = [cmd for cmd, _ in commands]
            values = [count for _, count in commands]
            
            return jsonify({
                'labels': labels,
                'values': values,
                'total': sum(command_stats.values())
            })
        except Exception as e:
            print(f"Error in command usage endpoint: {e}")
            return jsonify({'error': str(e)}), 500

    # --- Users API ---
    @app.route('/api/users')
    def api_users():
        """Get list of users from file"""
        stats = load_json_file(USER_STATS_FILE, {})
        try:
            users = []
            for user_id, data in stats.items():
                users.append({
                    'id': user_id,
                    'name': user_id,  # Optionally, resolve to username if available
                    'avatar': '/static/img/default_avatar.png',
                    'messages_sent': data.get('messages', 0),
                    'commands_used': data.get('commands', 0)
                })
            return jsonify({'users': sorted(users, key=lambda x: x['id'])})
        except Exception as e:
            print(f"Error getting users: {e}")
            return jsonify({'users': []})

    # --- Active Channels API ---
    @app.route('/api/channels/active')
    def api_active_channels():
        """Get list of active channels from file"""
        stats = load_json_file(CHANNEL_STATS_FILE, {})
        try:
            channels = []
            for channel_id, data in stats.items():
                channels.append({
                    'id': channel_id,
                    'name': data.get('name', f"Channel {channel_id}"),
                    'server': data.get('server', ''),
                    'active_users': len(data.get('active_users', [])),
                    'last_message': data.get('last_message', None)
                })
            return jsonify({'channels': channels})
        except Exception as e:
            print(f"Error getting active channels: {e}")
            return jsonify({'channels': []})

    # --- Tasks API ---
    @app.route('/api/tasks')
    def api_tasks():
        """Get scheduled tasks"""
        try:
            tasks_data = get_tasks_data() if 'get_tasks_data' in globals() else []
            if not tasks_data:
                # Return mock data for testing
                tasks_data = [
                    {
                        'id': '1',
                        'name': 'Daily Backup',
                        'description': 'Backup bot data daily',
                        'status': 'active',
                        'schedule': '0 0 * * *'
                    }
                ]
            return jsonify({'tasks': tasks_data})
        except Exception as e:
            print(f"Error getting tasks: {e}")
            return jsonify({'tasks': []})

    @app.route('/api/settings')
    def api_settings():
        """Get bot settings"""
        try:
            # In a real implementation, you would get this from your config/database
            return jsonify({
                'prefix': '!',
                'default_persona': 'friendly',
                'auto_responses': True,
                'debug_mode': False
            })
        except Exception as e:
            print(f"Error getting settings: {e}")
            return jsonify({'error': str(e)}), 500    # --- WebSocket Support ---
    # Socket.IO is already initialized at the start of the function

    def broadcast_analytics_update(socketio, app):
        """Broadcast analytics update to all connected clients"""
        try:
            bot = app.config.get('bot')
            if not bot:
                return
                
            analytics_data = {
                'server_count': len(bot.guilds),
                'total_users': sum(g.member_count for g in bot.guilds),
                'uptime': get_uptime(),
                'tasks': [],  # Will be populated if get_tasks_data is available
                'status': 'online'
            }
            
            # Add tasks data if the function is available
            if 'get_tasks_data' in globals():
                analytics_data['tasks'] = get_tasks_data()
                
            socketio.emit('analytics_update', analytics_data)
        except Exception as e:
            print(f"Error broadcasting analytics update: {e}")    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print("[Socket.IO] Client connected")
        try:
            bot = app.config.get('bot')
            if bot:
                emit('analytics_update', {
                    'server_count': len(bot.guilds),
                    'total_users': sum(g.member_count for g in bot.guilds),
                    'uptime': get_uptime(),
                    'status': 'online'
                })
        except Exception as e:
            print(f"[Socket.IO] Error sending initial analytics: {e}")

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print("Client disconnected")

    @app.route('/')
    def dashboard():
        """Serve the main dashboard page"""
        return render_template('dashboard.html')

    @app.route('/debug/status')
    def debug_status():
        """Debug endpoint to check system status"""
        bot = get_bot()
        return jsonify({
            'bot_ready': bool(bot),
            'guild_count': len(bot.guilds) if bot else 0,
            'endpoints': [str(rule) for rule in app.url_map.iter_rules()],
            'config': {
                'persona_modes': len(app.config['PERSONA_MODES']),
                'custom_personas': len(app.config['custom_personas'])
            }
        })

    return app

# Initialize stats dictionaries
message_stats = {}
command_stats = {}
server_stats = {}
channel_stats = {}
user_stats = {}

def load_dashboard_stats():
    """Load statistics from saved files"""
    global message_stats, command_stats, server_stats, channel_stats, user_stats
    
    try:
        if os.path.exists(MESSAGE_STATS_FILE):
            message_stats.update(load_json_file(MESSAGE_STATS_FILE))
        if os.path.exists(COMMAND_STATS_FILE):
            command_stats.update(load_json_file(COMMAND_STATS_FILE))
        if os.path.exists(SERVER_STATS_FILE):
            server_stats.update(load_json_file(SERVER_STATS_FILE))
        if os.path.exists(CHANNEL_STATS_FILE):
            channel_stats.update(load_json_file(CHANNEL_STATS_FILE))
        if os.path.exists(USER_STATS_FILE):
            user_stats.update(load_json_file(USER_STATS_FILE))
        print("[Stats] Successfully loaded dashboard statistics")
    except Exception as e:
        print(f"[Stats] Error loading statistics: {e}")
        # Initialize empty stats if loading fails
        message_stats.clear()
        command_stats.clear()
        server_stats.clear()
        channel_stats.clear()
        user_stats.clear()

# Call load_dashboard_stats when the module is imported
load_dashboard_stats()

# --- Threaded runner ---
def run_dashboard(PERSONA_MODES, custom_personas, get_level, get_xp):
    app = create_dashboard_app(PERSONA_MODES, custom_personas, get_level, get_xp)
    socketio = app.config['socketio']
    
    # Start the analytics broadcast thread
    broadcast_thread = threading.Thread(
        target=broadcast_analytics_update_periodic,
        args=(socketio, app),
        daemon=True
    )
    broadcast_thread.start()
    
    # Run the Socket.IO server
    socketio.run(app, host='0.0.0.0', port=5005, allow_unsafe_werkzeug=True)

def start_dashboard_thread(PERSONA_MODES, custom_personas, get_level, get_xp):
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        args=(PERSONA_MODES, custom_personas, get_level, get_xp),
        daemon=True
    )
    dashboard_thread.start()

class MockBot:
    """Mock bot class for testing when no bot instance is available"""
    def __init__(self):
        self.latency = 0.1
        self.guilds = [
            MockGuild(id=1, name="Test Server 1", member_count=100),
            MockGuild(id=2, name="Test Server 2", member_count=50)
        ]

class MockGuild:
    """Mock guild class for testing"""
    def __init__(self, id, name, member_count):
        self.id = id
        self.name = name
        self.member_count = member_count
        self.text_channels = [
            MockChannel(id=1, name="general", guild=self),
            MockChannel(id=2, name="chat", guild=self)
        ]
        self.members = [MockMember(id=i, name=f"User{i}", guild=self) for i in range(member_count)]

class MockChannel:
    """Mock channel class for testing"""
    def __init__(self, id, name, guild):
        self.id = id
        self.name = name
        self.guild = guild
        self.members = guild.members
        self.type = "text"

class MockMember:
    """Mock member class for testing"""
    def __init__(self, id, name, guild):
        self.id = id
        self.name = name
        self.guild = guild
        self.display_name = name
        self.bot = False
        self.discriminator = "0001"
        self.avatar = None

def get_bot():
    """Helper function to get the bot instance or return None"""
    if not hasattr(app, 'config'):
        return None
    return app.config.get('bot')

def get_tasks_data():
    """Get scheduled tasks data"""
    try:
        bot = get_bot()
        tasks = []
        # Add scheduled tasks if any exist
        if hasattr(bot, 'scheduled_tasks'):
            for task in bot.scheduled_tasks:
                tasks.append({
                    'name': task.get('name', 'Unknown Task'),
                    'next_run': task.get('next_run', 'Not scheduled'),
                    'interval': task.get('interval', 'Unknown')
                })
        return tasks
    except Exception as e:
        print(f"Error getting tasks data: {e}")
        return []

# --- WebSocket server run ---
if __name__ == '__main__':
    app = create_dashboard_app()
    socketio = app.config['socketio']
    socketio.run(app, debug=True)
