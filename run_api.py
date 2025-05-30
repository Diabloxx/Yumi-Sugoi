#!/usr/bin/env python3
"""
Yumi Sugoi Discord Bot API Server Startup Script

This script initializes and runs the Flask API server for the Yumi Sugoi
Discord bot dashboard with proper configuration and error handling.
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def setup_environment():
    """Setup environment variables with defaults"""
    env_vars = {
        'FLASK_SECRET_KEY': 'yumi-dashboard-secret-key-change-in-production',
        'JWT_SECRET': 'yumi-jwt-secret-change-in-production',
        'API_KEY': 'yumi-api-key-change-in-production',
        'DATABASE_URL': 'sqlite:///yumi_dashboard.db',
        'REDIS_URL': 'redis://localhost:6379',
        'FLASK_ENV': 'development'
    }
    
    for key, default_value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = default_value
            logger.info(f"Set default {key}")

def check_dependencies():
    """Check if all required dependencies are available"""
    required_packages = [
        'flask', 'flask_cors', 'redis', 'jwt'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Missing required packages: {missing_packages}")
        logger.error("Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)

def initialize_database():
    """Initialize database if needed"""
    try:
        # Check if SQLite database exists
        db_path = os.path.join('api', 'yumi_bot.db')
        if os.path.exists(db_path):
            logger.info("Database found and ready")
            return True
        else:
            logger.warning("Database not found - please run database setup script")
            logger.info("Run: python scripts/database_setup.py")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def test_redis_connection():
    """Test Redis connection"""
    try:
        import redis
        redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))
        redis_client.ping()
        logger.info("Redis connection successful")
        return True
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        logger.warning("Some real-time features may not work without Redis")
        return False

def main():
    """Main startup function"""
    logger.info("Starting Yumi Sugoi Dashboard API Server...")
    logger.info(f"Startup time: {datetime.now().isoformat()}")
    
    # Setup environment
    setup_environment()
    
    # Check dependencies
    check_dependencies()
    
    # Initialize database
    if not initialize_database():
        logger.error("Failed to initialize database. Exiting.")
        sys.exit(1)
    
    # Test Redis (optional)
    test_redis_connection()
      # Import and start the Flask app
    try:
        from api.app_fixed import app
        
        # Configure Flask app
        app.config['ENV'] = os.getenv('FLASK_ENV', 'development')
        
        if app.config['ENV'] == 'development':
            logger.info("Running in development mode")
            app.run(
                debug=True,
                host='0.0.0.0',
                port=int(os.getenv('PORT', 5000))
            )
        else:
            logger.info("Running in production mode")
            app.run(
                debug=False,
                host='0.0.0.0',
                port=int(os.getenv('PORT', 5000))
            )
            
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
