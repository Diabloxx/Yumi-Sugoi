"""
Enhanced error handling and logging utilities for Yumi Sugoi Discord Bot API

This module provides comprehensive error handling, custom exceptions,
and advanced logging functionality for the Flask API.
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional, Tuple
from flask import request, jsonify, g
import structlog
from pythonjsonlogger import jsonlogger

# Custom exceptions
class YumiAPIError(Exception):
    """Base exception for Yumi API errors"""
    def __init__(self, message: str, status_code: int = 500, payload: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

class AuthenticationError(YumiAPIError):
    """Authentication failed"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)

class AuthorizationError(YumiAPIError):
    """Authorization failed"""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)

class ValidationError(YumiAPIError):
    """Request validation failed"""
    def __init__(self, message: str, field: Optional[str] = None):
        payload = {'field': field} if field else None
        super().__init__(message, status_code=400, payload=payload)

class NotFoundError(YumiAPIError):
    """Resource not found"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)

class RateLimitError(YumiAPIError):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=429)

class ExternalServiceError(YumiAPIError):
    """External service error"""
    def __init__(self, message: str, service: str):
        super().__init__(f"{service}: {message}", status_code=502)

# Logging configuration
class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add request context if available
        if hasattr(g, 'request_id'):
            log_entry['request_id'] = g.request_id
        
        if request:
            log_entry['request'] = {
                'method': request.method,
                'url': request.url,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent'),
            }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_entry['extra'] = log_entry.get('extra', {})
                log_entry['extra'][key] = value
        
        return self._format_json(log_entry)
    
    def _format_json(self, log_entry):
        """Format log entry as JSON"""
        import json
        return json.dumps(log_entry, default=str, ensure_ascii=False)

def setup_logging(app):
    """Setup comprehensive logging for the application"""
    
    # Create logs directory
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with structured output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = StructuredFormatter()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = logging.FileHandler(
        os.path.join(log_dir, 'yumi_api.log'),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(console_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.FileHandler(
        os.path.join(log_dir, 'errors.log'),
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(console_formatter)
    root_logger.addHandler(error_handler)
    
    # Performance file handler
    perf_handler = logging.FileHandler(
        os.path.join(log_dir, 'performance.log'),
        encoding='utf-8'
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.addFilter(lambda record: hasattr(record, 'performance'))
    perf_handler.setFormatter(console_formatter)
    root_logger.addHandler(perf_handler)
    
    # Security file handler
    security_handler = logging.FileHandler(
        os.path.join(log_dir, 'security.log'),
        encoding='utf-8'
    )
    security_handler.setLevel(logging.WARNING)
    security_handler.addFilter(lambda record: hasattr(record, 'security'))
    security_handler.setFormatter(console_formatter)
    root_logger.addHandler(security_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    app.logger.info("Logging system initialized", extra={'component': 'logging'})

def error_handler(app):
    """Register error handlers for the Flask application"""
    
    @app.errorhandler(YumiAPIError)
    def handle_api_error(error):
        """Handle custom API errors"""
        response = {
            'error': error.message,
            'status_code': error.status_code,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if error.payload:
            response.update(error.payload)
        
        app.logger.warning(
            f"API Error: {error.message}",
            extra={
                'error_type': type(error).__name__,
                'status_code': error.status_code,
                'payload': error.payload
            }
        )
        
        return jsonify(response), error.status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors"""
        response = {
            'error': 'Resource not found',
            'status_code': 404,
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }
        
        app.logger.warning(f"404 Not Found: {request.path}")
        return jsonify(response), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """Handle method not allowed errors"""
        response = {
            'error': 'Method not allowed',
            'status_code': 405,
            'timestamp': datetime.utcnow().isoformat(),
            'method': request.method,
            'path': request.path
        }
        
        app.logger.warning(f"405 Method Not Allowed: {request.method} {request.path}")
        return jsonify(response), 405
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle internal server errors"""
        response = {
            'error': 'Internal server error',
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        app.logger.error(
            f"Internal Server Error: {str(error)}",
            exc_info=True,
            extra={'error_type': 'internal_server_error'}
        )
        
        return jsonify(response), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors"""
        response = {
            'error': 'An unexpected error occurred',
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        app.logger.error(
            f"Unexpected Error: {str(error)}",
            exc_info=True,
            extra={
                'error_type': 'unexpected_error',
                'exception_class': type(error).__name__
            }
        )
        
        return jsonify(response), 500

def log_performance(func):
    """Decorator to log function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.utcnow()
        
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logging.getLogger().info(
                f"Function {func.__name__} executed",
                extra={
                    'performance': True,
                    'function': func.__name__,
                    'duration_seconds': duration,
                    'success': success,
                    'error': error,
                    'args_count': len(args),
                    'kwargs_count': len(kwargs)
                }
            )
        
        return result
    return wrapper

def log_security_event(event_type: str, details: Dict[str, Any], level: str = 'warning'):
    """Log security-related events"""
    logger = logging.getLogger()
    log_method = getattr(logger, level.lower(), logger.warning)
    
    log_method(
        f"Security Event: {event_type}",
        extra={
            'security': True,
            'event_type': event_type,
            'details': details,
            'remote_addr': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None
        }
    )

def validate_request_data(required_fields: list, optional_fields: list = None):
    """Decorator to validate request data"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                raise ValidationError("Request must be JSON")
            
            data = request.get_json()
            if not data:
                raise ValidationError("Request body cannot be empty")
            
            # Check required fields
            missing_fields = []
            for field in required_fields:
                if field not in data or data[field] is None:
                    missing_fields.append(field)
            
            if missing_fields:
                raise ValidationError(
                    f"Missing required fields: {', '.join(missing_fields)}",
                    field=missing_fields[0]
                )
            
            # Validate field types if specified
            for field in required_fields + (optional_fields or []):
                if field in data and hasattr(func, '__annotations__'):
                    expected_type = func.__annotations__.get(field)
                    if expected_type and not isinstance(data[field], expected_type):
                        raise ValidationError(
                            f"Field '{field}' must be of type {expected_type.__name__}",
                            field=field
                        )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def handle_external_service_error(service_name: str):
    """Context manager for handling external service errors"""
    class ExternalServiceContext:
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                if hasattr(exc_val, 'response'):
                    # HTTP error
                    status_code = getattr(exc_val.response, 'status_code', 500)
                    message = f"HTTP {status_code} error"
                else:
                    # Other error
                    message = str(exc_val)
                
                logging.getLogger().error(
                    f"External service error: {service_name}",
                    extra={
                        'service': service_name,
                        'error': message,
                        'exception_type': exc_type.__name__
                    },
                    exc_info=True
                )
                
                raise ExternalServiceError(message, service_name)
    
    return ExternalServiceContext()

# Health check utilities
def get_system_health() -> Dict[str, Any]:
    """Get system health information"""
    import psutil
    import redis
    from api.app import db, redis_client
    
    health = {
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'healthy',
        'services': {}
    }
    
    # Database health
    try:
        db.session.execute('SELECT 1')
        health['services']['database'] = {'status': 'healthy', 'response_time_ms': 0}
    except Exception as e:
        health['services']['database'] = {'status': 'unhealthy', 'error': str(e)}
        health['status'] = 'degraded'
    
    # Redis health
    try:
        start_time = datetime.utcnow()
        redis_client.ping()
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        health['services']['redis'] = {'status': 'healthy', 'response_time_ms': response_time}
    except Exception as e:
        health['services']['redis'] = {'status': 'unhealthy', 'error': str(e)}
        health['status'] = 'degraded'
    
    # System metrics
    try:
        health['system'] = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
        }
    except Exception:
        health['system'] = {'error': 'Unable to retrieve system metrics'}
    
    return health
