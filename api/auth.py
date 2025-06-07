"""
Authentication system for Yumi Bot API
Handles API token validation and user authentication.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import request, jsonify, current_app
import os

TOKEN_FILE = os.path.join(os.path.dirname(__file__), 'api_tokens.json')

class TokenValidator:
    """Validates API tokens"""
    
    def __init__(self, token_file=TOKEN_FILE):
        self.token_file = Path(token_file)
        self._tokens_cache = None
        self._cache_time = None
    
    def _load_tokens(self):
        """Load tokens with caching"""
        try:
            if not self.token_file.exists():
                return {}
            
            # Cache tokens for 60 seconds to avoid excessive file I/O
            current_time = datetime.utcnow()
            if (self._tokens_cache is None or 
                self._cache_time is None or 
                (current_time - self._cache_time).seconds > 60):
                
                with open(self.token_file, 'r') as f:
                    self._tokens_cache = json.load(f)
                self._cache_time = current_time
            
            return self._tokens_cache
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _hash_token(self, token):
        """Hash a token for lookup"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def validate_token(self, raw_token):
        """
        Validate a token and return its info
        
        Args:
            raw_token (str): The raw token to validate
        
        Returns:
            dict: Token info if valid, None if invalid
        """
        if not raw_token:
            return None
        
        tokens = self._load_tokens()
        token_hash = self._hash_token(raw_token)
        
        if token_hash not in tokens:
            return None
        
        info = tokens[token_hash]
        
        # Check if token is active
        if not info.get('active', True):
            return None
        
        # Check expiry
        if info.get('expires_at'):
            try:
                expires_at = datetime.fromisoformat(info['expires_at'])
                if datetime.utcnow() > expires_at:
                    return None
            except (ValueError, TypeError):
                # Invalid date format, treat as expired
                return None
        
        # Update usage statistics (async to avoid file locking issues)
        self._update_token_usage(token_hash)
        
        return info
    
    def _update_token_usage(self, token_hash):
        """Update token usage statistics"""
        try:
            # Re-read fresh data for updates
            with open(self.token_file, 'r') as f:
                tokens = json.load(f)
            
            if token_hash in tokens:
                tokens[token_hash]['last_used'] = datetime.utcnow().isoformat()
                tokens[token_hash]['usage_count'] = tokens[token_hash].get('usage_count', 0) + 1
                
                with open(self.token_file, 'w') as f:
                    json.dump(tokens, f, indent=2, default=str)
                
                # Invalidate cache
                self._tokens_cache = None
        except Exception:
            # Silently fail usage updates to avoid breaking API calls
            pass

# Global validator instance
token_validator = TokenValidator()

def require_api_token(permissions=None):
    """
    Decorator to require API token authentication
    
    Args:
        permissions (list): Required permissions (optional)
    """
    if permissions is None:
        permissions = []
    
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Get token from various sources
            token = None
            
            # Check Authorization header (Bearer token)
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
            
            # Check X-API-Token header
            if not token:
                token = request.headers.get('X-API-Token')
            
            # Check X-API-Key header (legacy)
            if not token:
                token = request.headers.get('X-API-Key')
            
            # Check query parameter
            if not token:
                token = request.args.get('api_token') or request.args.get('api_key')
            
            if not token:
                return jsonify({
                    'error': 'API token required',
                    'message': 'Include token in Authorization header (Bearer), X-API-Token header, or api_token query parameter'
                }), 401
            
            # Validate token
            token_info = token_validator.validate_token(token)
            if not token_info:
                return jsonify({
                    'error': 'Invalid or expired API token',
                    'message': 'Please check your token and ensure it has not expired'
                }), 401
            
            # Check permissions
            token_permissions = token_info.get('permissions', [])
            for required_permission in permissions:
                if required_permission not in token_permissions:
                    return jsonify({
                        'error': 'Insufficient permissions',
                        'message': f'Token requires {required_permission} permission',
                        'required': permissions,
                        'available': token_permissions
                    }), 403
            
            # Add token info to request for use in endpoint
            request.token_info = token_info
            request.token_name = token_info.get('name', 'Unknown')
            request.token_permissions = token_permissions
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def require_admin_token(f):
    """Decorator to require admin-level API token"""
    @require_api_token(permissions=['admin'])
    @wraps(f)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated

def require_read_token(f):
    """Decorator to require read permission"""
    @require_api_token(permissions=['read'])
    @wraps(f)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated

def require_write_token(f):
    """Decorator to require write permission"""
    @require_api_token(permissions=['write'])
    @wraps(f)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated

# Legacy support for existing API key decorator
def require_api_key(f):
    """Legacy API key support - redirects to token auth"""
    return require_api_token()(f)
