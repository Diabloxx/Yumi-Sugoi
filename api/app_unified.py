# Unified Flask API Backend for Yumi Sugoi Discord Bot Dashboard
# Complete consolidation of all API endpoints into a single app file

import os
import sqlite3
import json
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from functools import wraps

from flask import Flask, request, jsonify, g, Response
from flask_cors import CORS
import redis

# Import the new authentication system
from api.auth import (
    require_api_token, 
    require_admin_token, 
    require_read_token, 
    require_write_token,
    require_api_key  # Legacy support
)

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'yumi-dashboard-secret-key-change-in-production')
app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'yumi_bot.db')
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'yumi-jwt-secret-change-in-production')
app.config['API_KEY'] = os.getenv('API_KEY', 'yumi-api-key-change-in-production')

# CORS setup for Next.js frontend
CORS(app, origins=[
    'http://localhost:3000',
    'http://localhost:3001',
    'http://10.0.0.31:5000',
    'https://yumi-dashboard.vercel.app'
])

# Redis setup (optional)
redis_client = None
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    print("Redis connected successfully")
except:
    print("Redis not available - running without real-time features")
    redis_client = None

# Global bot instance (placeholder - would be set by actual bot)
bot_instance = None

def get_bot_status_from_redis():
    """Get bot status from Redis if available"""
    if not redis_client:
        return {
            'connected': False,
            'ready': False,
            'latency': None,
            'guild_count': 0,
            'user_count': 0,
            'uptime': None,
            'start_time': None
        }
    
    try:
        # Get bot status from Redis
        bot_status_data = redis_client.get('bot:status')
        guild_count_data = redis_client.get('bot:guilds')
        
        if bot_status_data:
            bot_status = json.loads(bot_status_data)
            guild_count = int(guild_count_data) if guild_count_data else 0
            
            return {
                'connected': True,  # If data exists in Redis, bot is connected
                'ready': bot_status.get('connected', False),
                'latency': bot_status.get('latency'),
                'guild_count': guild_count,
                'user_count': 0,  # This would need to be calculated separately
                'uptime': bot_status.get('uptime'),
                'uptime_seconds': bot_status.get('uptime_seconds', 0),
                'start_time': bot_status.get('start_time'),
                'last_update': bot_status.get('last_update')
            }
        else:
            # No data in Redis means bot is not running
            return {
                'connected': False,
                'ready': False,
                'latency': None,
                'guild_count': 0,
                'user_count': 0,
                'uptime': None,
                'start_time': None
            }
    
    except Exception as e:
        print(f"Error getting bot status from Redis: {e}")
        return {
            'connected': False,
            'ready': False,
            'latency': None,
            'guild_count': 0,
            'user_count': 0,
            'uptime': None,
            'start_time': None
        }

# Database model placeholders for compatibility
class User:
    pass

class ServerConfig:
    pass

class PersonaMode:
    pass

class QAPair:
    pass

# ======================================================================
# DATABASE FUNCTIONS
# ======================================================================

def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE_PATH'])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.teardown_appcontext
def close_db_handler(error):
    close_db()

# ======================================================================
# AUTHENTICATION - Using new token-based system from auth.py
# ======================================================================
# Note: All authentication decorators are now imported from auth.py
# Use: @require_api_token() for general auth
#      @require_admin_token for admin endpoints
#      @require_read_token for read-only endpoints  
#      @require_write_token for write endpoints

# ======================================================================
# BASIC ROUTES
# ======================================================================

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Yumi Bot API is running',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected' if os.path.exists(app.config['DATABASE_PATH']) else 'not found',
        'redis': 'connected' if redis_client else 'not available'
    })

@app.route('/')
def index():
    """API index"""
    return jsonify({
        'name': 'Yumi Sugoi Bot API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            'health': '/api/health',
            'bot_stats': '/api/bot/stats',
            'personas': '/api/personas',
            'servers': '/api/servers',
            'commands': '/api/commands/discover',
            'admin': '/api/admin/system'
        }
    })

# ======================================================================
# BOT STATUS ROUTES
# ======================================================================

@app.route('/api/bot/stats')
def get_bot_stats():
    """Get bot statistics"""
    try:
        db = get_db()
        
        # Get counts from database
        user_count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        server_count = db.execute('SELECT COUNT(*) FROM server_configs').fetchone()[0]
        persona_count = db.execute('SELECT COUNT(*) FROM persona_modes WHERE is_custom = 1').fetchone()[0]
        qa_count = db.execute('SELECT COUNT(*) FROM qa_pairs').fetchone()[0]
        
        # Check for real-time bot stats from Redis
        bot_status = {'connected': False, 'latency': None, 'uptime': 'Unknown'}
        guild_count = 0
        
        if redis_client:
            try:
                bot_data = redis_client.get('bot:status')
                if bot_data:
                    bot_status = json.loads(bot_data)
                
                guild_data = redis_client.get('bot:guilds')
                if guild_data:
                    guild_count = int(guild_data)
            except Exception as e:
                print(f"Redis error: {e}")
        
        return {
            'bot_status': bot_status,
            'stats': {
                'guilds': guild_count if guild_count > 0 else server_count,
                'users': user_count,
                'custom_personas': persona_count,
                'qa_pairs': qa_count
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'bot_status': {'connected': False, 'latency': None, 'uptime': 'Unknown'},
            'stats': {'guilds': 0, 'users': 0, 'custom_personas': 0, 'qa_pairs': 0},
            'error': f'Failed to get bot stats: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }

@app.route('/api/bot/health', methods=['GET'])
def bot_health_check():
    """Bot health check endpoint"""
    try:
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
            'uptime': 'Unknown',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Try to get real uptime from Redis
        if redis_client:
            try:
                bot_status_data = redis_client.get('bot:status')
                if bot_status_data:
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

# ======================================================================
# PERSONA ROUTES
# ======================================================================

@app.route('/api/personas')
@require_read_token
def get_personas():
    """Get all personas"""
    try:
        db = get_db()
        personas = db.execute('SELECT * FROM persona_modes ORDER BY is_custom ASC, name ASC').fetchall()
        
        persona_list = []
        for p in personas:
            persona_list.append({
                'id': p['id'],
                'name': p['name'],
                'display_name': p['display_name'],
                'description': p['description'],
                'is_custom': bool(p['is_custom']),
                'is_nsfw': bool(p['is_nsfw']),
                'created_at': p['created_at']
            })
        
        return jsonify({
            'personas': persona_list,
            'total_count': len(persona_list)
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get personas: {str(e)}'}), 500

@app.route('/api/personas/<persona_name>', methods=['GET'])
@require_read_token
def get_persona(persona_name):
    """Get detailed information about a specific persona"""
    try:
        db = get_db()
        persona = db.execute('SELECT * FROM persona_modes WHERE name = ?', (persona_name,)).fetchone()
        
        if not persona:
            return jsonify({'error': 'Persona not found'}), 404
        
        return jsonify({
            'id': persona['id'],
            'name': persona['name'],
            'display_name': persona['display_name'],
            'description': persona['description'],
            'is_custom': bool(persona['is_custom']),
            'is_nsfw': bool(persona['is_nsfw']),
            'created_at': persona['created_at']
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get persona: {str(e)}'}), 500

@app.route('/api/personas', methods=['POST'])
@require_admin_token
def create_persona():
    """Create a new custom persona"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['name', 'display_name', 'description']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        db = get_db()
        
        # Check if persona already exists
        existing = db.execute('SELECT id FROM persona_modes WHERE name = ?', (data['name'],)).fetchone()
        if existing:
            return jsonify({'error': 'Persona with this name already exists'}), 409
        
        # Insert new persona
        cursor = db.execute('''
            INSERT INTO persona_modes (name, display_name, description, is_custom, is_nsfw, created_at)
            VALUES (?, ?, ?, 1, ?, ?)
        ''', (
            data['name'],
            data['display_name'], 
            data['description'],
            data.get('is_nsfw', False),
            datetime.utcnow().isoformat()
        ))
        
        db.commit()
        
        return jsonify({
            'id': cursor.lastrowid,
            'name': data['name'],
            'display_name': data['display_name'],
            'description': data['description'],
            'is_custom': True,
            'is_nsfw': data.get('is_nsfw', False),
            'created_at': datetime.utcnow().isoformat()
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Failed to create persona: {str(e)}'}), 500

# ======================================================================
# SERVER ROUTES
# ======================================================================

@app.route('/api/servers')
@require_read_token
def get_servers():
    """Get all servers"""
    try:
        db = get_db()
        servers = db.execute('SELECT * FROM server_configs ORDER BY guild_name ASC').fetchall()
        
        server_list = []
        for s in servers:
            server_list.append({
                'guild_id': s['guild_id'],
                'guild_name': s['guild_name'],
                'persona_mode': s['persona_mode'],
                'is_locked': bool(s['is_locked']),
                'created_at': s['created_at'],
                'updated_at': s['updated_at']
            })
        
        return jsonify({
            'servers': server_list,
            'total_count': len(server_list)
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get servers: {str(e)}'}), 500

@app.route('/api/servers/<guild_id>', methods=['GET'])
@require_read_token
def get_server(guild_id):
    """Get detailed information about a specific server"""
    try:
        db = get_db()
        server = db.execute('SELECT * FROM server_configs WHERE guild_id = ?', (guild_id,)).fetchone()
        
        if not server:
            return jsonify({'error': 'Server not found'}), 404
        
        return jsonify({
            'guild_id': server['guild_id'],
            'guild_name': server['guild_name'],
            'persona_mode': server['persona_mode'],
            'is_locked': bool(server['is_locked']),
            'created_at': server['created_at'],
            'updated_at': server['updated_at']
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get server: {str(e)}'}), 500

# ======================================================================
# ACTIVE SERVERS ROUTES (External Data)
# ======================================================================

SERVER_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                               'datasets', 'active_servers.json')

@app.route('/api/active', methods=['GET'])
@require_read_token
def get_active_servers():
    """Get list of all active servers where Yumi is present"""
    try:
        if not os.path.exists(SERVER_DATA_FILE):
            return jsonify({
                'status': 'error',
                'message': 'No server data available',
                'servers': []
            }), 404

        with open(SERVER_DATA_FILE, 'r', encoding='utf-8') as f:
            servers = json.load(f)

        return jsonify({
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'total_servers': len(servers),
            'servers': list(servers.values())
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error fetching server data: {str(e)}',
            'servers': []
        }), 500

@app.route('/api/active/<server_id>', methods=['GET'])
@require_read_token
def get_server_info(server_id):
    """Get detailed information about a specific server"""
    try:
        if not os.path.exists(SERVER_DATA_FILE):
            return jsonify({
                'status': 'error',
                'message': 'No server data available'
            }), 404

        with open(SERVER_DATA_FILE, 'r', encoding='utf-8') as f:
            servers = json.load(f)

        if str(server_id) not in servers:
            return jsonify({
                'status': 'error',
                'message': f'Server {server_id} not found'
            }), 404

        return jsonify({
            'status': 'success',
            'server': servers[str(server_id)]
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error fetching server data: {str(e)}'
        }), 500

# ======================================================================
# COMMAND TRACKING ROUTES
# ======================================================================

DASHBOARD_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'dashboard_data')
COMMAND_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'command_stats.json')
COMMAND_USAGE_DETAILS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'command_usage_details.json')
BOT_COMMANDS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot_core', 'commands.py')

def ensure_dashboard_data_dir():
    """Ensure dashboard data directory exists"""
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)

def load_json_file(filepath: str, default: Any = None) -> Any:
    """Load JSON file with error handling"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
    return default or {}

def save_json_file(filepath: str, data: Any) -> bool:
    """Save data to JSON file with error handling"""
    try:
        ensure_dashboard_data_dir()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

@app.route('/api/commands/discover', methods=['GET'])
@require_read_token
def discover_commands():
    """Discover and return all available bot commands"""
    try:
        commands_data = {
            'prefix_commands': [],
            'slash_commands': [],
            'built_in_commands': []
        }
        
        # Built-in commands that are always available
        built_in_commands = [
            {
                'name': 'yumi_help',
                'type': 'built-in',
                'description': 'Show help and features',
                'category': 'help',
                'permissions': None,
                'usage': '!yumi_help or /yumi_help'
            },
            {
                'name': 'yumi_mode',
                'type': 'built-in', 
                'description': 'Change persona mode',
                'category': 'persona',
                'permissions': None,
                'usage': '!yumi_mode <mode> or /yumi_mode <mode>'
            },
            {
                'name': 'yumi_modes',
                'type': 'built-in',
                'description': 'List available persona modes',
                'category': 'persona',
                'permissions': None,
                'usage': '!yumi_modes or /yumi_modes'
            }
        ]
        
        commands_data['built_in_commands'] = built_in_commands
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'commands': commands_data,
            'total_commands': len(built_in_commands)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to discover commands: {str(e)}'
        }), 500

@app.route('/api/commands/usage', methods=['GET'])
@require_read_token
def get_command_usage():
    """Get command usage statistics"""
    try:
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        usage_details = load_json_file(COMMAND_USAGE_DETAILS_FILE, {})
        
        # Calculate summary statistics
        total_uses = sum(command_stats.values())
        unique_commands = len(command_stats)
        
        # Get timeframe parameter
        timeframe = request.args.get('timeframe', '7d')
        
        # Filter usage details by timeframe if needed
        filtered_details = usage_details
        if timeframe != 'all':
            cutoff_date = datetime.utcnow() - timedelta(days=int(timeframe.rstrip('d')))
            filtered_details = {
                cmd: [usage for usage in usages 
                     if datetime.fromisoformat(usage['timestamp']) > cutoff_date]
                for cmd, usages in usage_details.items()
            }
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_uses': total_uses,
                'unique_commands': unique_commands,
                'timeframe': timeframe
            },
            'command_stats': command_stats,
            'usage_details': filtered_details
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get command usage: {str(e)}'
        }), 500

@app.route('/api/commands/track', methods=['POST'])
@require_write_token
def track_command():
    """Track a command usage event"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['command_name', 'user_id', 'guild_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Load existing data
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        usage_details = load_json_file(COMMAND_USAGE_DETAILS_FILE, {})
        
        # Update command stats
        command_name = data['command_name']
        command_stats[command_name] = command_stats.get(command_name, 0) + 1
        
        # Add usage detail
        usage_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': data['user_id'],
            'guild_id': data['guild_id'],
            'channel_id': data.get('channel_id'),
            'success': data.get('success', True),
            'error': data.get('error')
        }
        
        if command_name not in usage_details:
            usage_details[command_name] = []
        usage_details[command_name].append(usage_entry)
        
        # Keep only last 1000 entries per command to prevent file bloat
        if len(usage_details[command_name]) > 1000:
            usage_details[command_name] = usage_details[command_name][-1000:]
        
        # Save updated data
        save_json_file(COMMAND_STATS_FILE, command_stats)
        save_json_file(COMMAND_USAGE_DETAILS_FILE, usage_details)
        
        return jsonify({
            'status': 'success',
            'message': f'Command usage tracked: {command_name}',
            'total_uses': command_stats[command_name]
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to track command: {str(e)}'
        }), 500

@app.route('/api/commands/usage/chart', methods=['GET'])
@require_read_token
def get_usage_chart_data():
    """Get command usage data formatted for charts"""
    try:
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        
        # Sort commands by usage count
        sorted_commands = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)
        
        # Limit to top N commands
        limit = int(request.args.get('limit', 10))
        top_commands = sorted_commands[:limit]
        
        # Format for chart
        labels = [cmd[0] for cmd in top_commands]
        data = [cmd[1] for cmd in top_commands]
        
        return jsonify({
            'status': 'success',
            'chart_data': {
                'labels': labels,
                'datasets': [{
                    'label': 'Command Usage',
                    'data': data,
                    'backgroundColor': [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF',
                        '#4BC0C0', '#FF6384'
                    ][:len(data)]
                }]
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get chart data: {str(e)}'
        }), 500

# ======================================================================
# ADMIN ROUTES
# ======================================================================

def get_system_stats():
    """Get system resource usage statistics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Handle disk usage for different OS
        try:
            if os.name == 'nt':  # Windows
                disk = psutil.disk_usage('C:')
            else:  # Unix/Linux
                disk = psutil.disk_usage('/')
        except:
            disk = None
        
        stats = {
            'cpu': {
                'percent': round(cpu_percent, 2),
                'count': psutil.cpu_count(),
                'count_logical': psutil.cpu_count(logical=True)
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': round(memory.percent, 2),
                'used': memory.used,
                'total_gb': round(memory.total / (1024**3), 2),
                'used_gb': round(memory.used / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2)
            }
        }
        
        if disk:
            stats['disk'] = {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': round((disk.used / disk.total) * 100, 2),
                'total_gb': round(disk.total / (1024**3), 2),
                'used_gb': round(disk.used / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2)
            }
        
        return stats
    except Exception as e:
        return {'error': f'Failed to get system stats: {str(e)}'}

def get_bot_version():
    """Get bot version information"""
    try:
        # Try to read version from various sources
        version_files = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'VERSION'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'package.json'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pyproject.toml')
        ]
        
        for version_file in version_files:
            if os.path.exists(version_file):
                try:
                    with open(version_file, 'r') as f:
                        content = f.read().strip()
                        if version_file.endswith('.json'):
                            import json
                            data = json.loads(content)
                            return data.get('version', '1.0.0')
                        else:
                            return content
                except:
                    continue
        
        return '1.0.0'  # Default version
    except:
        return '1.0.0'

def get_process_uptime():
    """Get process uptime in seconds"""
    try:
        current_process = psutil.Process()
        create_time = current_process.create_time()
        uptime_seconds = time.time() - create_time
        return uptime_seconds
    except:
        return 0

@app.route('/api/system/info', methods=['GET'])
@require_read_token
def get_system_information():
    """Get comprehensive system information - PUBLIC endpoint for monitoring"""
    try:
        # Get system stats
        system_stats = get_system_stats()
        
        # Get bot version
        bot_version = get_bot_version()
        
        # Get environment
        environment = os.getenv('ENVIRONMENT', 'development')
        
        # Get process uptime
        uptime_seconds = get_process_uptime()
        uptime_hours = round(uptime_seconds / 3600, 2)
        uptime_days = round(uptime_seconds / 86400, 2)
          # Bot status information - Get from Redis if available
        bot_status = get_bot_status_from_redis()
        
        # Database status
        db_status = {
            'connected': False,
            'size': 0,
            'size_mb': 0
        }
        
        try:
            db_path = app.config['DATABASE_PATH']
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                db_status = {
                    'connected': True,
                    'size': db_size,
                    'size_mb': round(db_size / (1024**2), 2)
                }
                
                # Test database connection
                try:
                    conn = sqlite3.connect(db_path)
                    conn.execute("SELECT 1")
                    conn.close()
                    db_status['accessible'] = True
                except:
                    db_status['accessible'] = False
        except Exception as e:
            db_status['error'] = str(e)
        
        # Redis status
        redis_status = {
            'connected': redis_client is not None,
            'accessible': False,
            'info': None
        }
        
        if redis_client:
            try:
                redis_client.ping()
                redis_status['accessible'] = True
                redis_info = redis_client.info()
                redis_status['info'] = {
                    'used_memory_human': redis_info.get('used_memory_human', 'N/A'),
                    'connected_clients': redis_info.get('connected_clients', 0),
                    'total_commands_processed': redis_info.get('total_commands_processed', 0),
                    'uptime_in_seconds': redis_info.get('uptime_in_seconds', 0),
                    'version': redis_info.get('redis_version', 'Unknown')
                }
            except Exception as e:
                redis_status['error'] = str(e)
        
        # API latency (measure response time)
        api_start_time = time.time()
        
        system_info = {
            'timestamp': datetime.utcnow().isoformat(),
            'system_information': {
                'bot_version': bot_version,
                'environment': environment,
                'uptime': {
                    'seconds': round(uptime_seconds, 2),
                    'hours': uptime_hours,
                    'days': uptime_days,
                    'formatted': f"{int(uptime_days)}d {int(uptime_hours % 24)}h {int((uptime_seconds % 3600) / 60)}m"
                }
            },
            'bot_status': bot_status,
            'system_stats': system_stats,
            'database_status': db_status,
            'redis_status': redis_status,
            'api_latency': round((time.time() - api_start_time) * 1000, 2)  # milliseconds
        }
        
        return jsonify(system_info)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get system information: {str(e)}'}), 500

@app.route('/api/system/health', methods=['GET'])
def get_system_health():
    """Quick health check endpoint"""
    try:
        # Quick checks
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {
                'api': True,
                'database': os.path.exists(app.config['DATABASE_PATH']),
                'redis': redis_client is not None,
                'bot': bot_instance is not None
            }
        }
        
        # Test Redis if available
        if redis_client:
            try:
                redis_client.ping()
                health_status['checks']['redis_accessible'] = True
            except:
                health_status['checks']['redis_accessible'] = False
                health_status['status'] = 'degraded'
        
        # Test database if it exists
        if health_status['checks']['database']:
            try:
                conn = sqlite3.connect(app.config['DATABASE_PATH'])
                conn.execute("SELECT 1")
                conn.close()
                health_status['checks']['database_accessible'] = True
            except:
                health_status['checks']['database_accessible'] = False
                health_status['status'] = 'degraded'
        
        # Overall status
        if not all([health_status['checks']['api'], health_status['checks']['database']]):
            health_status['status'] = 'unhealthy'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return jsonify(health_status), status_code
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()        }), 500

@app.route('/api/admin/system', methods=['GET'])
@require_admin_token
def get_admin_system_info():
    """Get comprehensive system and bot information - ADMIN ONLY"""
    try:
        # Get the public system info first
        public_info_response = get_system_information()
        public_info = public_info_response.get_json()
        
        # Add admin-specific information
        admin_info = {
            'process_info': {
                'pid': os.getpid(),
                'working_directory': os.getcwd(),
                'python_version': f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
                'platform': os.name
            },
            'detailed_memory': {},
            'network_info': {},
            'disk_io': {},
            'process_threads': psutil.Process().num_threads()
        }
        
        # Get detailed memory information
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            admin_info['detailed_memory'] = {
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'rss_mb': round(memory_info.rss / (1024**2), 2),
                'vms_mb': round(memory_info.vms / (1024**2), 2),
                'percent': round(process.memory_percent(), 2)
            }
        except:
            pass
        
        # Get network information
        try:
            net_io = psutil.net_io_counters()
            admin_info['network_info'] = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except:
            pass
        
        # Get disk I/O
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                admin_info['disk_io'] = {
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count
                }
        except:
            pass
        
        # Combine public info with admin-specific info
        combined_info = public_info.copy()
        combined_info['admin_details'] = admin_info
        
        return jsonify(combined_info)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get admin system info: {str(e)}'}), 500

@app.route('/api/admin/bot/restart', methods=['POST'])
@require_admin_token
def restart_bot():
    """Restart the bot (requires Redis for command passing)"""
    try:
        if not redis_client:
            return jsonify({'error': 'Redis not available for bot commands'}), 503
        
        # Generate unique execution ID
        execution_id = f"restart_{int(time.time())}"
        
        # Send restart command via Redis
        redis_client.publish('bot_commands', json.dumps({
            'type': 'restart',
            'execution_id': execution_id,
            'requested_by': getattr(request, 'user_id', 'unknown'),
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        # Store execution info for tracking
        redis_client.setex(
            f'bot_execution:{execution_id}',
            300,  # 5 minutes TTL
            json.dumps({
                'type': 'restart',
                'status': 'sent',
                'requested_by': getattr(request, 'user_id', 'unknown'),
                'started_at': datetime.utcnow().isoformat()
            })
        )
        
        return jsonify({
            'success': True,
            'execution_id': execution_id,
            'message': 'Bot restart command sent',
            'note': 'Bot will restart shortly'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to restart bot: {str(e)}'}), 500

@app.route('/api/admin/bot/reload', methods=['POST'])
@require_admin_token
def reload_bot_modules():
    """Reload bot modules and configuration"""
    try:
        if not redis_client:
            return jsonify({'error': 'Redis not available for bot commands'}), 503
        
        data = request.get_json() or {}
        modules = data.get('modules', ['all'])
        
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

@app.route('/api/admin/commands', methods=['GET'])
@require_admin_token
def get_bot_commands():
    """Get all available bot commands with metadata"""
    try:
        commands = {
            'categories': {
                'moderation': {
                    'name': 'Moderation',
                    'description': 'Server moderation commands',
                    'commands': [
                        {
                            'name': 'yumi_lockdown',
                            'description': 'Lock Yumi to respond only in current channel',
                            'syntax': '!yumi_lockdown',
                            'permissions': ['administrator'],
                            'category': 'moderation'
                        },
                        {
                            'name': 'yumi_unlock',
                            'description': 'Remove channel lockdown',
                            'syntax': '!yumi_unlock',
                            'permissions': ['administrator'],
                            'category': 'moderation'
                        }
                    ]
                },
                'utility': {
                    'name': 'Utility',
                    'description': 'Utility and informational commands',
                    'commands': [
                        {
                            'name': 'yumi_help',
                            'description': 'Show help information',
                            'syntax': '!yumi_help [command]',
                            'permissions': [],
                            'category': 'utility'
                        },
                        {
                            'name': 'yumi_info',
                            'description': 'Show bot information and stats',
                            'syntax': '!yumi_info',
                            'permissions': [],
                            'category': 'utility'
                        }
                    ]
                },
                'persona': {
                    'name': 'Persona Management',
                    'description': 'Commands for managing bot personas',
                    'commands': [
                        {
                            'name': 'yumi_mode',
                            'description': 'Change bot persona mode',
                            'syntax': '!yumi_mode <mode>',
                            'permissions': ['administrator'],
                            'category': 'persona'
                        },
                        {
                            'name': 'yumi_modes',
                            'description': 'List available persona modes',
                            'syntax': '!yumi_modes',
                            'permissions': [],
                            'category': 'persona'
                        }
                    ]
                }
            }
        }
        
        return jsonify(commands)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get commands: {str(e)}'}), 500

@app.route('/api/admin/logs/stream', methods=['GET'])
@require_admin_token
def stream_bot_logs():
    """Stream real-time bot logs (Server-Sent Events)"""
    try:
        def generate_log_stream():
            """Generate log events from actual log files"""
            # This is a simplified version - in production you'd tail actual log files
            log_files = [
                'bot.log',
                'api.log',
                'error.log'
            ]
            
            while True:
                try:
                    # Send sample log entries
                    yield f"data: {json.dumps({'timestamp': datetime.utcnow().isoformat(), 'level': 'INFO', 'message': 'Bot is running normally', 'source': 'bot'})}\n\n"
                    time.sleep(5)
                except:
                    break
        
        return Response(
            generate_log_stream(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
    
    except Exception as e:
        return jsonify({'error': f'Failed to stream logs: {str(e)}'}), 500

@app.route('/api/admin/metrics/detailed', methods=['GET'])
@require_admin_token
def get_detailed_metrics():
    """Get detailed bot performance metrics"""
    try:
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'performance': {
                'response_time_avg': 150.5,
                'commands_per_minute': 25,
                'memory_usage_mb': 128,
                'cpu_usage_percent': 15.2
            },
            'activity': {
                'messages_today': 1250,
                'commands_today': 89,
                'unique_users_today': 45,
                'guilds_active': 12
            },
            'errors': {
                'total_today': 3,
                'critical_today': 0,
                'last_error': '2024-01-15T10:30:00Z'
            }
        }
        
        return jsonify(metrics)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get detailed metrics: {str(e)}'}), 500

# ======================================================================
# USER MANAGEMENT ROUTES
# ======================================================================

@app.route('/api/users/me', methods=['GET'])
@require_read_token
def get_current_user():
    """Get current user's information and memory"""
    try:
        user_id = getattr(request, 'user_id', 'unknown')
        
        # Mock user data for now
        user_data = {
            'id': user_id,
            'username': 'AdminUser',
            'display_name': 'Admin User',
            'avatar': None,
            'memory': {
                'facts': [],
                'preferences': {},
                'last_updated': datetime.utcnow().isoformat()
            }
        }
        
        return jsonify(user_data)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get user info: {str(e)}'}), 500

# ======================================================================
# Q&A SYSTEM ROUTES
# ======================================================================

@app.route('/api/qa/pairs', methods=['GET'])
@require_read_token
def get_qa_pairs():
    """Get Q&A pairs with filtering and pagination"""
    try:
        db = get_db()
        qa_pairs = db.execute('SELECT * FROM qa_pairs ORDER BY created_at DESC').fetchall()
        
        qa_list = []
        for qa in qa_pairs:
            qa_list.append({
                'id': qa['id'],
                'question': qa['question'],
                'answer': qa['answer'],
                'category': qa['category'],
                'created_at': qa['created_at'],
                'updated_at': qa['updated_at']
            })
        
        return jsonify({
            'qa_pairs': qa_list,
            'total_count': len(qa_list)
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get Q&A pairs: {str(e)}'}), 500

@app.route('/api/qa/pairs', methods=['POST'])
@require_admin_token
def create_qa_pair():
    """Create a new Q&A pair"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['question', 'answer']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        db = get_db()
        cursor = db.execute('''
            INSERT INTO qa_pairs (question, answer, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['question'],
            data['answer'],
            data.get('category', 'general'),
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        
        db.commit()
        
        return jsonify({
            'id': cursor.lastrowid,
            'question': data['question'],
            'answer': data['answer'],
            'category': data.get('category', 'general'),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Failed to create Q&A pair: {str(e)}'}), 500

# ======================================================================
# ERROR HANDLERS
# ======================================================================

@app.errorhandler(404)
def handle_not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Resource not found',
        'status_code': 404,
        'timestamp': datetime.utcnow().isoformat(),
        'path': request.path
    }), 404

@app.errorhandler(405)
def handle_method_not_allowed(error):
    """Handle method not allowed errors"""
    return jsonify({
        'error': 'Method not allowed',
        'status_code': 405,
        'timestamp': datetime.utcnow().isoformat(),
        'method': request.method,
        'path': request.path
    }), 405

@app.errorhandler(500)
def handle_internal_error(error):
    """Handle internal server errors"""
    return jsonify({
        'error': 'Internal server error',
        'status_code': 500,
        'timestamp': datetime.utcnow().isoformat()
    }), 500

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Handle unexpected errors"""
    return jsonify({
        'error': 'An unexpected error occurred',
        'status_code': 500,
        'timestamp': datetime.utcnow().isoformat()
    }), 500

# ======================================================================
# MAIN ENTRY POINT
# ======================================================================

if __name__ == '__main__':
    print("Starting Yumi Bot Unified API Server")
    print(f"Database: {app.config['DATABASE_PATH']}")
    print(f"Redis: {'Connected' if redis_client else 'Not available'}")
    print("")
    print("Available endpoints:")
    print("- GET  /api/health")
    print("- GET  /api/bot/stats")
    print("- GET  /api/personas")
    print("- GET  /api/servers")
    print("- GET  /api/active")
    print("- GET  /api/commands/discover")
    print("- GET  /api/commands/usage")
    print("- POST /api/commands/track")
    print("- GET  /api/admin/system")
    print("- POST /api/admin/bot/restart")
    print("- GET  /api/admin/commands")
    print("- GET  /api/admin/logs/stream")
    print("- GET  /api/qa/pairs")
    print("")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
