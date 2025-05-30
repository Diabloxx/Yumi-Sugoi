"""
Rate limiting and security middleware for Yumi Sugoi Discord Bot API

This module provides comprehensive rate limiting, security headers,
and protection against common web attacks.
"""

import os
import time
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, Tuple
from flask import request, jsonify, g, current_app
import redis
from werkzeug.exceptions import TooManyRequests

logger = logging.getLogger(__name__)

class RateLimiter:
    """Redis-based rate limiter with multiple strategies"""
    
    def __init__(self, redis_client, default_limit: int = 100, default_window: int = 3600):
        self.redis = redis_client
        self.default_limit = default_limit
        self.default_window = default_window
    
    def is_allowed(self, key: str, limit: int = None, window: int = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed under rate limit
        
        Returns:
            (allowed, info) where info contains limit details
        """
        limit = limit or self.default_limit
        window = window or self.default_window
        
        now = int(time.time())
        pipeline = self.redis.pipeline()
        
        # Sliding window log approach
        pipeline.zremrangebyscore(key, '-inf', now - window)
        pipeline.zcard(key)
        pipeline.zadd(key, {str(now): now})
        pipeline.expire(key, window)
        
        try:
            results = pipeline.execute()
            current_requests = results[1]
            
            # Calculate reset time
            reset_time = now + window
            
            info = {
                'limit': limit,
                'remaining': max(0, limit - current_requests - 1),
                'reset': reset_time,
                'retry_after': window if current_requests >= limit else 0
            }
            
            allowed = current_requests < limit
            
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for key: {key}",
                    extra={
                        'security': True,
                        'rate_limit': True,
                        'key': key,
                        'current_requests': current_requests,
                        'limit': limit
                    }
                )
            
            return allowed, info
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open - allow request if rate limiter is down
            return True, {
                'limit': limit,
                'remaining': limit,
                'reset': now + window,
                'retry_after': 0,
                'error': 'Rate limiter unavailable'
            }
    
    def reset_limit(self, key: str) -> bool:
        """Reset rate limit for a key"""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {key}: {e}")
            return False

def get_rate_limit_key(identifier: str, endpoint: str = None) -> str:
    """Generate rate limit key"""
    endpoint = endpoint or request.endpoint or 'unknown'
    return f"rate_limit:{identifier}:{endpoint}"

def rate_limit(limit: int = 100, window: int = 3600, per: str = 'ip', key_func=None):
    """
    Rate limiting decorator
    
    Args:
        limit: Number of requests allowed
        window: Time window in seconds
        per: Rate limit per 'ip', 'user', or 'api_key'
        key_func: Custom function to generate rate limit key
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not hasattr(current_app, 'rate_limiter'):
                # Rate limiter not configured, allow request
                return func(*args, **kwargs)
            
            # Generate rate limit key
            if key_func:
                key = key_func()
            elif per == 'ip':
                identifier = request.remote_addr
                key = get_rate_limit_key(identifier)
            elif per == 'user' and hasattr(g, 'current_user'):
                identifier = str(g.current_user.id)
                key = get_rate_limit_key(identifier)
            elif per == 'api_key' and hasattr(g, 'api_key'):
                identifier = hashlib.sha256(g.api_key.encode()).hexdigest()[:16]
                key = get_rate_limit_key(identifier)
            else:
                identifier = request.remote_addr
                key = get_rate_limit_key(identifier)
            
            # Check rate limit
            allowed, info = current_app.rate_limiter.is_allowed(key, limit, window)
            
            # Add rate limit headers
            response_headers = {
                'X-RateLimit-Limit': str(info['limit']),
                'X-RateLimit-Remaining': str(info['remaining']),
                'X-RateLimit-Reset': str(info['reset'])
            }
            
            if not allowed:
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Limit: {limit} per {window} seconds',
                    'retry_after': info['retry_after']
                })
                
                for header, value in response_headers.items():
                    response.headers[header] = value
                response.headers['Retry-After'] = str(info['retry_after'])
                
                return response, 429
            
            # Execute the original function
            response = func(*args, **kwargs)
            
            # Add rate limit headers to successful response
            if hasattr(response, 'headers'):
                for header, value in response_headers.items():
                    response.headers[header] = value
            
            return response
        
        return wrapper
    return decorator

class SecurityHeaders:
    """Security headers middleware"""
    
    @staticmethod
    def apply_headers(response):
        """Apply security headers to response"""
        headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' wss: https:; "
                "frame-ancestors 'none';"
            ),
            'Permissions-Policy': (
                "camera=(), microphone=(), geolocation=(), "
                "payment=(), usb=(), accelerometer=(), gyroscope=()"
            )
        }
        
        for header, value in headers.items():
            response.headers[header] = value
        
        return response

def validate_request_signature(secret_key: str, tolerance: int = 300):
    """
    Validate request signature for webhook security
    
    Args:
        secret_key: Secret key for HMAC validation
        tolerance: Allowed time difference in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get signature from headers
            signature = request.headers.get('X-Signature-256') or request.headers.get('X-Hub-Signature-256')
            timestamp = request.headers.get('X-Timestamp')
            
            if not signature or not timestamp:
                logger.warning(
                    "Missing signature or timestamp in webhook request",
                    extra={'security': True, 'webhook_validation': True}
                )
                return jsonify({'error': 'Missing signature or timestamp'}), 401
            
            try:
                # Validate timestamp
                request_time = int(timestamp)
                current_time = int(time.time())
                
                if abs(current_time - request_time) > tolerance:
                    logger.warning(
                        f"Webhook request timestamp too old: {current_time - request_time}s",
                        extra={'security': True, 'webhook_validation': True}
                    )
                    return jsonify({'error': 'Request timestamp too old'}), 401
                
                # Validate signature
                payload = request.get_data()
                expected_signature = hmac.new(
                    secret_key.encode(),
                    timestamp.encode() + payload,
                    hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(f"sha256={expected_signature}", signature):
                    logger.warning(
                        "Invalid webhook signature",
                        extra={'security': True, 'webhook_validation': True}
                    )
                    return jsonify({'error': 'Invalid signature'}), 401
                
                return func(*args, **kwargs)
                
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Webhook validation error: {e}",
                    extra={'security': True, 'webhook_validation': True}
                )
                return jsonify({'error': 'Invalid timestamp format'}), 400
        
        return wrapper
    return decorator

class IPWhitelist:
    """IP whitelist/blacklist functionality"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted"""
        try:
            return self.redis.sismember('ip_whitelist', ip)
        except Exception:
            return False
    
    def is_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted"""
        try:
            return self.redis.sismember('ip_blacklist', ip)
        except Exception:
            return False
    
    def add_to_whitelist(self, ip: str) -> bool:
        """Add IP to whitelist"""
        try:
            self.redis.sadd('ip_whitelist', ip)
            return True
        except Exception:
            return False
    
    def add_to_blacklist(self, ip: str, duration: int = None) -> bool:
        """Add IP to blacklist"""
        try:
            self.redis.sadd('ip_blacklist', ip)
            if duration:
                self.redis.expire('ip_blacklist', duration)
            return True
        except Exception:
            return False
    
    def remove_from_blacklist(self, ip: str) -> bool:
        """Remove IP from blacklist"""
        try:
            self.redis.srem('ip_blacklist', ip)
            return True
        except Exception:
            return False

def ip_filter(whitelist_only: bool = False):
    """
    IP filtering decorator
    
    Args:
        whitelist_only: If True, only allow whitelisted IPs
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            
            if hasattr(current_app, 'ip_whitelist'):
                # Check blacklist
                if current_app.ip_whitelist.is_blacklisted(ip):
                    logger.warning(
                        f"Blocked request from blacklisted IP: {ip}",
                        extra={'security': True, 'ip_filter': True, 'ip': ip}
                    )
                    return jsonify({'error': 'Access denied'}), 403
                
                # Check whitelist if required
                if whitelist_only and not current_app.ip_whitelist.is_whitelisted(ip):
                    logger.warning(
                        f"Blocked request from non-whitelisted IP: {ip}",
                        extra={'security': True, 'ip_filter': True, 'ip': ip}
                    )
                    return jsonify({'error': 'Access denied'}), 403
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def detect_suspicious_patterns():
    """Middleware to detect suspicious request patterns"""
    
    @wraps
    def wrapper():
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        # Detect common attack patterns
        suspicious_patterns = [
            'sqlmap', 'nikto', 'dirb', 'gobuster', 'nmap',
            'python-requests', 'curl', 'wget'  # Depending on your use case
        ]
        
        if any(pattern in user_agent.lower() for pattern in suspicious_patterns):
            logger.warning(
                f"Suspicious user agent detected: {user_agent}",
                extra={
                    'security': True,
                    'suspicious_pattern': True,
                    'ip': ip,
                    'user_agent': user_agent
                }
            )
        
        # Detect rapid requests from same IP
        if hasattr(current_app, 'rate_limiter'):
            key = f"suspicious:{ip}"
            allowed, info = current_app.rate_limiter.is_allowed(key, limit=50, window=60)
            
            if not allowed:
                logger.warning(
                    f"Rapid requests detected from IP: {ip}",
                    extra={
                        'security': True,
                        'rapid_requests': True,
                        'ip': ip
                    }
                )
                
                # Temporarily blacklist aggressive IPs
                if hasattr(current_app, 'ip_whitelist'):
                    current_app.ip_whitelist.add_to_blacklist(ip, duration=3600)  # 1 hour
    
    return wrapper

def setup_security_middleware(app):
    """Setup security middleware for the Flask application"""
    
    # Initialize rate limiter
    if hasattr(app, 'redis_client'):
        app.rate_limiter = RateLimiter(app.redis_client)
        app.ip_whitelist = IPWhitelist(app.redis_client)
    
    # Apply security headers to all responses
    @app.after_request
    def apply_security_headers(response):
        return SecurityHeaders.apply_headers(response)
    
    # Request logging and suspicious pattern detection
    @app.before_request
    def log_request():
        # Generate request ID
        g.request_id = hashlib.md5(
            f"{time.time()}{request.remote_addr}{request.path}".encode()
        ).hexdigest()[:8]
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.path}",
            extra={
                'request_id': g.request_id,
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent')
            }
        )
        
        # Detect suspicious patterns
        detect_suspicious_patterns()
    
    # Response logging
    @app.after_request
    def log_response(response):
        logger.info(
            f"Response: {response.status_code}",
            extra={
                'request_id': getattr(g, 'request_id', 'unknown'),
                'status_code': response.status_code,
                'content_length': response.content_length
            }
        )
        return response

# Decorators for common rate limits
def auth_rate_limit(func):
    """Rate limit for authentication endpoints"""
    return rate_limit(limit=10, window=300, per='ip')(func)

def api_rate_limit(func):
    """Rate limit for general API endpoints"""
    return rate_limit(limit=100, window=3600, per='user')(func)

def admin_rate_limit(func):
    """Rate limit for admin endpoints"""
    return rate_limit(limit=50, window=3600, per='user')(func)

def webhook_rate_limit(func):
    """Rate limit for webhook endpoints"""
    return rate_limit(limit=1000, window=3600, per='ip')(func)
