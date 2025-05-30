"""
Persona management API routes for Yumi Sugoi Discord Bot Dashboard

Provides endpoints for managing bot personas, including built-in and custom personas,
persona switching, and persona-specific configurations.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import json
from typing import Dict, List, Optional

from .app import (
    bot_instance, db, redis_client,
    require_api_key, require_discord_auth, require_admin,
    PersonaMode, ServerConfig
)

personas_bp = Blueprint('personas', __name__)

def get_built_in_personas():
    """Get list of built-in persona modes"""
    try:
        from bot_core.main import PERSONA_MODES, CUSTOM_PERSONAS
        
        built_in = []
        for name, config in PERSONA_MODES.items():
            persona_data = {
                'name': name,
                'display_name': config.get('display_name', name.title()),
                'description': config.get('description', ''),
                'system_prompt': config.get('system_prompt', ''),
                'temperature': config.get('temperature', 0.7),
                'is_nsfw': config.get('nsfw', False),
                'is_custom': False,
                'is_built_in': True
            }
            built_in.append(persona_data)
        
        return built_in
    except Exception as e:
        print(f"Failed to get built-in personas: {e}")
        return []

@personas_bp.route('/api/personas', methods=['GET'])
@require_discord_auth
def get_personas():
    """Get all available personas (built-in and custom)"""
    try:
        # Get built-in personas
        personas = get_built_in_personas()
        
        # Get custom personas from database
        custom_personas = PersonaMode.query.filter_by(is_custom=True).all()
        for persona in custom_personas:
            personas.append(persona.to_dict())
        
        # Sort by name
        personas.sort(key=lambda x: x['display_name'].lower())
        
        return jsonify({
            'personas': personas,
            'total_count': len(personas),
            'built_in_count': len([p for p in personas if not p['is_custom']]),
            'custom_count': len([p for p in personas if p['is_custom']])
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get personas: {str(e)}'}), 500

@personas_bp.route('/api/personas/<persona_name>', methods=['GET'])
@require_discord_auth
def get_persona(persona_name):
    """Get detailed information about a specific persona"""
    try:
        # Check if it's a built-in persona first
        built_in_personas = get_built_in_personas()
        for persona in built_in_personas:
            if persona['name'] == persona_name:
                return jsonify(persona)
        
        # Check custom personas
        custom_persona = PersonaMode.query.filter_by(name=persona_name, is_custom=True).first()
        if custom_persona:
            return jsonify(custom_persona.to_dict())
        
        return jsonify({'error': 'Persona not found'}), 404
    
    except Exception as e:
        return jsonify({'error': f'Failed to get persona: {str(e)}'}), 500

@personas_bp.route('/api/personas', methods=['POST'])
@require_discord_auth
def create_persona():
    """Create a new custom persona"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'display_name', 'description', 'system_prompt']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if persona name already exists
        existing = PersonaMode.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({'error': 'Persona name already exists'}), 409
        
        # Check built-in personas too
        built_in_personas = get_built_in_personas()
        if any(p['name'] == data['name'] for p in built_in_personas):
            return jsonify({'error': 'Persona name conflicts with built-in persona'}), 409
        
        # Create new persona
        persona = PersonaMode(
            name=data['name'],
            display_name=data['display_name'],
            description=data['description'],
            system_prompt=data['system_prompt'],
            temperature=data.get('temperature', 0.7),
            is_nsfw=data.get('is_nsfw', False),
            is_custom=True,
            created_by=getattr(request, 'user_id', None)
        )
        
        db.session.add(persona)
        db.session.commit()
        
        # Notify bot of new persona via Redis
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'persona_created',
                    'persona': persona.to_dict()
                }))
            except Exception as e:
                print(f"Failed to notify bot of new persona: {e}")
        
        return jsonify(persona.to_dict()), 201
    
    except Exception as e:
        return jsonify({'error': f'Failed to create persona: {str(e)}'}), 500

@personas_bp.route('/api/personas/<int:persona_id>', methods=['PUT'])
@require_discord_auth
def update_persona(persona_id):
    """Update a custom persona"""
    try:
        persona = PersonaMode.query.get(persona_id)
        if not persona:
            return jsonify({'error': 'Persona not found'}), 404
        
        if not persona.is_custom:
            return jsonify({'error': 'Cannot modify built-in personas'}), 403
        
        # Check permissions (only creator or admin can modify)
        user_id = getattr(request, 'user_id', None)
        if persona.created_by != user_id and not getattr(request, 'is_admin', False):
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update fields
        if 'display_name' in data:
            persona.display_name = data['display_name']
        if 'description' in data:
            persona.description = data['description']
        if 'system_prompt' in data:
            persona.system_prompt = data['system_prompt']
        if 'temperature' in data:
            persona.temperature = min(max(data['temperature'], 0.0), 2.0)
        if 'is_nsfw' in data:
            persona.is_nsfw = data['is_nsfw']
        
        db.session.commit()
        
        # Notify bot of persona update via Redis
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'persona_updated',
                    'persona': persona.to_dict()
                }))
            except Exception as e:
                print(f"Failed to notify bot of persona update: {e}")
        
        return jsonify(persona.to_dict())
    
    except Exception as e:
        return jsonify({'error': f'Failed to update persona: {str(e)}'}), 500

@personas_bp.route('/api/personas/<int:persona_id>', methods=['DELETE'])
@require_discord_auth
def delete_persona(persona_id):
    """Delete a custom persona"""
    try:
        persona = PersonaMode.query.get(persona_id)
        if not persona:
            return jsonify({'error': 'Persona not found'}), 404
        
        if not persona.is_custom:
            return jsonify({'error': 'Cannot delete built-in personas'}), 403
        
        # Check permissions
        user_id = getattr(request, 'user_id', None)
        if persona.created_by != user_id and not getattr(request, 'is_admin', False):
            return jsonify({'error': 'Permission denied'}), 403
        
        # Check if persona is currently in use
        servers_using = ServerConfig.query.filter_by(persona_mode=persona.name).count()
        if servers_using > 0:
            return jsonify({
                'error': f'Cannot delete persona that is in use by {servers_using} server(s)'
            }), 409
        
        persona_name = persona.name
        db.session.delete(persona)
        db.session.commit()
        
        # Notify bot of persona deletion via Redis
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'persona_deleted',
                    'persona_name': persona_name
                }))
            except Exception as e:
                print(f"Failed to notify bot of persona deletion: {e}")
        
        return jsonify({'success': True, 'message': 'Persona deleted'})
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete persona: {str(e)}'}), 500

@personas_bp.route('/api/personas/<persona_name>/activate', methods=['POST'])
@require_discord_auth
def activate_persona_global(persona_name):
    """Activate a persona globally (requires admin)"""
    try:
        if not getattr(request, 'is_admin', False):
            return jsonify({'error': 'Admin permissions required'}), 403
        
        # Verify persona exists
        built_in_personas = get_built_in_personas()
        persona_exists = any(p['name'] == persona_name for p in built_in_personas)
        
        if not persona_exists:
            custom_persona = PersonaMode.query.filter_by(name=persona_name, is_custom=True).first()
            if not custom_persona:
                return jsonify({'error': 'Persona not found'}), 404
        
        # Send command to bot via Redis
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'activate_persona_global',
                    'persona_name': persona_name
                }))
            except Exception as e:
                print(f"Failed to send persona activation command: {e}")
                return jsonify({'error': 'Failed to activate persona'}), 500
        
        return jsonify({
            'success': True,
            'persona_name': persona_name,
            'message': f'Persona "{persona_name}" activated globally'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to activate persona: {str(e)}'}), 500

@personas_bp.route('/api/servers/<guild_id>/persona', methods=['GET', 'PUT'])
@require_discord_auth
def server_persona(guild_id):
    """Get or set persona for a specific server"""
    try:
        if not bot_instance:
            return jsonify({'error': 'Bot not connected'}), 503
        
        guild = bot_instance.get_guild(int(guild_id))
        if not guild:
            return jsonify({'error': 'Server not found'}), 404
        
        # Check admin permissions for PUT requests
        if request.method == 'PUT':
            user_id = getattr(request, 'user_id', None)
            if user_id:
                member = guild.get_member(int(user_id))
                if not member or not member.guild_permissions.administrator:
                    return jsonify({'error': 'Admin permissions required'}), 403
        
        if request.method == 'GET':
            config = ServerConfig.query.filter_by(guild_id=guild_id).first()
            current_persona = config.persona_mode if config else 'normal'
            
            # Get persona details
            persona_details = None
            built_in_personas = get_built_in_personas()
            for persona in built_in_personas:
                if persona['name'] == current_persona:
                    persona_details = persona
                    break
            
            if not persona_details:
                custom_persona = PersonaMode.query.filter_by(name=current_persona, is_custom=True).first()
                if custom_persona:
                    persona_details = custom_persona.to_dict()
            
            return jsonify({
                'current_persona': current_persona,
                'persona_details': persona_details
            })
        
        elif request.method == 'PUT':
            data = request.get_json()
            if not data or 'persona_name' not in data:
                return jsonify({'error': 'Persona name required'}), 400
            
            persona_name = data['persona_name']
            
            # Verify persona exists
            built_in_personas = get_built_in_personas()
            persona_exists = any(p['name'] == persona_name for p in built_in_personas)
            
            if not persona_exists:
                custom_persona = PersonaMode.query.filter_by(name=persona_name, is_custom=True).first()
                if not custom_persona:
                    return jsonify({'error': 'Persona not found'}), 404
            
            # Update server configuration
            config = ServerConfig.query.filter_by(guild_id=guild_id).first()
            if not config:
                config = ServerConfig(
                    guild_id=guild_id,
                    guild_name=guild.name
                )
                db.session.add(config)
            
            config.persona_mode = persona_name
            config.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Notify bot via Redis
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'set_server_persona',
                        'guild_id': guild_id,
                        'persona_name': persona_name
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of persona change: {e}")
            
            return jsonify({
                'success': True,
                'guild_id': guild_id,
                'persona_name': persona_name,
                'message': f'Persona set to "{persona_name}" for server'
            })
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage server persona: {str(e)}'}), 500

@personas_bp.route('/api/personas/usage', methods=['GET'])
@require_discord_auth
def get_persona_usage():
    """Get usage statistics for all personas"""
    try:
        # Get usage from server configurations
        usage_stats = {}
        
        # Built-in personas
        for persona in get_built_in_personas():
            usage_stats[persona['name']] = {
                'name': persona['name'],
                'display_name': persona['display_name'],
                'is_custom': False,
                'server_count': 0,
                'servers': []
            }
        
        # Custom personas
        custom_personas = PersonaMode.query.filter_by(is_custom=True).all()
        for persona in custom_personas:
            usage_stats[persona.name] = {
                'name': persona.name,
                'display_name': persona.display_name,
                'is_custom': True,
                'server_count': 0,
                'servers': []
            }
        
        # Count usage in server configs
        server_configs = ServerConfig.query.all()
        for config in server_configs:
            if config.persona_mode in usage_stats:
                usage_stats[config.persona_mode]['server_count'] += 1
                usage_stats[config.persona_mode]['servers'].append({
                    'guild_id': config.guild_id,
                    'guild_name': config.guild_name
                })
        
        # Convert to list and sort by usage
        usage_list = list(usage_stats.values())
        usage_list.sort(key=lambda x: x['server_count'], reverse=True)
        
        return jsonify({
            'usage_stats': usage_list,
            'total_personas': len(usage_list),
            'total_active': len([p for p in usage_list if p['server_count'] > 0])
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get persona usage: {str(e)}'}), 500
