# Changelog

All notable changes to Yumi Sugoi Discord Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-06-07

### Added
- **Python Package Distribution**: Complete PyPI-ready package structure
  - Modern `pyproject.toml` configuration
  - Backward-compatible `setup.py`
  - Package metadata and entry points
  - MIT license
- **Command-line Entry Points**: 
  - `yumi-bot` command to start the Discord bot
  - `yumi-api` command to start the web dashboard
- **GitHub Workflows**: 
  - Automated CI/CD pipeline with multi-platform testing
  - Automated PyPI releases on version tags
  - Comprehensive testing on Python 3.8-3.12
- **Custom Persona Override System**: Support for custom personas in persona commands
- **Enhanced Security**: 
  - Comprehensive `.gitignore` protecting sensitive data
  - Example configuration files for setup guidance
  - Security audit and data protection
- **Real Uptime Tracking**: Implemented accurate uptime tracking for bot monitoring
  - Added `BotStatusPublisher` class with start time tracking and uptime calculation
  - Enhanced `/api/bot/health` endpoint to display real uptime in formatted string
  - Status data published to Redis every 30 seconds with real metrics
- **API Integration Module**: New `api_integration.py` for bot-API communication
- **Enhanced Server Tracking**: Improved server join/leave event handlers

### Fixed
- **API Command Tracking**: Fixed 500 error caused by field name mismatch in command logging
- **Custom Persona Validation**: Resolved KeyError when using custom personas
- **Package Entry Points**: Fixed ImportError issues with pip-installed commands
- **Authentication Errors**: Improved API token validation and error handling

### Changed
- **Project Structure**: Reorganized as a proper Python package
- **Installation Method**: Now installable via `pip install yumi-sugoi`
- **Configuration**: Enhanced environment variable handling
- **Documentation**: Updated README with new installation and usage instructions
- **Bot Status Reporting**: Replaced hardcoded "active" status with calculated uptime
- **API Health Check**: Enhanced to fetch and display real uptime from Redis storage

### Security
- **Data Protection**: All sensitive files properly ignored by git
- **Token Security**: Enhanced API token management
- **Environment Variables**: Secure configuration file handling

## [1.9.0] - Previous Core Features

### Core Features
- Advanced AI chat with Ollama LLM integration
- Multi-persona system with dynamic personality switching
- Modern web dashboard with real-time monitoring
- Self-learning capabilities with user feedback
- Privacy-focused local LLM processing
- Persistent memory and context management
- Automatic user fact extraction and memory
- Per-user, per-channel conversation context
- Image understanding with BLIP captioning
- Smart moderation and lockdown features
- XP system and user engagement tools
- Custom commands and server management

### Technical
- Flask-based API backend
- Discord.py bot framework
- SQLite database with migration support
- Redis caching (optional)
- Docker containerization
- Comprehensive test suite
- **Background Tasks**: Status updates run every 30 seconds to maintain current metrics

### Fixed
- **Indentation Errors**: Resolved syntax issues in status publisher module
- **Import Errors**: Fixed module initialization preventing bot startup

---

## Previous Versions

*This changelog starts from the implementation of uptime tracking. Previous changes were not formally documented.*