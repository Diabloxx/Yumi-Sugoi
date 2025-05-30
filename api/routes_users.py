"""
User memory management API routes for Yumi Sugoi Discord Bot Dashboard

Provides endpoints for managing user memories, preferences, and interaction data.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional

from .app import (
    bot_instance, db, redis_client,
    require_api_key, require_discord_auth,
    User
)

users_bp = Blueprint('users', __name__)

def format_user_memory(memory_data: dict) -> dict:
    """Format user memory data for API response"""
    if not memory_data:
        return {}
    
    return {
        'facts': memory_data.get('facts', []),
        'preferences': memory_data.get('preferences', {}),
        'interactions': memory_data.get('interactions', []),
        'personality_traits': memory_data.get('personality_traits', {}),
        'conversation_context': memory_data.get('conversation_context', {}),
        'last_updated': memory_data.get('last_updated'),
        'memory_strength': memory_data.get('memory_strength', 1.0)
    }

@users_bp.route('/api/users/me', methods=['GET'])
@require_discord_auth
def get_current_user():
    """Get current user's information and memory"""
    try:
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'User ID not found in token'}), 401
        
        user = User.query.filter_by(discord_id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user.to_dict()
        user_data['memory'] = format_user_memory(
            json.loads(user.memory_data) if user.memory_data else {}
        )
        
        # Add interaction statistics
        memory_data = json.loads(user.memory_data) if user.memory_data else {}
        interactions = memory_data.get('interactions', [])
        
        user_data['stats'] = {
            'total_interactions': len(interactions),
            'facts_learned': len(memory_data.get('facts', [])),
            'last_interaction': interactions[-1].get('timestamp') if interactions else None,
            'memory_size_kb': len(user.memory_data) / 1024 if user.memory_data else 0
        }
        
        return jsonify(user_data)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get user data: {str(e)}'}), 500

@users_bp.route('/api/users/me/memory', methods=['GET', 'PUT'])
@require_discord_auth
def manage_user_memory():
    """Get or update current user's memory data"""
    try:
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'User ID not found in token'}), 401
        
        user = User.query.filter_by(discord_id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if request.method == 'GET':
            memory_data = json.loads(user.memory_data) if user.memory_data else {}
            return jsonify({
                'memory': format_user_memory(memory_data),
                'raw_memory': memory_data  # Include raw data for debugging
            })
        
        elif request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Get current memory
            current_memory = json.loads(user.memory_data) if user.memory_data else {}
            
            # Update specific fields
            if 'facts' in data:
                current_memory['facts'] = data['facts']
            if 'preferences' in data:
                current_memory['preferences'] = data['preferences']
            if 'personality_traits' in data:
                current_memory['personality_traits'] = data['personality_traits']
            
            # Update metadata
            current_memory['last_updated'] = datetime.utcnow().isoformat()
            current_memory['updated_via'] = 'dashboard'
            
            user.memory_data = json.dumps(current_memory)
            user.last_active = datetime.utcnow()
            db.session.commit()
            
            # Notify bot of memory update via Redis
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'user_memory_updated',
                        'user_id': user_id,
                        'updated_fields': list(data.keys())
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of memory update: {e}")
            
            return jsonify({
                'success': True,
                'memory': format_user_memory(current_memory)
            })
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage user memory: {str(e)}'}), 500

@users_bp.route('/api/users/me/memory/facts', methods=['GET', 'POST', 'DELETE'])
@require_discord_auth
def manage_user_facts():
    """Manage user facts"""
    try:
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'User ID not found in token'}), 401
        
        user = User.query.filter_by(discord_id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        memory_data = json.loads(user.memory_data) if user.memory_data else {}
        facts = memory_data.get('facts', [])
        
        if request.method == 'GET':
            # Filter and sort facts
            category = request.args.get('category')
            search = request.args.get('search', '').lower()
            
            filtered_facts = facts
            if category:
                filtered_facts = [f for f in facts if f.get('category') == category]
            if search:
                filtered_facts = [f for f in filtered_facts 
                                if search in f.get('content', '').lower()]
            
            # Group by category
            categories = {}
            for fact in filtered_facts:
                cat = fact.get('category', 'general')
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(fact)
            
            return jsonify({
                'facts': filtered_facts,
                'categories': categories,
                'total_count': len(facts),
                'filtered_count': len(filtered_facts)
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            if not data or 'content' not in data:
                return jsonify({'error': 'Fact content required'}), 400
            
            new_fact = {
                'id': len(facts) + 1,
                'content': data['content'],
                'category': data.get('category', 'general'),
                'confidence': data.get('confidence', 1.0),
                'source': 'dashboard',
                'created_at': datetime.utcnow().isoformat(),
                'tags': data.get('tags', [])
            }
            
            facts.append(new_fact)
            memory_data['facts'] = facts
            memory_data['last_updated'] = datetime.utcnow().isoformat()
            
            user.memory_data = json.dumps(memory_data)
            user.last_active = datetime.utcnow()
            db.session.commit()
            
            # Notify bot
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'user_fact_added',
                        'user_id': user_id,
                        'fact': new_fact
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of new fact: {e}")
            
            return jsonify({
                'success': True,
                'fact': new_fact,
                'total_facts': len(facts)
            }), 201
        
        elif request.method == 'DELETE':
            fact_id = request.args.get('fact_id', type=int)
            if fact_id is None:
                return jsonify({'error': 'Fact ID required'}), 400
            
            # Find and remove fact
            original_count = len(facts)
            facts = [f for f in facts if f.get('id') != fact_id]
            
            if len(facts) == original_count:
                return jsonify({'error': 'Fact not found'}), 404
            
            memory_data['facts'] = facts
            memory_data['last_updated'] = datetime.utcnow().isoformat()
            
            user.memory_data = json.dumps(memory_data)
            db.session.commit()
            
            # Notify bot
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'user_fact_deleted',
                        'user_id': user_id,
                        'fact_id': fact_id
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of fact deletion: {e}")
            
            return jsonify({
                'success': True,
                'deleted_fact_id': fact_id,
                'remaining_facts': len(facts)
            })
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage user facts: {str(e)}'}), 500

@users_bp.route('/api/users/me/preferences', methods=['GET', 'PUT'])
@require_discord_auth
def manage_user_preferences():
    """Get or update user preferences"""
    try:
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'User ID not found in token'}), 401
        
        user = User.query.filter_by(discord_id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if request.method == 'GET':
            preferences = json.loads(user.preferences) if user.preferences else {}
            return jsonify({
                'preferences': preferences,
                'available_settings': {
                    'communication_style': ['formal', 'casual', 'friendly', 'professional'],
                    'response_length': ['short', 'medium', 'long'],
                    'topics_of_interest': ['technology', 'science', 'art', 'music', 'sports', 'gaming'],
                    'language_preference': ['english', 'japanese', 'mixed'],
                    'nsfw_content': [True, False],
                    'personality_mode': ['helpful', 'creative', 'analytical', 'playful']
                }
            })
        
        elif request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No preferences provided'}), 400
            
            # Validate preferences
            valid_preferences = [
                'communication_style', 'response_length', 'topics_of_interest',
                'language_preference', 'nsfw_content', 'personality_mode',
                'timezone', 'notification_settings'
            ]
            
            preferences = json.loads(user.preferences) if user.preferences else {}
            updated_fields = []
            
            for key, value in data.items():
                if key in valid_preferences:
                    preferences[key] = value
                    updated_fields.append(key)
            
            preferences['last_updated'] = datetime.utcnow().isoformat()
            preferences['updated_via'] = 'dashboard'
            
            user.preferences = json.dumps(preferences)
            user.last_active = datetime.utcnow()
            db.session.commit()
            
            # Notify bot
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'user_preferences_updated',
                        'user_id': user_id,
                        'updated_fields': updated_fields,
                        'preferences': preferences
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of preference update: {e}")
            
            return jsonify({
                'success': True,
                'preferences': preferences,
                'updated_fields': updated_fields
            })
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage user preferences: {str(e)}'}), 500

@users_bp.route('/api/users/me/interactions', methods=['GET'])
@require_discord_auth
def get_user_interactions():
    """Get user's interaction history"""
    try:
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'User ID not found in token'}), 401
        
        user = User.query.filter_by(discord_id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        memory_data = json.loads(user.memory_data) if user.memory_data else {}
        interactions = memory_data.get('interactions', [])
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Filter by date range
        days = request.args.get('days', type=int)
        if days:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            interactions = [
                i for i in interactions 
                if datetime.fromisoformat(i.get('timestamp', '')) >= cutoff_date
            ]
        
        # Sort by timestamp (newest first)
        interactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Paginate
        total = len(interactions)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_interactions = interactions[start:end]
        
        # Generate statistics
        stats = {
            'total_interactions': total,
            'interactions_today': len([
                i for i in interactions 
                if datetime.fromisoformat(i.get('timestamp', '')).date() == datetime.utcnow().date()
            ]),
            'most_active_channel': None,
            'favorite_commands': {},
            'conversation_topics': []
        }
        
        # Calculate most active channel
        channel_counts = {}
        command_counts = {}
        
        for interaction in interactions:
            channel_id = interaction.get('channel_id')
            if channel_id:
                channel_counts[channel_id] = channel_counts.get(channel_id, 0) + 1
            
            command = interaction.get('command')
            if command:
                command_counts[command] = command_counts.get(command, 0) + 1
        
        if channel_counts:
            stats['most_active_channel'] = max(channel_counts, key=channel_counts.get)
        
        stats['favorite_commands'] = dict(sorted(command_counts.items(), 
                                                key=lambda x: x[1], reverse=True)[:5])
        
        return jsonify({
            'interactions': paginated_interactions,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            },
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get user interactions: {str(e)}'}), 500

@users_bp.route('/api/users/me/export', methods=['POST'])
@require_discord_auth
def export_user_data():
    """Export user's data for download"""
    try:
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'User ID not found in token'}), 401
        
        user = User.query.filter_by(discord_id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Compile all user data
        export_data = {
            'user_info': user.to_dict(),
            'memory_data': json.loads(user.memory_data) if user.memory_data else {},
            'preferences': json.loads(user.preferences) if user.preferences else {},
            'export_metadata': {
                'exported_at': datetime.utcnow().isoformat(),
                'export_version': '1.0',
                'privacy_note': 'This export contains all your personal data stored by Yumi Bot.'
            }
        }
        
        # Remove sensitive fields if any
        if 'user_info' in export_data:
            export_data['user_info'].pop('id', None)  # Remove internal ID
        
        return jsonify({
            'success': True,
            'data': export_data,
            'download_filename': f'yumi_user_data_{user_id}_{datetime.utcnow().strftime("%Y%m%d")}.json'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to export user data: {str(e)}'}), 500

@users_bp.route('/api/users/me/delete', methods=['POST'])
@require_discord_auth
def delete_user_account():
    """Delete user account and all associated data"""
    try:
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'User ID not found in token'}), 401
        
        data = request.get_json()
        confirmation = data.get('confirmation') if data else None
        
        if confirmation != 'DELETE_MY_ACCOUNT':
            return jsonify({
                'error': 'Account deletion requires confirmation string "DELETE_MY_ACCOUNT"'
            }), 400
        
        user = User.query.filter_by(discord_id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Notify bot to clear user data
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'user_account_deleted',
                    'user_id': user_id,
                    'username': user.username
                }))
            except Exception as e:
                print(f"Failed to notify bot of account deletion: {e}")
        
        # Delete user from database
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Account successfully deleted',
            'note': 'All your data has been permanently removed from Yumi Bot.'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to delete account: {str(e)}'}), 500
