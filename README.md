# Yumi Sugoi Discord AI Chatbot

Yumi Sugoi is a modular, multi-persona Discord AI chatbot powered by Ollama and self-learning Q&A. She supports per-user and per-server persona modes, persistent memory, and a modern Discord experience.

## Features
- Multiple persona modes (normal, mistress, bdsm, girlfriend, wifey, tsundere, shy, and more)
- Per-user and per-server mode switching (with persistence)
- Self-learning Q&A (teachable by users)
- Local LLM integration with Ollama (using gemma3:4b by default)
- Persistent per-user name memory
- Human-like typing and chat
- Discord slash commands and admin support
- Random DM reminders
- Rotating Discord status
- Image captioning (BLIP)
- Web search fallback
- Modern white UI dashboard for administration

## New Features (2025)

- **Ollama Integration:** Use your own local network Ollama instance (gemma3:4b model by default) for complete privacy control and no usage costs.
- **Configurable LLM Settings:** Customize model, temperature, and other parameters via environment variables.
- **Admin Hot-Reload:** `!yumi_reload` lets admins reload bot modules and persistent data without restarting the bot.
- **Advanced Persona System:** Create, edit, and activate custom personas. Set personas per channel. Switch between built-in and user personas.
- **Channel Personas:** Assign a persona to a specific channel for unique vibes.
- **Scheduled Announcements:** Use `!yumi_announce` to schedule reminders/announcements in any channel.
- **Long-Term User Memory:** Store and recall user facts/preferences with `!yumi_fact` and `!yumi_fact_recall`.
- **XP/Leveling System:** Earn XP for chatting, level up, and check your progress with `!yumi_level`.
- **Fun/Utility Commands:** Polls (`!yumi_poll`), suggestion box (`!yumi_suggest`), meme generator (`!yumi_meme`), and more.
- **Media/AI Features:** Placeholders for AI art (`!yumi_aiart`) and TTS/voice (`!yumi_tts`).
- **Advanced Moderation:** Auto-moderation, message delete/member join logging to #yumi-logs.
- **Web Dashboard:** Live chat console, user management, scheduled tasks, persona management, server controls, and moderation logs with modern white UI.

## Requirements
- Python 3.9+
- **discord.py 2.x+** (for slash command support)
- Flask, python-dotenv, and other dependencies in requirements.txt

> **Note:** Slash commands (e.g. `/yumi_mode`) are supported natively using discord.py 2.x+ and do not require any extra libraries.

## Project Structure

```
Yumi-Sugoi/
│   README.md
│   requirements.txt
│   .gitignore
│   .env                  # Environment variables (DISCORD_TOKEN, Ollama settings)
│   .env.example          # Example environment variables
│   run_bot.py            # Main entry point
│   CHANGELOG.md          # Version history
│
├── bot_core/
│   ├── __init__.py
│   ├── main.py           # Main bot logic
│   ├── persona.py        # Persona logic
│   ├── llm.py            # LLM/Ollama integration
│   ├── history.py        # Conversation history
│   ├── feedback.py       # Feedback and learning
│   ├── websearch.py      # Web search fallback
│   ├── image_caption.py  # Image captioning
│   ├── web_dashboard.py  # Web dashboard backend
│   ├── static/           # Static assets for dashboard
│   └── templates/        # HTML templates for dashboard
│
├── datasets/
│   ├── chatbot_dataset.json   # Q&A pairs (self-learning)
│   ├── user_facts.json        # User long-term memory
│   ├── custom_personas.json   # Custom persona data
│   ├── user_xp.json           # User XP/leveling data
│   ├── ollama_log.txt         # Log of prompts and responses
```

## Setup
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create a `.env` file with your Discord token and Ollama settings:
   ```
   DISCORD_TOKEN=your_discord_token_here
   OLLAMA_URL=http://10.0.0.28:11434/api/generate
   OLLAMA_MODEL=gemma3:4b
   OLLAMA_TEMPERATURE=0.7
   OLLAMA_NUM_PREDICT=256
   ```
3. Run the bot:
   ```
   python run_bot.py
   ```
4. Access the web dashboard at http://localhost:5000

## Usage Example

- Change persona: `!yumi_mode <mode>` or `/yumi_mode <mode>`
- Create persona: `!yumi_persona_create <name> <description>`
- Set channel persona: `!yumi_channel_persona <name>`
- Schedule announcement: `!yumi_announce YYYY-MM-DD HH:MM <message>`
- Store fact: `!yumi_fact <something>`
- Recall fact: `!yumi_fact_recall`
- Check level: `!yumi_level`
- Admin reload: `!yumi_reload`

> **Tip:** You can use both traditional prefix commands (e.g. `!yumi_mode`) and Discord slash commands (e.g. `/yumi_mode`) with this bot.

See `!yumi_help` for more commands and details.

## Contributing
Pull requests are welcome! Please keep code modular and well-documented.
