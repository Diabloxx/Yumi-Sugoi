# Yumi Sugoi Discord AI Chatbot

Yumi Sugoi is a modular, multi-persona Discord AI chatbot powered by OpenAI and self-learning Q&A. She supports per-user and per-server persona modes, persistent memory, and a modern Discord experience.

## Features
- Multiple persona modes (normal, mistress, bdsm, girlfriend, wifey)
- Per-user and per-server mode switching (with persistence)
- Self-learning Q&A (teachable by users)
- Persistent per-user name memory
- Human-like typing and chat
- Discord slash commands and admin support
- Random DM reminders
- Rotating Discord status
- Image captioning (BLIP)
- Web search fallback

## New Features (2025)

- **Admin Hot-Reload:** `!yumi_reload` lets admins reload bot modules and persistent data without restarting the bot.
- **Advanced Persona System:** Create, edit, and activate custom personas. Set personas per channel. Switch between built-in and user personas.
- **Channel Personas:** Assign a persona to a specific channel for unique vibes.
- **Scheduled Announcements:** Use `!yumi_announce` to schedule reminders/announcements in any channel.
- **Long-Term User Memory:** Store and recall user facts/preferences with `!yumi_fact` and `!yumi_fact_recall`.
- **XP/Leveling System:** Earn XP for chatting, level up, and check your progress with `!yumi_level`.
- **Fun/Utility Commands:** Polls (`!yumi_poll`), suggestion box (`!yumi_suggest`), meme generator (`!yumi_meme`), and more.
- **Media/AI Features:** Placeholders for AI art (`!yumi_aiart`) and TTS/voice (`!yumi_tts`).
- **Advanced Moderation:** Auto-moderation, message delete/member join logging to #yumi-logs.
- **Web Dashboard (WIP):** Flask API endpoints for personas and XP, groundwork for a future dashboard.

## Requirements
- Python 3.9+
- **discord.py 2.x+** (for slash command support)
- Flask, python-dotenv, and other dependencies in requirements.txt

> **Note:** Slash commands (e.g. `/yumi_mode`) are supported natively using discord.py 2.x+ and do not require any extra libraries.

## Project Structure

```
AI-Discord/
│   README.md
│   requirements.txt
│   .gitignore
│   run_bot.py
│   cleanup_datasets.py
│
├── bot_core/
│   ├── __init__.py
│   ├── main.py           # Main bot logic
│   ├── persona.py        # Persona logic
│   ├── llm.py            # LLM/OpenAI logic
│   ├── history.py        # Conversation history
│   ├── feedback.py       # Feedback and learning
│   ├── websearch.py      # Web search fallback
│   ├── image_caption.py  # Image captioning
│
├── datasets/
│   ├── chatbot_dataset.json   # Q&A pairs (self-learning)
│   ├── user_names.json        # Per-user name memory
│   ├── yumi_modes.json        # Persona mode persistence
│   └── README.txt             # Dataset info
```

## Setup
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create a `.env` file with your Discord and OpenAI tokens:
   ```
   DISCORD_TOKEN=your_discord_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```
3. Run the bot:
   ```
   python run_bot.py
   ```

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
