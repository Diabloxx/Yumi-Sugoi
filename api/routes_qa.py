"""
Q&A learning system API routes for Yumi Sugoi Discord Bot Dashboard

Provides endpoints for managing the bot's question-answer learning system,
including training data, responses, and knowledge base management.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
from sqlalchemy import or_, and_, func

from .app import (
    bot_instance, db, redis_client,
    require_api_key, require_discord_auth, require_admin,
    QAPair, User
)

qa_bp = Blueprint('qa', __name__)

def calculate_similarity(question1: str, question2: str) -> float:
    """Calculate simple similarity between two questions"""
    # Simple word-based similarity (could be improved with NLP)
    words1 = set(question1.lower().split())
    words2 = set(question2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)

@qa_bp.route('/api/qa/pairs', methods=['GET'])
@require_discord_auth
def get_qa_pairs():
    """Get Q&A pairs with filtering and pagination"""
    try:
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Filters
        category = request.args.get('category')
        search = request.args.get('search', '').lower()
        min_confidence = request.args.get('min_confidence', type=float)
        sort_by = request.args.get('sort_by', 'created_at')  # created_at, confidence, usage_count
        order = request.args.get('order', 'desc')
        
        # Build query
        query = QAPair.query
        
        if category:
            query = query.filter(QAPair.category == category)
        
        if search:
            query = query.filter(
                or_(
                    QAPair.question.ilike(f'%{search}%'),
                    QAPair.answer.ilike(f'%{search}%')
                )
            )
        
        if min_confidence is not None:
            query = query.filter(QAPair.confidence >= min_confidence)
        
        # Apply sorting
        if sort_by == 'confidence':
            order_col = QAPair.confidence.desc() if order == 'desc' else QAPair.confidence.asc()
        elif sort_by == 'usage_count':
            order_col = QAPair.usage_count.desc() if order == 'desc' else QAPair.usage_count.asc()
        elif sort_by == 'updated_at':
            order_col = QAPair.updated_at.desc() if order == 'desc' else QAPair.updated_at.asc()
        else:  # created_at
            order_col = QAPair.created_at.desc() if order == 'desc' else QAPair.created_at.asc()
        
        query = query.order_by(order_col)
        
        # Paginate
        paginated = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        qa_pairs = [pair.to_dict() for pair in paginated.items]
        
        # Get categories for filtering
        categories = db.session.query(QAPair.category, func.count(QAPair.id)).group_by(QAPair.category).all()
        category_stats = {cat: count for cat, count in categories if cat}
        
        return jsonify({
            'qa_pairs': qa_pairs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated.total,
                'pages': paginated.pages,
                'has_next': paginated.has_next,
                'has_prev': paginated.has_prev
            },
            'filters': {
                'category': category,
                'search': search,
                'min_confidence': min_confidence,
                'sort_by': sort_by,
                'order': order
            },
            'categories': category_stats
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get Q&A pairs: {str(e)}'}), 500

@qa_bp.route('/api/qa/pairs', methods=['POST'])
@require_discord_auth
def create_qa_pair():
    """Create a new Q&A pair"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if 'question' not in data or 'answer' not in data:
            return jsonify({'error': 'Question and answer are required'}), 400
        
        question = data['question'].strip()
        answer = data['answer'].strip()
        
        if not question or not answer:
            return jsonify({'error': 'Question and answer cannot be empty'}), 400
        
        # Check for similar existing questions
        existing_pairs = QAPair.query.all()
        similar_pairs = []
        
        for pair in existing_pairs:
            similarity = calculate_similarity(question, pair.question)
            if similarity > 0.7:  # High similarity threshold
                similar_pairs.append({
                    'id': pair.id,
                    'question': pair.question,
                    'similarity': similarity
                })
        
        if similar_pairs:
            return jsonify({
                'error': 'Similar questions already exist',
                'similar_pairs': similar_pairs,
                'suggestion': 'Consider updating an existing Q&A pair instead'
            }), 409
        
        # Create new Q&A pair
        qa_pair = QAPair(
            question=question,
            answer=answer,
            category=data.get('category', 'general'),
            confidence=min(max(data.get('confidence', 1.0), 0.0), 1.0),
            created_by=getattr(request, 'user_id', None)
        )
        
        db.session.add(qa_pair)
        db.session.commit()
        
        # Notify bot of new Q&A pair via Redis
        if redis_client:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'qa_pair_added',
                    'qa_pair': qa_pair.to_dict()
                }))
            except Exception as e:
                print(f"Failed to notify bot of new Q&A pair: {e}")
        
        return jsonify(qa_pair.to_dict()), 201
    
    except Exception as e:
        return jsonify({'error': f'Failed to create Q&A pair: {str(e)}'}), 500

@qa_bp.route('/api/qa/pairs/<int:pair_id>', methods=['GET', 'PUT', 'DELETE'])
@require_discord_auth
def manage_qa_pair(pair_id):
    """Get, update, or delete a specific Q&A pair"""
    try:
        qa_pair = QAPair.query.get(pair_id)
        if not qa_pair:
            return jsonify({'error': 'Q&A pair not found'}), 404
        
        if request.method == 'GET':
            return jsonify(qa_pair.to_dict())
        
        elif request.method == 'PUT':
            # Check permissions (creator or admin can edit)
            user_id = getattr(request, 'user_id', None)
            if qa_pair.created_by != user_id and not getattr(request, 'is_admin', False):
                return jsonify({'error': 'Permission denied'}), 403
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Update fields
            if 'question' in data:
                qa_pair.question = data['question'].strip()
            if 'answer' in data:
                qa_pair.answer = data['answer'].strip()
            if 'category' in data:
                qa_pair.category = data['category']
            if 'confidence' in data:
                qa_pair.confidence = min(max(data['confidence'], 0.0), 1.0)
            
            qa_pair.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Notify bot of update
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'qa_pair_updated',
                        'qa_pair': qa_pair.to_dict()
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of Q&A pair update: {e}")
            
            return jsonify(qa_pair.to_dict())
        
        elif request.method == 'DELETE':
            # Check permissions
            user_id = getattr(request, 'user_id', None)
            if qa_pair.created_by != user_id and not getattr(request, 'is_admin', False):
                return jsonify({'error': 'Permission denied'}), 403
            
            pair_data = qa_pair.to_dict()
            db.session.delete(qa_pair)
            db.session.commit()
            
            # Notify bot of deletion
            if redis_client:
                try:
                    redis_client.publish('bot_commands', json.dumps({
                        'type': 'qa_pair_deleted',
                        'pair_id': pair_id,
                        'question': pair_data['question']
                    }))
                except Exception as e:
                    print(f"Failed to notify bot of Q&A pair deletion: {e}")
            
            return jsonify({'success': True, 'message': 'Q&A pair deleted'})
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage Q&A pair: {str(e)}'}), 500

@qa_bp.route('/api/qa/search', methods=['POST'])
@require_discord_auth
def search_qa_pairs():
    """Search for Q&A pairs similar to a given question"""
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'error': 'Question required for search'}), 400
        
        search_question = data['question'].strip().lower()
        limit = min(data.get('limit', 10), 50)
        min_similarity = data.get('min_similarity', 0.3)
        
        # Get all Q&A pairs
        all_pairs = QAPair.query.all()
        
        # Calculate similarities
        matches = []
        for pair in all_pairs:
            similarity = calculate_similarity(search_question, pair.question)
            if similarity >= min_similarity:
                pair_data = pair.to_dict()
                pair_data['similarity'] = similarity
                matches.append(pair_data)
        
        # Sort by similarity (descending) and confidence
        matches.sort(key=lambda x: (x['similarity'], x['confidence']), reverse=True)
        
        # Limit results
        matches = matches[:limit]
        
        return jsonify({
            'matches': matches,
            'search_question': data['question'],
            'total_matches': len(matches),
            'parameters': {
                'min_similarity': min_similarity,
                'limit': limit
            }
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to search Q&A pairs: {str(e)}'}), 500

@qa_bp.route('/api/qa/train', methods=['POST'])
@require_discord_auth
@require_admin
def bulk_train_qa():
    """Bulk upload Q&A pairs for training"""
    try:
        data = request.get_json()
        if not data or 'qa_pairs' not in data:
            return jsonify({'error': 'Q&A pairs data required'}), 400
        
        qa_data = data['qa_pairs']
        if not isinstance(qa_data, list):
            return jsonify({'error': 'Q&A pairs must be a list'}), 400
        
        results = {
            'created': 0,
            'skipped': 0,
            'errors': [],
            'created_pairs': []
        }
        
        for i, pair_data in enumerate(qa_data):
            try:
                if not isinstance(pair_data, dict) or 'question' not in pair_data or 'answer' not in pair_data:
                    results['errors'].append(f"Item {i}: Missing question or answer")
                    continue
                
                question = pair_data['question'].strip()
                answer = pair_data['answer'].strip()
                
                if not question or not answer:
                    results['errors'].append(f"Item {i}: Empty question or answer")
                    continue
                
                # Check for existing similar question
                existing = QAPair.query.filter(QAPair.question.ilike(f'%{question}%')).first()
                if existing:
                    results['skipped'] += 1
                    continue
                
                # Create Q&A pair
                qa_pair = QAPair(
                    question=question,
                    answer=answer,
                    category=pair_data.get('category', 'training'),
                    confidence=min(max(pair_data.get('confidence', 0.8), 0.0), 1.0),
                    created_by=getattr(request, 'user_id', None)
                )
                
                db.session.add(qa_pair)
                results['created'] += 1
                results['created_pairs'].append({
                    'question': question,
                    'category': qa_pair.category
                })
            
            except Exception as e:
                results['errors'].append(f"Item {i}: {str(e)}")
        
        db.session.commit()
        
        # Notify bot of bulk training
        if redis_client and results['created'] > 0:
            try:
                redis_client.publish('bot_commands', json.dumps({
                    'type': 'qa_bulk_training',
                    'created_count': results['created'],
                    'total_pairs': QAPair.query.count()
                }))
            except Exception as e:
                print(f"Failed to notify bot of bulk training: {e}")
        
        return jsonify({
            'success': True,
            'results': results,
            'message': f"Training completed: {results['created']} pairs created, {results['skipped']} skipped"
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to bulk train Q&A: {str(e)}'}), 500

@qa_bp.route('/api/qa/categories', methods=['GET', 'POST'])
@require_discord_auth
def manage_qa_categories():
    """Get available categories or suggest new ones"""
    try:
        if request.method == 'GET':
            # Get categories with counts and stats
            categories = db.session.query(
                QAPair.category,
                func.count(QAPair.id).label('count'),
                func.avg(QAPair.confidence).label('avg_confidence'),
                func.sum(QAPair.usage_count).label('total_usage')
            ).group_by(QAPair.category).all()
            
            category_stats = []
            for cat, count, avg_conf, total_usage in categories:
                if cat:  # Skip None categories
                    category_stats.append({
                        'name': cat,
                        'count': count,
                        'avg_confidence': round(float(avg_conf or 0), 2),
                        'total_usage': int(total_usage or 0)
                    })
            
            # Sort by count descending
            category_stats.sort(key=lambda x: x['count'], reverse=True)
            
            return jsonify({
                'categories': category_stats,
                'total_categories': len(category_stats),
                'total_pairs': sum(cat['count'] for cat in category_stats)
            })
        
        elif request.method == 'POST':
            # This would be for creating/managing categories
            # For now, categories are implicit based on Q&A pair creation
            return jsonify({
                'message': 'Categories are automatically created when Q&A pairs are added',
                'note': 'Use the category field when creating Q&A pairs'
            })
    
    except Exception as e:
        return jsonify({'error': f'Failed to manage categories: {str(e)}'}), 500

@qa_bp.route('/api/qa/analytics', methods=['GET'])
@require_discord_auth
def get_qa_analytics():
    """Get Q&A system analytics and performance metrics"""
    try:
        # Time range for analytics
        days = request.args.get('days', 30, type=int)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Basic statistics
        total_pairs = QAPair.query.count()
        recent_pairs = QAPair.query.filter(QAPair.created_at >= start_date).count()
        
        # Usage statistics
        top_used = QAPair.query.order_by(QAPair.usage_count.desc()).limit(10).all()
        
        # Confidence distribution
        confidence_ranges = {
            'high': QAPair.query.filter(QAPair.confidence >= 0.8).count(),
            'medium': QAPair.query.filter(and_(QAPair.confidence >= 0.5, QAPair.confidence < 0.8)).count(),
            'low': QAPair.query.filter(QAPair.confidence < 0.5).count()
        }
        
        # Category distribution
        category_counts = db.session.query(
            QAPair.category,
            func.count(QAPair.id)
        ).group_by(QAPair.category).all()
        
        categories = {cat: count for cat, count in category_counts if cat}
        
        # Recent activity
        recent_activity = QAPair.query.filter(
            QAPair.created_at >= start_date
        ).order_by(QAPair.created_at.desc()).limit(20).all()
        
        activity_timeline = []
        for pair in recent_activity:
            activity_timeline.append({
                'date': pair.created_at.isoformat(),
                'question': pair.question[:100] + '...' if len(pair.question) > 100 else pair.question,
                'category': pair.category,
                'confidence': pair.confidence
            })
        
        analytics = {
            'time_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            },
            'overview': {
                'total_pairs': total_pairs,
                'recent_pairs': recent_pairs,
                'total_usage': sum(pair.usage_count for pair in QAPair.query.all()),
                'avg_confidence': float(db.session.query(func.avg(QAPair.confidence)).scalar() or 0)
            },
            'top_used_pairs': [
                {
                    'id': pair.id,
                    'question': pair.question[:100] + '...' if len(pair.question) > 100 else pair.question,
                    'usage_count': pair.usage_count,
                    'confidence': pair.confidence,
                    'category': pair.category
                }
                for pair in top_used
            ],
            'confidence_distribution': confidence_ranges,
            'category_distribution': categories,
            'recent_activity': activity_timeline
        }
        
        return jsonify(analytics)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get Q&A analytics: {str(e)}'}), 500

@qa_bp.route('/api/qa/export', methods=['POST'])
@require_discord_auth
@require_admin
def export_qa_data():
    """Export Q&A data for backup or analysis"""
    try:
        data = request.get_json() or {}
        format_type = data.get('format', 'json')  # json, csv
        category = data.get('category')
        min_confidence = data.get('min_confidence')
        
        # Build query with filters
        query = QAPair.query
        
        if category:
            query = query.filter(QAPair.category == category)
        if min_confidence is not None:
            query = query.filter(QAPair.confidence >= min_confidence)
        
        qa_pairs = query.all()
        
        if format_type == 'json':
            export_data = {
                'export_info': {
                    'exported_at': datetime.utcnow().isoformat(),
                    'total_pairs': len(qa_pairs),
                    'filters': {
                        'category': category,
                        'min_confidence': min_confidence
                    }
                },
                'qa_pairs': [pair.to_dict() for pair in qa_pairs]
            }
            
            return jsonify({
                'success': True,
                'format': 'json',
                'data': export_data,
                'filename': f'yumi_qa_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
            })
        
        elif format_type == 'csv':
            # For CSV, we'd return the data in a format suitable for CSV conversion
            csv_data = []
            for pair in qa_pairs:
                csv_data.append({
                    'id': pair.id,
                    'question': pair.question,
                    'answer': pair.answer,
                    'category': pair.category,
                    'confidence': pair.confidence,
                    'usage_count': pair.usage_count,
                    'created_at': pair.created_at.isoformat(),
                    'created_by': pair.created_by
                })
            
            return jsonify({
                'success': True,
                'format': 'csv',
                'data': csv_data,
                'filename': f'yumi_qa_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
            })
        
        else:
            return jsonify({'error': 'Unsupported format. Use "json" or "csv"'}), 400
    
    except Exception as e:
        return jsonify({'error': f'Failed to export Q&A data: {str(e)}'}), 500
