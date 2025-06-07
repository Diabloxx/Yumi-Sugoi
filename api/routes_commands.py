"""
Command Discovery and Usage Tracking API Routes
This module provides endpoints for command discovery, usage statistics, and analytics
for the external dashboard.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

from flask import Blueprint, request, jsonify, g
import inspect
import importlib.util

commands_bp = Blueprint('commands', __name__)

# File paths
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

def discover_bot_commands() -> Dict[str, List[Dict[str, Any]]]:
    """Discover all bot commands from the commands.py file"""
    commands_data = {
        'prefix_commands': [],
        'slash_commands': [],
        'built_in_commands': []
    }
    
    try:
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
            }
        ]
        
        # Read commands.py file and parse command definitions
        if os.path.exists(BOT_COMMANDS_FILE):
            with open(BOT_COMMANDS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse prefix commands (@bot.command decorators)
            import re
            
            # Find @bot.command definitions
            prefix_pattern = r'@bot\.command\(name="([^"]+)"\)'
            prefix_matches = re.findall(prefix_pattern, content)
            
            # Find function definitions and docstrings
            func_pattern = r'async def (\w+)\(.*?\):\s*"""([^"]*?)"""'
            func_matches = re.findall(func_pattern, content, re.DOTALL)
            func_docs = {name: desc.strip() for name, desc in func_matches}
            
            # Find @commands.has_permissions decorators
            perm_pattern = r'@commands\.has_permissions\(([^)]+)\)\s*async def (\w+)'
            perm_matches = re.findall(perm_pattern, content)
            func_perms = {name: perms for perms, name in perm_matches}
            
            for cmd_name in prefix_matches:
                commands_data['prefix_commands'].append({
                    'name': cmd_name,
                    'type': 'prefix',
                    'description': func_docs.get(cmd_name, 'No description available'),
                    'category': categorize_command(cmd_name),
                    'permissions': func_perms.get(cmd_name),
                    'usage': f'!{cmd_name}'
                })
            
            # Find @bot.tree.command definitions (slash commands)
            slash_pattern = r'@bot\.tree\.command\(name="([^"]+)".*?description="([^"]*)"'
            slash_matches = re.findall(slash_pattern, content, re.DOTALL)
            
            # Find @app_commands.checks.has_permissions decorators
            slash_perm_pattern = r'@app_commands\.checks\.has_permissions\(([^)]+)\)\s*async def (\w+)'
            slash_perm_matches = re.findall(slash_perm_pattern, content)
            slash_func_perms = {name: perms for perms, name in slash_perm_matches}
            
            for cmd_name, description in slash_matches:
                func_name = f"{cmd_name}_slash"
                commands_data['slash_commands'].append({
                    'name': cmd_name,
                    'type': 'slash',
                    'description': description.strip(),
                    'category': categorize_command(cmd_name),
                    'permissions': slash_func_perms.get(func_name),
                    'usage': f'/{cmd_name}'
                })
        
        commands_data['built_in_commands'] = built_in_commands
        
        print(f"[Command Discovery] Found {len(commands_data['prefix_commands'])} prefix commands, "
              f"{len(commands_data['slash_commands'])} slash commands, "
              f"{len(commands_data['built_in_commands'])} built-in commands")
        
    except Exception as e:
        print(f"Error discovering commands: {e}")
    
    return commands_data

def categorize_command(command_name: str) -> str:
    """Categorize command based on name patterns"""
    if 'persona' in command_name or 'mode' in command_name:
        return 'persona'
    elif any(word in command_name for word in ['kick', 'ban', 'warn', 'purge', 'slowmode']):
        return 'moderation'
    elif any(word in command_name for word in ['userinfo', 'serverinfo', 'ping']):
        return 'info'
    elif any(word in command_name for word in ['help', 'commands']):
        return 'help'
    elif any(word in command_name for word in ['lockdown', 'unlock', 'admin']):
        return 'admin'
    elif any(word in command_name for word in ['hug', 'kiss', 'uwu', 'meme', 'poll']):
        return 'fun'
    else:
        return 'other'

@commands_bp.route('/api/commands/discover', methods=['GET'])
def discover_commands():
    """Discover and return all available bot commands"""
    try:
        commands_data = discover_bot_commands()
        
        # Flatten all commands for easier consumption
        all_commands = []
        for command_type, commands in commands_data.items():
            all_commands.extend(commands)
        
        # Group by category
        by_category = defaultdict(list)
        for cmd in all_commands:
            by_category[cmd['category']].append(cmd)
        
        return jsonify({
            'status': 'success',
            'commands': {
                'all': all_commands,
                'by_type': commands_data,
                'by_category': dict(by_category),
                'total_count': len(all_commands),
                'counts': {
                    'prefix': len(commands_data['prefix_commands']),
                    'slash': len(commands_data['slash_commands']),
                    'built_in': len(commands_data['built_in_commands'])
                }
            },
            'discovered_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to discover commands: {str(e)}'
        }), 500

@commands_bp.route('/api/commands/usage', methods=['GET'])
def get_command_usage():
    """Get command usage statistics"""
    try:
        # Load basic command stats
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        
        # Load detailed usage data
        usage_details = load_json_file(COMMAND_USAGE_DETAILS_FILE, {})
        
        # Calculate additional metrics
        total_commands = sum(command_stats.values())
        most_used = max(command_stats.items(), key=lambda x: x[1]) if command_stats else ("none", 0)
        
        # Prepare response data
        usage_data = []
        for cmd_name, count in command_stats.items():
            details = usage_details.get(cmd_name, {})
            usage_data.append({
                'name': cmd_name,
                'count': count,
                'percentage': (count / total_commands * 100) if total_commands > 0 else 0,
                'last_used': details.get('last_used'),
                'users_count': len(details.get('users', [])),
                'servers_count': len(details.get('servers', [])),
                'daily_average': details.get('daily_average', 0),
                'weekly_trend': details.get('weekly_trend', 0)
            })
        
        # Sort by usage count
        usage_data.sort(key=lambda x: x['count'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'usage': {
                'commands': usage_data,
                'summary': {
                    'total_commands_executed': total_commands,
                    'unique_commands': len(command_stats),
                    'most_used_command': most_used[0],
                    'most_used_count': most_used[1],
                    'average_per_command': total_commands / len(command_stats) if command_stats else 0
                }
            },
            'updated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get command usage: {str(e)}'
        }), 500

@commands_bp.route('/api/commands/usage/chart', methods=['GET'])
def get_command_usage_chart():
    """Get command usage data formatted for charts"""
    try:
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        
        # Get top 10 most used commands
        sorted_commands = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        labels = [cmd[0] for cmd in sorted_commands]
        values = [cmd[1] for cmd in sorted_commands]
        
        return jsonify({
            'status': 'success',
            'chart_data': {
                'labels': labels,
                'values': values,
                'colors': ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', 
                          '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1'][:len(labels)]
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get chart data: {str(e)}'
        }), 500

@commands_bp.route('/api/commands/usage/timeline', methods=['GET'])
def get_command_usage_timeline():
    """Get command usage timeline data"""
    try:
        days = request.args.get('days', 7, type=int)
        command_name = request.args.get('command', None)
        
        usage_details = load_json_file(COMMAND_USAGE_DETAILS_FILE, {})
        
        # Generate timeline data
        timeline_data = []
        base_date = datetime.now() - timedelta(days=days-1)
        
        for i in range(days):
            current_date = base_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            
            if command_name:
                # Get specific command usage for this date
                cmd_details = usage_details.get(command_name, {})
                daily_usage = cmd_details.get('daily_usage', {})
                count = daily_usage.get(date_str, 0)
            else:
                # Get total usage for this date
                count = 0
                for cmd_details in usage_details.values():
                    daily_usage = cmd_details.get('daily_usage', {})
                    count += daily_usage.get(date_str, 0)
            
            timeline_data.append({
                'date': date_str,
                'count': count,
                'formatted_date': current_date.strftime('%m/%d')
            })
        
        return jsonify({
            'status': 'success',
            'timeline': {
                'data': timeline_data,
                'command': command_name,
                'days': days,
                'total': sum(item['count'] for item in timeline_data)
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get timeline data: {str(e)}'
        }), 500

@commands_bp.route('/api/commands/track', methods=['POST'])
def track_command_usage():
    """Track command usage (called by bot)"""
    try:
        data = request.get_json()
        if not data or 'command_name' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Command name required'
            }), 400
        
        command_name = data['command_name']
        user_id = data.get('user_id')
        server_id = data.get('server_id')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        command_type = data.get('type', 'unknown')  # prefix, slash, built-in
        
        # Update basic command stats
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        command_stats[command_name] = command_stats.get(command_name, 0) + 1
        save_json_file(COMMAND_STATS_FILE, command_stats)
        
        # Update detailed usage data
        usage_details = load_json_file(COMMAND_USAGE_DETAILS_FILE, {})
        
        if command_name not in usage_details:
            usage_details[command_name] = {
                'first_used': timestamp,
                'last_used': timestamp,
                'users': [],
                'servers': [],
                'daily_usage': {},
                'hourly_usage': {},
                'type_breakdown': {},
                'daily_average': 0,
                'weekly_trend': 0
            }
        
        cmd_details = usage_details[command_name]
        
        # Update tracking data
        cmd_details['last_used'] = timestamp
        
        # Track unique users and servers
        if user_id and user_id not in cmd_details['users']:
            cmd_details['users'].append(user_id)
        if server_id and server_id not in cmd_details['servers']:
            cmd_details['servers'].append(server_id)
        
        # Track daily usage
        date_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d')
        cmd_details['daily_usage'][date_str] = cmd_details['daily_usage'].get(date_str, 0) + 1
        
        # Track hourly usage
        hour_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%H')
        cmd_details['hourly_usage'][hour_str] = cmd_details['hourly_usage'].get(hour_str, 0) + 1
        
        # Track command type breakdown
        cmd_details['type_breakdown'][command_type] = cmd_details['type_breakdown'].get(command_type, 0) + 1
        
        # Calculate daily average (last 7 days)
        recent_days = []
        for i in range(7):
            day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            recent_days.append(cmd_details['daily_usage'].get(day, 0))
        cmd_details['daily_average'] = sum(recent_days) / 7
        
        save_json_file(COMMAND_USAGE_DETAILS_FILE, usage_details)
        
        return jsonify({
            'status': 'success',
            'message': 'Command usage tracked successfully',
            'command': command_name,
            'total_usage': command_stats[command_name]
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to track command usage: {str(e)}'
        }), 500

@commands_bp.route('/api/commands/stats/summary', methods=['GET'])
def get_command_stats_summary():
    """Get summary statistics for commands"""
    try:
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        usage_details = load_json_file(COMMAND_USAGE_DETAILS_FILE, {})
        
        # Calculate summary metrics
        total_commands = sum(command_stats.values())
        unique_commands = len(command_stats)
        
        # Most active period (hour of day)
        hourly_totals = defaultdict(int)
        for cmd_details in usage_details.values():
            for hour, count in cmd_details.get('hourly_usage', {}).items():
                hourly_totals[hour] += count
        
        most_active_hour = max(hourly_totals.items(), key=lambda x: x[1]) if hourly_totals else ("00", 0)
        
        # Command type breakdown
        type_breakdown = defaultdict(int)
        for cmd_details in usage_details.values():
            for cmd_type, count in cmd_details.get('type_breakdown', {}).items():
                type_breakdown[cmd_type] += count
        
        # Recent activity (last 24 hours)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        
        recent_activity = 0
        for cmd_details in usage_details.values():
            recent_activity += cmd_details.get('daily_usage', {}).get(yesterday, 0)
            recent_activity += cmd_details.get('daily_usage', {}).get(today, 0)
        
        return jsonify({
            'status': 'success',
            'summary': {
                'total_commands_executed': total_commands,
                'unique_commands_used': unique_commands,
                'most_active_hour': {
                    'hour': most_active_hour[0],
                    'count': most_active_hour[1]
                },
                'command_type_breakdown': dict(type_breakdown),
                'recent_activity_24h': recent_activity,
                'average_commands_per_day': total_commands / max(len(set().union(*[
                    cmd_details.get('daily_usage', {}).keys() 
                    for cmd_details in usage_details.values()
                ])), 1)
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get summary stats: {str(e)}'
        }), 500

@commands_bp.route('/api/commands/<command_name>/details', methods=['GET'])
def get_command_details(command_name: str):
    """Get detailed information about a specific command"""
    try:
        # Get command definition
        commands_data = discover_bot_commands()
        all_commands = []
        for command_type, commands in commands_data.items():
            all_commands.extend(commands)
        
        command_info = next((cmd for cmd in all_commands if cmd['name'] == command_name), None)
        
        if not command_info:
            return jsonify({
                'status': 'error',
                'message': f'Command {command_name} not found'
            }), 404
        
        # Get usage statistics
        command_stats = load_json_file(COMMAND_STATS_FILE, {})
        usage_details = load_json_file(COMMAND_USAGE_DETAILS_FILE, {})
        
        usage_count = command_stats.get(command_name, 0)
        details = usage_details.get(command_name, {})
        
        return jsonify({
            'status': 'success',
            'command': {
                **command_info,
                'usage_count': usage_count,
                'first_used': details.get('first_used'),
                'last_used': details.get('last_used'),
                'unique_users': len(details.get('users', [])),
                'unique_servers': len(details.get('servers', [])),
                'daily_average': details.get('daily_average', 0),
                'hourly_usage': details.get('hourly_usage', {}),
                'daily_usage': details.get('daily_usage', {}),
                'type_breakdown': details.get('type_breakdown', {})
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get command details: {str(e)}'
        }), 500

# Routes for database-based command tracking (future enhancement)
@commands_bp.route('/api/commands/db/init', methods=['POST'])
def init_command_database():
    """Initialize command tracking database tables"""
    try:
        from flask import current_app
        db_path = current_app.config.get('DATABASE_PATH')
        
        if not db_path:
            return jsonify({
                'status': 'error',
                'message': 'Database not configured'
            }), 500
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create command definitions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL, -- prefix, slash, built-in
                description TEXT,
                category TEXT,
                permissions TEXT,
                usage_example TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create command usage tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_name TEXT NOT NULL,
                user_id TEXT,
                server_id TEXT,
                channel_id TEXT,
                command_type TEXT, -- prefix, slash, built-in
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                execution_time_ms INTEGER,
                FOREIGN KEY (command_name) REFERENCES command_definitions(name)
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_command_usage_name ON command_usage(command_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_command_usage_date ON command_usage(executed_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_command_usage_user ON command_usage(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_command_usage_server ON command_usage(server_id)')
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Command tracking database initialized successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to initialize database: {str(e)}'
        }), 500

@commands_bp.route('/api/commands/db/sync', methods=['POST'])
def sync_commands_to_database():
    """Sync discovered commands to database"""
    try:
        from flask import current_app
        db_path = current_app.config.get('DATABASE_PATH')
        
        if not db_path:
            return jsonify({
                'status': 'error',
                'message': 'Database not configured'
            }), 500
        
        commands_data = discover_bot_commands()
        all_commands = []
        for command_type, commands in commands_data.items():
            all_commands.extend(commands)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        synced_count = 0
        for cmd in all_commands:
            cursor.execute('''
                INSERT OR REPLACE INTO command_definitions 
                (name, type, description, category, permissions, usage_example, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                cmd['name'],
                cmd['type'],
                cmd['description'],
                cmd['category'],
                cmd.get('permissions'),
                cmd['usage']
            ))
            synced_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': f'Synced {synced_count} commands to database'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to sync commands: {str(e)}'
        }), 500
