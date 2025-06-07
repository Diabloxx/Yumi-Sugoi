"""
Yumi Sugoi Discord Bot API Package

This package contains the Flask-based API for the Yumi Sugoi Discord bot dashboard,
providing endpoints for bot management, statistics, and user interactions.
"""

__version__ = "2.0.0"
__author__ = "Yumi Sugoi Team"
__email__ = "contact@yumi-sugoi.dev"
__license__ = "MIT"

# Core imports
from . import app_unified

# Version information
VERSION = __version__

def get_version():
    """Get the current version of the API."""
    return __version__

def main():
    """Main entry point for the API server."""
    import sys
    import os
    
    # Add the project root to Python path
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Import and run the unified app
    from .app_unified import app
    
    print("Starting Yumi Sugoi API Server...")
    print(f"Database: {app.config['DATABASE_PATH']}")
    print(f"Available at: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
