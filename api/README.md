# Yumi Sugoi Discord Bot API Documentation

## Overview

The Yumi Sugoi Discord Bot API is a comprehensive RESTful API that provides real-time control and monitoring capabilities for the Yumi Sugoi Discord bot. The API enables web dashboard functionality, bot management, user data handling, and administrative operations.

## Base URL

```
Production: https://api.yumi-bot.com
Development: http://localhost:5000
```

## Authentication

The API supports multiple authentication methods:

### 1. API Key Authentication
Include the API key in the request header:
```http
X-API-Key: your-api-key-here
```

### 2. JWT Token Authentication
Include the JWT token in the Authorization header:
```http
Authorization: Bearer your-jwt-token-here
```

### 3. Discord OAuth2 (Web Dashboard)
OAuth2 flow for web dashboard authentication with Discord.

## Rate Limiting

The API implements rate limiting to ensure fair usage:
- **General API**: 100 requests per hour per user
- **Authentication**: 10 requests per 5 minutes per IP
- **Admin endpoints**: 50 requests per hour per user
- **Webhooks**: 1000 requests per hour per IP

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Error Handling

The API returns standardized error responses:

```json
{
  "error": "Error message",
  "status_code": 400,
  "timestamp": "2024-01-01T12:00:00Z",
  "field": "field_name"  // For validation errors
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error

## WebSocket Support

Real-time features are supported via WebSocket connections:

```javascript
const socket = io('ws://localhost:5000');

// Subscribe to bot status updates
socket.emit('subscribe_bot_status');

// Listen for status changes
socket.on('bot_status_update', (data) => {
  console.log('Bot status:', data);
});
```

## API Endpoints

### Bot Management

#### Get Bot Statistics
```http
GET /api/bot/stats
```

**Response:**
```json
{
  "guild_count": 150,
  "user_count": 50000,
  "uptime_seconds": 86400,
  "memory_usage_mb": 256,
  "cpu_usage_percent": 15.5,
  "commands_executed_today": 1250,
  "messages_processed_today": 8500,
  "active_conversations": 45
}
```

#### Get Bot Health
```http
GET /api/bot/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "services": {
    "database": {"status": "healthy", "response_time_ms": 12},
    "redis": {"status": "healthy", "response_time_ms": 3},
    "discord": {"status": "connected", "latency_ms": 45}
  },
  "system": {
    "cpu_percent": 15.5,
    "memory_percent": 45.2,
    "disk_percent": 30.8
  }
}
```

#### Get Bot Activity
```http
GET /api/bot/activity
```

**Query Parameters:**
- `limit` (optional): Number of events to return (default: 50)
- `since` (optional): ISO timestamp to get events since

#### Restart Bot (Admin)
```http
POST /api/bot/restart
Authorization: Bearer admin-jwt-token
```

### Server Management

#### List All Servers
```http
GET /api/servers
```

**Response:**
```json
{
  "servers": [
    {
      "id": "123456789012345678",
      "name": "My Discord Server",
      "icon": "https://cdn.discordapp.com/icons/123.png",
      "member_count": 1500,
      "text_channels": 25,
      "voice_channels": 8,
      "owner_id": "987654321098765432",
      "bot_permissions": ["SEND_MESSAGES", "READ_MESSAGES"],
      "joined_at": "2024-01-01T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 50
}
```

#### Get Server Details
```http
GET /api/servers/{guild_id}
```

#### Update Server Configuration
```http
PUT /api/servers/{guild_id}/config
Content-Type: application/json

{
  "persona_mode": "kawaii",
  "admin_users": ["123456789012345678"],
  "auto_respond": true,
  "command_prefix": "!",
  "moderation_enabled": false
}
```

#### Get Server Members
```http
GET /api/servers/{guild_id}/members
```

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 50)
- `role` (optional): Filter by role ID

#### Lock/Unlock Channel
```http
POST /api/servers/{guild_id}/channels/{channel_id}/lock
Content-Type: application/json

{
  "locked": true,
  "reason": "Maintenance"
}
```

### Persona Management

#### List All Personas
```http
GET /api/personas
```

**Response:**
```json
{
  "personas": [
    {
      "id": 1,
      "name": "normal",
      "description": "Default balanced personality",
      "type": "built-in",
      "is_default": true,
      "usage_count": 1500,
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "id": 2,
      "name": "kawaii",
      "description": "Cute and playful personality",
      "type": "built-in",
      "is_default": false,
      "usage_count": 850,
      "created_at": "2024-01-01T12:00:00Z"
    }
  ]
}
```

#### Create Custom Persona
```http
POST /api/personas
Content-Type: application/json

{
  "name": "professional",
  "description": "Professional business personality",
  "prompt": "You are a professional AI assistant...",
  "style": {
    "formality": "high",
    "emoji_usage": "minimal",
    "response_length": "detailed"
  },
  "sample_responses": [
    "Good morning! How may I assist you today?",
    "I understand your requirements and will help accordingly."
  ]
}
```

#### Activate Persona Globally
```http
POST /api/personas/{persona_name}/activate
```

#### Set Server Persona
```http
PUT /api/servers/{guild_id}/persona
Content-Type: application/json

{
  "persona_name": "kawaii"
}
```

### User Memory Management

#### Get Current User Info
```http
GET /api/users/me
Authorization: Bearer user-jwt-token
```

**Response:**
```json
{
  "id": "123456789012345678",
  "username": "user123",
  "discriminator": "1234",
  "avatar": "https://cdn.discordapp.com/avatars/123.png",
  "memory": {
    "facts": ["Likes cats", "Lives in Tokyo", "Software developer"],
    "preferences": {
      "response_style": "friendly",
      "language": "en",
      "timezone": "Asia/Tokyo"
    },
    "conversation_history_length": 25,
    "last_interaction": "2024-01-01T11:30:00Z"
  },
  "statistics": {
    "total_messages": 1250,
    "commands_used": 89,
    "favorite_persona": "normal",
    "member_since": "2024-01-01T12:00:00Z"
  }
}
```

#### Update User Memory
```http
PUT /api/users/me/memory
Content-Type: application/json

{
  "facts": ["Likes cats", "Lives in Tokyo", "Software developer", "Enjoys gaming"],
  "preferences": {
    "response_style": "casual",
    "language": "en"
  }
}
```

#### Add User Fact
```http
POST /api/users/me/memory/facts
Content-Type: application/json

{
  "fact": "Prefers tea over coffee"
}
```

#### Export User Data (GDPR)
```http
GET /api/users/me/export
Authorization: Bearer user-jwt-token
```

#### Delete User Account
```http
DELETE /api/users/me
Authorization: Bearer user-jwt-token
```

### Q&A Learning System

#### List Q&A Pairs
```http
GET /api/qa/pairs
```

**Query Parameters:**
- `page` (optional): Page number
- `per_page` (optional): Items per page
- `category` (optional): Filter by category
- `search` (optional): Search query

#### Create Q&A Pair
```http
POST /api/qa/pairs
Content-Type: application/json

{
  "question": "How do I change my persona?",
  "answer": "Use the !persona command followed by the persona name.",
  "category": "commands",
  "keywords": ["persona", "change", "switch"],
  "confidence": 0.95
}
```

#### Search Q&A Pairs
```http
GET /api/qa/search?q=persona%20change
```

#### Train Q&A System
```http
POST /api/qa/train
Content-Type: application/json

{
  "pairs": [
    {
      "question": "What is Yumi?",
      "answer": "Yumi is an AI Discord bot assistant.",
      "category": "general"
    }
  ]
}
```

### Admin Tools

#### Get System Information
```http
GET /api/admin/system
Authorization: Bearer admin-jwt-token
```

#### List All Users (Admin)
```http
GET /api/admin/users
Authorization: Bearer admin-jwt-token
```

**Query Parameters:**
- `page`, `per_page`: Pagination
- `search`: Search users
- `banned`: Filter banned users

#### Manage User (Admin)
```http
PUT /api/admin/users/{user_id}
Content-Type: application/json
Authorization: Bearer admin-jwt-token

{
  "banned": false,
  "admin": true,
  "memory_limit": 1000
}
```

#### Clear User Memory (Admin)
```http
DELETE /api/admin/users/{user_id}/memory
Authorization: Bearer admin-jwt-token
```

#### Bulk Server Operations (Admin)
```http
POST /api/admin/servers/bulk
Content-Type: application/json
Authorization: Bearer admin-jwt-token

{
  "action": "set_persona",
  "server_ids": ["123", "456", "789"],
  "parameters": {
    "persona_name": "normal"
  }
}
```

#### Database Backup (Admin)
```http
POST /api/admin/database/backup
Authorization: Bearer admin-jwt-token
```

## WebSocket Events

### Client to Server Events

#### Subscribe to Bot Status
```javascript
socket.emit('subscribe_bot_status');
```

#### Subscribe to Server Activity
```javascript
socket.emit('subscribe_server_activity', {
  guild_id: '123456789012345678'
});
```

#### Execute Bot Command
```javascript
socket.emit('execute_bot_command', {
  command: 'set_persona',
  parameters: {
    guild_id: '123456789012345678',
    persona_name: 'kawaii'
  }
});
```

### Server to Client Events

#### Bot Status Update
```javascript
socket.on('bot_status_update', (data) => {
  // data: { status: 'online', guilds: 150, users: 50000, timestamp: '...' }
});
```

#### Server Activity Update
```javascript
socket.on('server_activity_update', (data) => {
  // data: { guild_id: '123', activity_type: 'message', details: {...} }
});
```

#### Command Result
```javascript
socket.on('command_result', (data) => {
  // data: { command: 'set_persona', success: true, result: {...} }
});
```

## SDKs and Libraries

### JavaScript/TypeScript
```bash
npm install yumi-bot-api
```

```javascript
import { YumiAPI } from 'yumi-bot-api';

const api = new YumiAPI({
  baseURL: 'https://api.yumi-bot.com',
  apiKey: 'your-api-key'
});

// Get bot stats
const stats = await api.bot.getStats();
console.log(stats);
```

### Python
```bash
pip install yumi-bot-api
```

```python
from yumi_bot_api import YumiAPI

api = YumiAPI(
    base_url='https://api.yumi-bot.com',
    api_key='your-api-key'
)

# Get bot stats
stats = api.bot.get_stats()
print(stats)
```

## Webhooks

### Discord Bot Events
Configure webhooks to receive real-time bot events:

```http
POST /api/webhooks/discord
X-Signature-256: sha256=signature
X-Timestamp: 1640995200
Content-Type: application/json

{
  "event": "message_create",
  "data": {
    "guild_id": "123456789012345678",
    "channel_id": "987654321098765432",
    "user_id": "456789012345678901",
    "content": "Hello Yumi!",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

## Development

### Running Locally

1. Clone the repository:
```bash
git clone https://github.com/yourusername/yumi-sugoi.git
cd yumi-sugoi
```

2. Install dependencies:
```bash
pip install -r api/requirements.txt
```

3. Set environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize database:
```bash
python api/migrate.py init
python api/migrate.py seed
```

5. Run the API:
```bash
python run_api.py
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build individual container
docker build -t yumi-api ./api
docker run -p 5000:5000 yumi-api
```

## Security

- **HTTPS Only**: All production endpoints require HTTPS
- **Rate Limiting**: Prevents abuse and ensures fair usage
- **Input Validation**: All inputs are validated and sanitized
- **Authentication**: Multiple auth methods with proper token validation
- **CORS**: Configured for approved domains only
- **Security Headers**: Comprehensive security headers applied
- **Audit Logging**: All actions are logged for security monitoring

## Support

- **Documentation**: https://docs.yumi-bot.com
- **Discord Server**: https://discord.gg/yumi-bot
- **GitHub Issues**: https://github.com/yourusername/yumi-sugoi/issues
- **Email Support**: support@yumi-bot.com

## Changelog

### v2.0.0 (2024-01-01)
- Complete API rewrite with Flask
- Added real-time WebSocket support
- Implemented comprehensive authentication
- Added admin tools and bulk operations
- Enhanced security and rate limiting
- Added Q&A learning system
- Improved user memory management

### v1.0.0 (2023-12-01)
- Initial API release
- Basic bot management endpoints
- Simple authentication
- Dashboard integration
