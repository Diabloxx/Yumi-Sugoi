#!/usr/bin/env python3
"""
API Token Generator for Yumi Bot API
Generates secure API tokens for accessing the Yumi Bot API endpoints.
"""

import secrets
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import argparse

# Configuration
TOKEN_FILE = os.path.join(os.path.dirname(__file__), 'api', 'api_tokens.json')
TOKEN_LENGTH = 64  # Length of the raw token
DEFAULT_EXPIRY_DAYS = 365  # Default token expiry

class APITokenManager:
    """Manages API tokens for the Yumi Bot API"""
    
    def __init__(self, token_file=TOKEN_FILE):
        self.token_file = Path(token_file)
        self.tokens = self._load_tokens()
    
    def _load_tokens(self):
        """Load existing tokens from file"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}
    
    def _save_tokens(self):
        """Save tokens to file"""
        # Ensure directory exists
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.token_file, 'w') as f:
            json.dump(self.tokens, f, indent=2, default=str)
    
    def _generate_token(self):
        """Generate a cryptographically secure token"""
        return secrets.token_urlsafe(TOKEN_LENGTH)
    
    def _hash_token(self, token):
        """Hash a token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def create_token(self, name, description="", expiry_days=DEFAULT_EXPIRY_DAYS, permissions=None):
        """
        Create a new API token
        
        Args:
            name (str): Human-readable name for the token
            description (str): Optional description
            expiry_days (int): Number of days until expiry (0 = never expires)
            permissions (list): List of permissions (future use)
        
        Returns:
            dict: Token information including the raw token
        """
        if permissions is None:
            permissions = ["read", "write", "admin"]
        
        # Generate token
        raw_token = self._generate_token()
        token_hash = self._hash_token(raw_token)
        
        # Calculate expiry
        created_at = datetime.utcnow()
        expires_at = None if expiry_days == 0 else created_at + timedelta(days=expiry_days)
        
        # Store token info (never store raw token)
        token_info = {
            'name': name,
            'description': description,
            'created_at': created_at.isoformat(),
            'expires_at': expires_at.isoformat() if expires_at else None,
            'permissions': permissions,
            'last_used': None,
            'usage_count': 0,
            'active': True
        }
        
        self.tokens[token_hash] = token_info
        self._save_tokens()
        
        print(f"✅ API Token created successfully!")
        print(f"📝 Name: {name}")
        print(f"📅 Created: {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏰ Expires: {'Never' if expires_at is None else expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔑 Token: {raw_token}")
        print(f"\n⚠️  IMPORTANT: Save this token now! It won't be shown again.")
        print(f"💡 Usage: Include in API requests as 'X-API-Token: {raw_token}'")
        
        return {
            'token': raw_token,
            'hash': token_hash,
            'info': token_info
        }
    
    def list_tokens(self):
        """List all tokens (without raw values)"""
        if not self.tokens:
            print("📋 No API tokens found.")
            return
        
        print("📋 API Tokens:")
        print("-" * 80)
        
        for token_hash, info in self.tokens.items():
            status = "🟢 Active" if info['active'] else "🔴 Inactive"
            expires = "Never" if info['expires_at'] is None else info['expires_at']
            last_used = info['last_used'] or "Never"
            
            print(f"Name: {info['name']}")
            print(f"Description: {info['description']}")
            print(f"Status: {status}")
            print(f"Created: {info['created_at']}")
            print(f"Expires: {expires}")
            print(f"Last Used: {last_used}")
            print(f"Usage Count: {info['usage_count']}")
            print(f"Permissions: {', '.join(info['permissions'])}")
            print(f"Hash: {token_hash[:16]}...")
            print("-" * 80)
    
    def revoke_token(self, token_hash_prefix):
        """Revoke a token by hash prefix"""
        matches = [h for h in self.tokens.keys() if h.startswith(token_hash_prefix)]
        
        if not matches:
            print(f"❌ No token found with hash prefix: {token_hash_prefix}")
            return False
        
        if len(matches) > 1:
            print(f"❌ Multiple tokens match prefix: {token_hash_prefix}")
            print("Please provide a longer prefix to uniquely identify the token.")
            return False
        
        token_hash = matches[0]
        token_info = self.tokens[token_hash]
        
        # Mark as inactive instead of deleting (for audit trail)
        self.tokens[token_hash]['active'] = False
        self.tokens[token_hash]['revoked_at'] = datetime.utcnow().isoformat()
        self._save_tokens()
        
        print(f"✅ Token '{token_info['name']}' has been revoked.")
        return True
    
    def cleanup_expired(self):
        """Remove expired tokens"""
        now = datetime.utcnow()
        expired_count = 0
        
        for token_hash, info in list(self.tokens.items()):
            if info['expires_at'] and datetime.fromisoformat(info['expires_at']) < now:
                del self.tokens[token_hash]
                expired_count += 1
        
        if expired_count > 0:
            self._save_tokens()
            print(f"🧹 Cleaned up {expired_count} expired tokens.")
        else:
            print("✨ No expired tokens found.")
    
    def validate_token(self, raw_token):
        """
        Validate a token and return its info
        
        Args:
            raw_token (str): The raw token to validate
        
        Returns:
            dict: Token info if valid, None if invalid
        """
        token_hash = self._hash_token(raw_token)
        
        if token_hash not in self.tokens:
            return None
        
        info = self.tokens[token_hash]
        
        # Check if token is active
        if not info['active']:
            return None
        
        # Check expiry
        if info['expires_at']:
            expires_at = datetime.fromisoformat(info['expires_at'])
            if datetime.utcnow() > expires_at:
                return None
        
        # Update usage statistics
        self.tokens[token_hash]['last_used'] = datetime.utcnow().isoformat()
        self.tokens[token_hash]['usage_count'] += 1
        self._save_tokens()
        
        return info


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Yumi Bot API Token Manager")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create token command
    create_parser = subparsers.add_parser('create', help='Create a new API token')
    create_parser.add_argument('name', help='Name for the token')
    create_parser.add_argument('--description', '-d', default='', help='Description for the token')
    create_parser.add_argument('--expires', '-e', type=int, default=DEFAULT_EXPIRY_DAYS, 
                             help=f'Expiry in days (0 = never expires, default: {DEFAULT_EXPIRY_DAYS})')
    create_parser.add_argument('--permissions', '-p', nargs='+', default=['read', 'write', 'admin'],
                             help='Permissions for the token (default: read write admin)')
    
    # List tokens command
    list_parser = subparsers.add_parser('list', help='List all tokens')
    
    # Revoke token command
    revoke_parser = subparsers.add_parser('revoke', help='Revoke a token')
    revoke_parser.add_argument('hash_prefix', help='Hash prefix of the token to revoke')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove expired tokens')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = APITokenManager()
    
    if args.command == 'create':
        manager.create_token(
            name=args.name,
            description=args.description,
            expiry_days=args.expires,
            permissions=args.permissions
        )
    
    elif args.command == 'list':
        manager.list_tokens()
    
    elif args.command == 'revoke':
        manager.revoke_token(args.hash_prefix)
    
    elif args.command == 'cleanup':
        manager.cleanup_expired()


if __name__ == '__main__':
    main()
