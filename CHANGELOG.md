# Changelog

All notable changes to Yumi Sugoi bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Real Uptime Tracking**: Implemented accurate uptime tracking for bot monitoring
  - Added `BotStatusPublisher` class with start time tracking and uptime calculation
  - Enhanced `/api/bot/health` endpoint to display real uptime in formatted string (e.g., "2d 5h 30m")
  - Added uptime_seconds and start_time fields to API responses
  - Status data now published to Redis every 30 seconds with real metrics
- **API Integration Module**: New `api_integration.py` for bot-API communication
- **Enhanced Server Tracking**: Improved server join/leave event handlers
- **Status Publisher**: New `status_publisher.py` module for real-time bot status updates

### Changed
- **Bot Status Reporting**: Replaced hardcoded "active" status with calculated uptime
- **API Health Check**: Enhanced to fetch and display real uptime from Redis storage
- **Main Bot Integration**: Added initialization for API integration and status publishing

### Technical Details
- **Files Modified**:
  - `bot_core/main.py`: Added API integration and status publisher initialization
  - `bot_core/status_publisher.py`: New module for uptime tracking and status publishing
  - `bot_core/api_integration.py`: New module for bot-API communication
  - `api/routes_bot.py`: Enhanced health endpoint with real uptime data
- **Redis Integration**: Bot status now stored in Redis with structured data including uptime metrics
- **Background Tasks**: Status updates run every 30 seconds to maintain current metrics

### Fixed
- **Indentation Errors**: Resolved syntax issues in status publisher module
- **Import Errors**: Fixed module initialization preventing bot startup

---

## Previous Versions

*This changelog starts from the implementation of uptime tracking. Previous changes were not formally documented.*