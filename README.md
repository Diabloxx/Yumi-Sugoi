# Yumi Sugoi Discord AI Chatbot

[![CI](https://github.com/Diabloxx/Yumi-Sugoi/actions/workflows/ci.yml/badge.svg)](https://github.com/Diabloxx/Yumi-Sugoi/actions/workflows/ci.yml)
[![Release](https://github.com/Diabloxx/Yumi-Sugoi/actions/workflows/release.yml/badge.svg)](https://github.com/Diabloxx/Yumi-Sugoi/actions/workflows/release.yml)
[![PyPI version](https://badge.fury.io/py/yumi-sugoi.svg)](https://badge.fury.io/py/yumi-sugoi)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Yumi Sugoi is a modern, feature-rich Discord AI chatbot powered by Ollama LLM and equipped with multiple personas, self-learning capabilities, persistent memory, and a beautiful web dashboard. Perfect for communities seeking an engaging, customizable AI companion.

## Core Features
- **Advanced AI Chat:** Natural, context-aware conversations powered by local Ollama LLM
- **Multi-Persona System:** Rich selection of personality modes with custom persona support
- **Modern Dashboard:** Beautiful web interface for administration and monitoring
- **Self-Learning:** Learns from user interactions and feedback
- **Privacy-Focused:** Local LLM processing with Ollama, no data sent to external APIs
- **Persistent Memory:** Remembers user preferences, facts, and conversation context
- **Automatic User Fact Memory:** Yumi now automatically extracts and remembers user facts (like name, location, preferences) from natural language, without explicit commands
- **Per-User, Per-Channel Context:** Maintains separate conversation history and memory for each user in each channel or DM, supporting many users in parallel

## Key Features (2025)

### AI & Chat
- **Local LLM Processing:** Powered by Ollama (default: gemma3:4b) for complete privacy
- **Natural Conversations:** Human-like typing indicators and response timing
- **Multi-Context Memory:** Separate conversation context per user and channel
- **Smart Responses:** Context-aware replies with personality consistency
- **Image Understanding:** BLIP-powered image captioning
- **Web Search Fallback:** Handles unknown topics via web search integration

### Personalization
- **Dynamic Personas:** Switch between built-in and custom personality modes
- **Channel-Specific Personas:** Set unique personas for different channels
- **User Memory:** Remembers names, preferences, and user-taught facts
- **Automatic Fact Extraction:** Yumi can now learn facts about users from natural conversation (e.g., "my name is...", "I live in...") and recall them in future chats
- **XP System:** Engage users with chat-based leveling and rewards
- **Custom Commands:** Create and manage server-specific commands

### Administration
- **Modern Dashboard:**
  - Real-time chat monitoring and control
  - User management and analytics
  - Server settings and persona configuration
  - Moderation tools and logs
  - Task scheduling and announcements
  - Beautiful white UI with responsive design

### Moderation
- **Smart Lockdown:** Channel-specific response restrictions
- **Auto-Moderation:** Content filtering and user management
- **Audit Logging:** Comprehensive activity tracking
- **Admin Commands:** Powerful moderation and management tools

## Installation & Quick Start

### From PyPI (Recommended)
```bash
# Install the package
pip install yumi-sugoi

# Run the bot
yumi-bot

# Run the API dashboard (in another terminal)
yumi-api
```

### From Source
```bash
# Clone the repository
git clone https://github.com/Diabloxx/Yumi-Sugoi.git
cd Yumi-Sugoi

# Install in development mode
pip install -e .

# Run the bot
yumi-bot

# Run the API dashboard
yumi-api
```

## Requirements
- Python 3.8+
- Ollama (running locally or on network)
- Discord Bot Token (from Discord Developer Portal)
- Redis (optional, for enhanced performance)
## Configuration

### Environment Variables
Create a `.env` file in the project root:

```ini
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_token_here

# Ollama LLM Configuration  
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=mistralrp
OLLAMA_TEMPERATURE=0.7
OLLAMA_NUM_PREDICT=256

# API Configuration
API_SECRET_KEY=your_secret_key_here
FLASK_SECRET_KEY=your_flask_secret_key

# Optional: Redis Configuration
REDIS_URL=redis://localhost:6379

# Optional: Database Configuration
DATABASE_URL=sqlite:///./api/yumi_bot.db
```

### API Tokens
Generate API tokens for dashboard access:
```bash
python generate_api_token.py
```

## Quick Setup

1. **Install Ollama** and pull the model:
   ```bash
   ollama pull mistralrp
   ```

2. **Install Yumi Sugoi**:
   ```bash
   pip install yumi-sugoi
   ```

3. **Configure Environment**:
   - Copy `.env.example` to `.env`
   - Add your Discord bot token
   - Configure Ollama URL if not running locally

4. **Run the Bot**:
   ```bash
   yumi-bot
   ```

5. **Run the Dashboard** (optional):
   ```bash
   yumi-api
   ```
   ```powershell
   python scripts/database_setup.py
   ```

4. Start the full system (API + Bot):
   ```powershell
   python start_yumi.py
   ```
   
   Or run components separately:
   ```powershell
   # API server only
   python run_api.py
   
   # Discord bot only  
   python run_bot.py
   ```

5. Access dashboard: http://localhost:5000

## Key Commands

### General
- `/help` - Show command list
- `/yumi_mode <mode>` - Change persona mode
- `/yumi_level` - Check your XP level
- `/yumi_fact <text>` - Teach Yumi a fact (manual, but now also learns automatically)
- `/yumi_fact_recall` - Recall stored facts

### Admin
- `/yumi_reload` - Hot-reload bot modules
- `/yumi_lockdown` - Restrict responses to specific channel
- `/yumi_announce` - Schedule announcements
- `/yumi_persona_create` - Create custom persona

## Project Structure
```
Yumi-Sugoi/
├── api/               # Flask API backend
│   ├── app.py         # Main API application
│   ├── app_fixed.py   # SQLite-based API (production)
│   ├── routes_*.py    # API route modules
│   ├── yumi_bot.db    # SQLite database
│   └── ...
├── bot_core/          # Core Discord bot functionality
│   ├── main.py        # Main bot logic
│   ├── llm.py         # Ollama LLM integration
│   ├── persona.py     # Persona system
│   ├── commands.py    # Bot commands
│   ├── static/        # Web dashboard assets
│   ├── templates/     # Dashboard templates
│   └── ...
├── datasets/          # Persistent data storage
│   ├── user_facts.json    # User memory data
│   ├── convo_history.json # Conversation history
│   ├── custom_personas.json # Custom personas
│   └── dashboard_data/    # Dashboard analytics
├── tests/             # All test files
├── scripts/           # Setup and utility scripts
├── docs/              # Documentation
├── docker/            # Docker configuration
├── logs/              # Application logs
├── start_yumi.py      # Unified startup script
├── run_api.py         # API server launcher
└── run_bot.py         # Bot launcher
```

## Memory & Context System (2025)
- Yumi now automatically extracts user facts (name, location, preferences, etc.) from natural language and stores them per user.
- Conversation history and user facts are injected into the LLM prompt for more natural, context-aware responses.
- Memory is tracked per user and per channel/DM, supporting many users in parallel.
- All memory and context features work for both general and private conversations.

## Contributing
Issues and PRs welcome! Check our contribution guidelines in CONTRIBUTING.md.

## Support
Join our Discord server for support, updates, and community discussion.
