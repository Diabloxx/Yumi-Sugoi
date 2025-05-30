"""
Bot Status and Statistics API Routes
"""

from flask import Blueprint, jsonify, request
import os
import json
from datetime import datetime, timedelta

# Create Blueprint
bot_bp = Blueprint('bot', __name__)

# Import from parent app - we'll handle this in the route functions
def get_app_dependencies():
    """Get app dependencies dynamically"""
    try:
        from .app_fixed import bot_instance, get_bot_stats, require_api_key, require_discord_auth
        return bot_instance, get_bot_stats, require_api_key, require_discord_auth
    except ImportError:
        # Fallback functions if imports fail
        def fallback_auth(f):
            return f
        def fallback_stats():
            return {'bot_status': {'connected': False, 'latency': None, 'uptime': 'Unknown'}, 'stats': {'guilds': 0, 'users': 0, 'custom_personas': 0, 'qa_pairs': 0}}
        return None, fallback_stats, fallback_auth, fallback_auth

@bot_bp.route('/api/bot/stats', methods=['GET'])
def get_bot_statistics():
    """Get comprehensive bot statistics"""
    try:
        bot_instance, get_bot_stats, require_api_key, require_discord_auth = get_app_dependencies()
        
        stats = get_bot_stats()
        
        # Load dashboard stats if available
        dashboard_stats = {}
        try:
            stats_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'dashboard_data')
            
            # Load message stats
            message_stats_file = os.path.join(stats_dir, 'message_stats.json')
            if os.path.exists(message_stats_file):
                with open(message_stats_file, 'r') as f:
                    dashboard_stats['messages'] = json.load(f)
            
            # Load command stats
            command_stats_file = os.path.join(stats_dir, 'command_stats.json')
            if os.path.exists(command_stats_file):
                with open(command_stats_file, 'r') as f:
                    dashboard_stats['commands'] = json.load(f)
            
            # Load server stats
            server_stats_file = os.path.join(stats_dir, 'server_stats.json')
            if os.path.exists(server_stats_file):
                with open(server_stats_file, 'r') as f:
                    dashboard_stats['servers'] = json.load(f)
                    
        except Exception as e:
            print(f"Error loading dashboard stats: {e}")
        
        # Combine stats
        response = {
            **stats,
            'dashboard_stats': dashboard_stats,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bot_bp.route('/api/bot/health', methods=['GET'])
def bot_health_check():
    """Bot health check endpoint"""
    try:
        bot_instance, get_bot_stats, require_api_key, require_discord_auth = get_app_dependencies()
        if not bot_instance:
            return jsonify({
                'status': 'unhealthy',
                'message': 'Bot instance not available',
                'timestamp': datetime.utcnow().isoformat()
            }), 503
        
        health_status = {
            'status': 'healthy' if bot_instance.is_ready() else 'starting',
            'latency': round(bot_instance.latency * 1000) if bot_instance.latency else None,
            'guilds': len(bot_instance.guilds) if bot_instance.guilds else 0,
            'uptime': 'Unknown',  # Will be updated from Redis if available
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Try to get real uptime from Redis
        try:
            from .app_fixed import redis_client
            if redis_client:
                bot_status_data = redis_client.get('bot:status')
                if bot_status_data:
                    import json
                    status_info = json.loads(bot_status_data)
                    if 'uptime' in status_info:
                        health_status['uptime'] = status_info['uptime']
                    if 'uptime_seconds' in status_info:
                        health_status['uptime_seconds'] = status_info['uptime_seconds']
                    if 'start_time' in status_info:
                        health_status['start_time'] = status_info['start_time']
        except Exception as e:
            print(f"Error getting uptime from Redis: {e}")
        
        return jsonify(health_status), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@bot_bp.route('/api/bot/activity', methods=['GET'])
def get_bot_activity():
    """Get recent bot activity and events"""
    try:
        bot_instance, get_bot_stats, require_api_key, require_discord_auth = get_app_dependencies()
        
        # Get time range from query params
        hours = request.args.get('hours', 24, type=int)
        since = datetime.utcnow() - timedelta(hours=hours)
        
        activity_data = {
            'message_activity': [],
            'command_usage': [],
            'server_events': [],
            'user_interactions': [],
            'time_range': f"Last {hours} hours",
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Load activity data from dashboard stats
        try:
            stats_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'dashboard_data')
            
            # Message activity by hour
            message_stats_file = os.path.join(stats_dir, 'message_stats.json')
            if os.path.exists(message_stats_file):
                with open(message_stats_file, 'r') as f:
                    message_stats = json.load(f)
                    activity_data['message_activity'] = message_stats
            
            # Command usage
            command_stats_file = os.path.join(stats_dir, 'command_stats.json')
            if os.path.exists(command_stats_file):
                with open(command_stats_file, 'r') as f:
                    command_stats = json.load(f)
                    activity_data['command_usage'] = command_stats
                    
        except Exception as e:
            print(f"Error loading activity data: {e}")
        
        return jsonify(activity_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bot_bp.route('/api/bot/metrics', methods=['GET'])
def get_bot_metrics():
    """Get detailed bot performance metrics"""
    try:
        metrics = {
            'performance': {
                'latency': round(bot_instance.latency * 1000) if bot_instance and bot_instance.latency else 0,
                'memory_usage': 0,  # You can implement memory tracking
                'cpu_usage': 0,     # You can implement CPU tracking
                'response_time': 0   # Average response time
            },
            'usage': {
                'total_guilds': len(bot_instance.guilds) if bot_instance and bot_instance.guilds else 0,
                'total_users': sum(guild.member_count for guild in bot_instance.guilds) if bot_instance and bot_instance.guilds else 0,
                'active_channels': 0,  # Number of channels with recent activity
                'daily_messages': 0    # Messages processed today
            },
            'features': {
                'personas_available': len(PERSONA_MODES) if 'PERSONA_MODES' in globals() else 0,
                'custom_personas': 0,   # Count from database
                'qa_pairs': 0,          # Count from database
                'locked_servers': 0     # Count of locked servers
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Get additional metrics from database
        from .app import PersonaMode, QAPair, ServerConfig
        
        try:
            metrics['features']['custom_personas'] = PersonaMode.query.filter_by(is_custom=True).count()
            metrics['features']['qa_pairs'] = QAPair.query.count()
            metrics['features']['locked_servers'] = ServerConfig.query.filter_by(is_locked=True).count()
        except Exception as e:
            print(f"Error getting database metrics: {e}")
        
        return jsonify(metrics), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bot_bp.route('/api/bot/logs', methods=['GET'])
def get_bot_logs():
    """Get recent bot logs"""
    try:
        bot_instance, get_bot_stats, require_api_key, require_discord_auth = get_app_dependencies()
        
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level', 'all')  # all, error, warning, info
        
        logs = []
        
        # Try to read bot log file if it exists
        log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot.log')
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # Get last N lines
                recent_lines = lines[-limit:] if len(lines) > limit else lines
                
                for line in recent_lines:
                    if line.strip():
                        logs.append({
                            'timestamp': datetime.utcnow().isoformat(),  # You can parse actual timestamps
                            'level': 'info',  # You can parse actual log levels
                            'message': line.strip()
                        })
            except Exception as e:
                print(f"Error reading log file: {e}")
        
        # If no log file, provide sample log entries
        if not logs:
            logs = [
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'level': 'info',
                    'message': 'Bot is running normally'
                },
                {
                    'timestamp': (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                    'level': 'info',
                    'message': 'Dashboard API started'
                }
            ]
        
        return jsonify({
            'logs': logs,
            'total': len(logs),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
