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
    from .app_unified import main as api_main
    api_main()
