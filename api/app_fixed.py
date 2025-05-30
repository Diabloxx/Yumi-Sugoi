# Fixed Flask API Backend for Yumi Sugoi Discord Bot Dashboard
# This version uses direct SQLite operations to avoid SQLAlchemy 2.0 compatibility issues

import os
import sqlite3
import json
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional, Any

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import redis
import jwt

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'yumi_bot.db')
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'your-jwt-secret')
app.config['API_KEY'] = os.getenv('API_KEY', 'your-api-key')

# CORS setup for Next.js frontend
CORS(app, origins=[
    'http://localhost:3000',
    'http://localhost:3001',
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

# Bot instance (will be None for now)
bot_instance = None

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

# Authentication decorators
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key or api_key != app.config['API_KEY']:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated

def require_discord_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'error': 'Authorization header required'}), 401
            
            token = auth_header
            if token.startswith('Bearer '):
                token = token[7:]
            
            # For now, just check if token exists
            # In production, verify JWT token properly
            if not token:
                return jsonify({'error': 'Token required'}), 401
            
            # Mock user data for testing
            request.user_id = '123456789'
            request.is_admin = True
            
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not getattr(request, 'is_admin', False):
            return jsonify({'error': 'Admin permissions required'}), 403
        return f(*args, **kwargs)
    return decorated

# Basic routes
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
            'servers': '/api/servers'
        }
    })

# Bot status routes
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
                # Try to get real-time bot stats from Redis
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

# Persona routes
@app.route('/api/personas')
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

# Server data routes
SERVER_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                               'datasets', 'active_servers.json')

@app.route('/api/active', methods=['GET'])
def get_active_servers():
    """Get list of all active servers where Yumi is present"""
    try:
        # Check if file exists
        if not os.path.exists(SERVER_DATA_FILE):
            return jsonify({
                'status': 'error',
                'message': 'No server data available',
                'servers': []
            }), 404

        # Read server data
        with open(SERVER_DATA_FILE, 'r', encoding='utf-8') as f:
            servers = json.load(f)

        # Return formatted response
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
def get_server_info(server_id):
    """Get detailed information about a specific server"""
    try:
        # Check if file exists
        if not os.path.exists(SERVER_DATA_FILE):
            return jsonify({
                'status': 'error',
                'message': 'No server data available'
            }), 404

        # Read server data
        with open(SERVER_DATA_FILE, 'r', encoding='utf-8') as f:
            servers = json.load(f)

        # Check if server exists
        if str(server_id) not in servers:
            return jsonify({
                'status': 'error',
                'message': f'Server {server_id} not found'
            }), 404

        # Return server info
        return jsonify({
            'status': 'success',
            'server': servers[str(server_id)]
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error fetching server data: {str(e)}'
        }), 500

# Server routes
@app.route('/api/servers')
@require_discord_auth
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

if __name__ == '__main__':
    print("Starting Yumi Bot API Server")
    print(f"Database: {app.config['DATABASE_PATH']}")
    print(f"Redis: {'Connected' if redis_client else 'Not available'}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
