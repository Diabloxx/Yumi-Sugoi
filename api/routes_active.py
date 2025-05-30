from flask import Blueprint, jsonify
import os
import json
from datetime import datetime

# Create blueprint with url_prefix
active_bp = Blueprint('active', __name__, url_prefix='/api')

# File path for server data
SERVER_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                               'datasets', 'active_servers.json')

@active_bp.route('/active', methods=['GET'])
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

@active_bp.route('/servers/active/<server_id>', methods=['GET'])
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