"""
Yumi Sugoi Discord Bot Core Package

This package contains the core functionality for the Yumi Sugoi Discord bot,
including AI capabilities, persona management, and command handling.
"""

__version__ = "2.0.0"
__author__ = "Yumi Sugoi Team"
__email__ = "contact@yumi-sugoi.dev"
__license__ = "MIT"

# Core imports
from . import main
from . import persona
from . import llm
from . import commands

# Version information
VERSION = __version__

def get_version():
    """Get the current version of the bot."""
    return __version__

def main():
    """Main entry point for the bot."""
    from .main import run
    run()
