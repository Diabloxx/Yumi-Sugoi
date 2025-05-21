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

## Contributing
Pull requests are welcome! Please keep code modular and well-documented.
