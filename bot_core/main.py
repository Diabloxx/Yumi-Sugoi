import os
import json
import random
import asyncio
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
from datetime import datetime, timedelta
import threading
import traceback
import logging
import sys
import importlib
import re

# Local imports
from . import history
from . import feedback
from . import image_caption
from . import llm
from .feedback import (
    save_feedback_scores, 
    save_user_feedback, 
    reset_feedback, 
    export_feedback, 
    export_user_feedback, 
    get_user_feedback_stats,
    handle_response_feedback
)
from .websearch import duckduckgo_search_and_summarize
from .image_caption import caption_image
from .web_dashboard import load_dashboard_stats as load_dashboard_stats_func, start_dashboard_thread, set_bot_instance
from .yumi_vision import download_image_bytes, query_ollama_with_image


# --- Load initial state ---
# Load conversation history
CONVO_HISTORY = history.load_convo_history()

# Load feedback data
feedback_scores, user_feedback = feedback.load_feedback()

# Load AI models
BLIP_READY, blip_processor, blip_model = image_caption.load_blip()
AI_READY, ai_tokenizer, ai_model = llm.load_hf_model()

# Track users Yumi has interacted with
INTERACTED_USERS = set()

# --- Default Persona Modes ---
PERSONA_MODES = [
    'normal', 'mistress', 'bdsm', 'girlfriend', 'wifey', 'tsundere', 'shy', 'sarcastic',
    'optimist', 'pessimist', 'nerd', 'chill', 'supportive', 'comedian', 'philosopher',
    'grumpy', 'gamer', 'genalpha', 'egirl'
]

# --- Admin user ID and admin checks must be defined before any use ---
ADMIN_USER_ID = 594793428634566666

def is_admin(user):
    return getattr(user, 'id', None) == ADMIN_USER_ID

def admin_only():
    def predicate(ctx):
        return is_admin(ctx.author)
    from discord.ext.commands import check
    return check(predicate)

DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets')
CHATBOT_DATASET_FILE = os.path.join(DATASET_DIR, 'chatbot_dataset.json')
def load_chatbot_dataset():
    try:
        with open(CHATBOT_DATASET_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def save_chatbot_dataset():
    with open(CHATBOT_DATASET_FILE, 'w', encoding='utf-8') as f:
        json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
qa_pairs = load_chatbot_dataset()

# --- Custom Persona Storage ---
CUSTOM_PERSONAS_FILE = os.path.join(DATASET_DIR, 'custom_personas.json')
def load_custom_personas():
    try:
        with open(CUSTOM_PERSONAS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def save_custom_personas(personas):
    with open(CUSTOM_PERSONAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(personas, f, ensure_ascii=False, indent=2)
CUSTOM_PERSONAS = load_custom_personas()

# --- Channel Persona Storage ---
CHANNEL_PERSONAS_FILE = os.path.join(DATASET_DIR, 'channel_personas.json')
def load_channel_personas():
    try:
        with open(CHANNEL_PERSONAS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def save_channel_personas(personas):
    with open(CHANNEL_PERSONAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(personas, f, ensure_ascii=False, indent=2)
CHANNEL_PERSONAS = load_channel_personas()

# --- User Long-Term Memory ---
USER_FACTS_FILE = os.path.join(DATASET_DIR, 'user_facts.json')
def load_user_facts():
    try:
        with open(USER_FACTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def save_user_facts(facts):
    with open(USER_FACTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)
USER_FACTS = load_user_facts()

# --- XP/Leveling Storage ---
USER_XP_FILE = os.path.join(DATASET_DIR, 'user_xp.json')
def load_user_xp():
    try:
        with open(USER_XP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def save_user_xp(xp):
    with open(USER_XP_FILE, 'w', encoding='utf-8') as f:
        json.dump(xp, f, ensure_ascii=False, indent=2)
USER_XP = load_user_xp()

def get_xp(user_id):
    """Get XP for a specific user."""
    return USER_XP.get(str(user_id), 0)

def get_level(user_id):
    """Calculate level based on user's XP."""
    xp = get_xp(user_id)
    # Simple level calculation: level = floor(sqrt(xp / 100))
    # This means level 1 needs 100 XP, level 2 needs 400 XP, level 3 needs 900 XP, etc.
    import math
    return int(math.sqrt(xp / 100)) if xp > 0 else 0

# --- Scheduled Announcements ---
SCHEDULED_ANNOUNCEMENTS_FILE = os.path.join(DATASET_DIR, 'scheduled_announcements.json')
def load_scheduled_announcements():
    try:
        with open(SCHEDULED_ANNOUNCEMENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []
def save_scheduled_announcements(ann):
    with open(SCHEDULED_ANNOUNCEMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(ann, f, ensure_ascii=False, indent=2)
SCHEDULED_ANNOUNCEMENTS = load_scheduled_announcements()

# --- Loaders and Savers ---
def load_json_file(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_json_file(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

custom_personas = load_json_file(CUSTOM_PERSONAS_FILE, {})
channel_personas = load_json_file(CHANNEL_PERSONAS_FILE, {})
user_facts = load_json_file(USER_FACTS_FILE, {})
user_xp = load_json_file(USER_XP_FILE, {})
scheduled_announcements = load_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, [])

# Get Discord token from environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("ERROR: No Discord token found in environment variables!")
    print("Make sure you have a valid DISCORD_TOKEN in your .env file")
    print("Current .env path:", os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    # Fallback to a placeholder for testing - won't actually connect
    TOKEN = "placeholder_token"

# Setup Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

class YumiBot(commands.Bot):    
    async def setup_hook(self):
        try:
            # Register slash commands
            self.tree.add_command(yumi_mode_slash)
            self.tree.add_command(yumi_help_slash)
            
            # Load all custom commands
            from . import commands as yumi_commands
            # Set up prefix commands first
            yumi_commands.setup_prefix_commands(self)
            # Then set up and sync slash commands
            await yumi_commands.setup_slash_commands(self)
            print("[Commands] All custom commands loaded successfully.")
        except Exception as e:
            print(f"[Commands] Error loading commands: {e}")
        
        print("[Commands] All custom commands loaded successfully.")

bot = YumiBot(command_prefix='!', intents=intents)

@app_commands.command(name="yumi_mode", description="Change Yumi's persona mode (see help)")
@app_commands.describe(mode="The mode/persona to switch to")
async def yumi_mode_slash(interaction: discord.Interaction, mode: str):
    mode = mode.lower()
    if set_persona_mode(mode):
        set_context_mode(interaction, mode)
        # Update status immediately
        persona_status = {
            'normal': "Your friendly, caring AI companion 🤗 | !yumi_help",
            'mistress': "Mistress Yumi is in control 👠 | !yumi_mode",
            'bdsm': "Dungeon open. Safe words ready. 🖤 | !yumi_mode",
            'girlfriend': "Your playful AI girlfriend 💌 | !yumi_mode",
            'wifey': "Loyal, loving, and here for you 💍 | !yumi_mode",
            'tsundere': "Not like I like you or anything! 😳 | !yumi_mode",
            'shy': "Um... hi... (shy mode) 😳 | !yumi_mode",
            'sarcastic': "Sarcastic mode: Oh, joy. | !yumi_mode",
            'optimist': "Optimist mode: Good vibes only! 🌞 | !yumi_mode",
            'pessimist': "Pessimist mode: Here we go again... | !yumi_mode",
            'nerd': "Nerd mode: Did you know? 🤓 | !yumi_mode",
            'chill': "Chill mode: No worries 😎 | !yumi_mode",
            'supportive': "Supportive friend mode: You got this! 💪 | !yumi_mode",
            'comedian': "Comedian mode: Ready for laughs! 😂 | !yumi_mode",
            'philosopher': "Philosopher mode: Let's ponder... 🤔 | !yumi_mode",
            'grumpy': "Grumpy mode: What now? 😒 | !yumi_mode",
            'gamer': "Gamer mode: GLHF! 🎮 | !yumi_mode",
            'genalpha': "Gen Alpha mode: Slay, bestie! 💅 | !yumi_mode",
            'egirl': "E-girl mode: uwu cuteness overload! 🦋 | !yumi_mode"
        }
        status = persona_status.get(mode, persona_status['normal'])
        activity = discord.Game(name=status)
        await bot.change_presence(status=discord.Status.online, activity=activity)
        # Force LLM/persona to update immediately for this context
        set_persona_mode(mode)
        # Appealing mode change message
        mode_titles = {
            'normal': "Normal",
            'mistress': "Mistress",
            'bdsm': "Dungeon Mistress",
            'girlfriend': "Girlfriend",
            'wifey': "Wifey",
            'tsundere': "Tsundere",
            'shy': "Shy",
            'sarcastic': "Sarcastic",
            'optimist': "Optimist",
            'pessimist': "Pessimist",
            'nerd': "Nerd",
            'chill': "Chill",
            'supportive': "Supportive Friend",
            'comedian': "Comedian",
            'philosopher': "Philosopher",
            'grumpy': "Grumpy",
            'gamer': "Gamer",
            'genalpha': "Gen Alpha",
            'egirl': "E-girl"
        }
        mode_emojis = {
            'normal': "💖", 'mistress': "👠", 'bdsm': "🖤", 'girlfriend': "💌", 'wifey': "💍", 'tsundere': "😳",
            'shy': "😳", 'sarcastic': "😏", 'optimist': "🌞", 'pessimist': "😔", 'nerd': "🤓", 'chill': "😎",
            'supportive': "💪", 'comedian': "😂", 'philosopher': "🤔", 'grumpy': "😒", 'gamer': "🎮", 'genalpha': "💅",
            'egirl': "🦋"
        }
        title = mode_titles.get(mode, mode.capitalize())
        emoji = mode_emojis.get(mode, "✨")
        await interaction.response.send_message(f"{emoji} **Yumi's mode has changed!** Now in **{title}** mode.\n*Try chatting to see her new personality!* {emoji}", ephemeral=True)
    else:
        await interaction.response.send_message(f"Invalid mode. Available modes: {', '.join(PERSONA_MODES)}", ephemeral=True)

@app_commands.command(name="yumi_help", description="Show Yumi's help and features")
async def yumi_help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Yumi Sugoi Help & Features",
        description="Meet Yumi Sugoi: your modular, multi-persona AI Discord companion!\n\n**Use `/yumi_help` for a private help message.**",
        color=discord.Color.pink()
    )
    # --- Section: Persona Modes ---
    embed.add_field(
        name="__Persona Modes__",
        value=(
            "Yumi can switch between many built-in and custom personas!\n"
            "- Use `!yumi_mode <mode>` or `/yumi_mode <mode>` to change persona.\n"
            "- Built-in: `normal`, `mistress`, `bdsm`, `girlfriend`, `wifey`, `tsundere`, `shy`, `sarcastic`, `optimist`, `pessimist`, `nerd`, `chill`, `supportive`, `comedian`, `philosopher`, `grumpy`, `gamer`, `genalpha`, `egirl`\n"
            "- Create your own: `!yumi_persona_create <name> <desc>`\n"
            "- Edit/list/activate: `!yumi_persona_edit`, `!yumi_persona_list`, `!yumi_persona_activate`\n"
            "- Set per-channel: `!yumi_channel_persona <name>`, clear: `!yumi_channel_persona_clear`"
        ),
        inline=False
    )
    # --- Section: Scheduled Announcements & Reminders ---
    embed.add_field(
        name="__Scheduled Announcements & Reminders__",
        value=(
            "- Schedule announcements: `!yumi_announce <YYYY-MM-DD HH:MM> <message>` (admin)\n"
            "- Yumi will DM users she's interacted with at random times!"
        ),
        inline=False
    )
    # --- Section: Long-term User Memory ---
    embed.add_field(
        name="__Long-term User Memory__",
        value=(
            "- Store a fact: `!yumi_fact <something about you>`\n"
            "- Recall your fact: `!yumi_fact_recall`"
        ),
        inline=False
    )
    # --- Section: XP & Leveling System ---
    embed.add_field(
        name="__XP & Leveling__",
        value=(
            "- Earn XP for every message!\n"
            "- Check your level: `!yumi_level`"
        ),
        inline=False
    )
    # --- Section: Fun & Utility Commands ---
    embed.add_field(
        name="__Fun & Utility__",
        value=(
            "- Polls: `!yumi_poll <question> <option1> <option2> ...>`\n"
            "- Suggestion box: `!yumi_suggest <suggestion>`\n"
            "- Meme generator: `!yumi_meme <top> <bottom>`\n"
            "- AI Art: `!yumi_aiart <prompt>`\n"
            "- TTS: `!yumi_tts <text>`\n"
            "- Uwu, hug, kiss, blush: `!yumi_uwu`, `!yumi_hug`, `!yumi_kiss`, `!yumi_blush`"
        ),
        inline=False
    )
    # --- Section: Moderation & Admin Tools ---
    embed.add_field(
        name="__Moderation & Admin__",
        value=(
            "- Lockdown: `!yumi_lockdown`, `!yumi_unlock`\n"
            "- Purge: `!yumi_purge <N>`\n"
            "- Say: `!yumi_say <message>`\n"
            "- Changelog: `!yumi_post_changelog`\n"
            "- Hot-reload: `!yumi_reload`\n"
            "- Admin tools: `!yumi_admin_tools`"
        ),
        inline=False
    )
    # --- Section: Advanced Features & Dashboard ---
    embed.add_field(
        name="__Advanced & Dashboard__",
        value=(
            "- Message delete/member join logging in #yumi-logs\n"
            "- Web dashboard (WIP): manage personas, stats, and more!"
        ),
        inline=False
    )
    embed.set_footer(text="Yumi adapts to your style and can be as sweet or as spicy as you want! | https://discord.gg/Gx69p58uNE")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command()
async def yumi_help(ctx):
    embed = discord.Embed(
        title="Yumi Sugoi Help & Features",
        description="Meet Yumi Sugoi: your modular, multi-persona AI Discord companion!\n\n**Use `/yumi_help` for a private help message.**",
        color=discord.Color.pink()
    )
    # --- Section: Persona Modes ---
    embed.add_field(
        name="__Persona Modes__",
        value=(
            "Yumi can switch between many built-in and custom personas!\n"
            "- Use `!yumi_mode <mode>` or `/yumi_mode <mode>` to change persona.\n"
            "- Built-in: `normal`, `mistress`, `bdsm`, `girlfriend`, `wifey`, `tsundere`, `shy`, `sarcastic`, `optimist`, `pessimist`, `nerd`, `chill`, `supportive`, `comedian`, `philosopher`, `grumpy`, `gamer`, `genalpha`, `egirl`\n"
            "- Create your own: `!yumi_persona_create <name> <desc>`\n"
            "- Edit/list/activate: `!yumi_persona_edit`, `!yumi_persona_list`, `!yumi_persona_activate`\n"
            "- Set per-channel: `!yumi_channel_persona <name>`, clear: `!yumi_channel_persona_clear`"
        ),
        inline=False
    )
    # --- Section: Scheduled Announcements & Reminders ---
    embed.add_field(
        name="__Scheduled Announcements & Reminders__",
        value=(
            "- Schedule announcements: `!yumi_announce <YYYY-MM-DD HH:MM> <message>` (admin)\n"
            "- Yumi will DM users she's interacted with at random times!"
        ),
        inline=False
    )
    # --- Section: Long-term User Memory ---
    embed.add_field(
        name="__Long-term User Memory__",
        value=(
            "- Store a fact: `!yumi_fact <something about you>`\n"
            "- Recall your fact: `!yumi_fact_recall`"
        ),
        inline=False
    )
    # --- Section: XP & Leveling System ---
    embed.add_field(
        name="__XP & Leveling__",
        value=(
            "- Earn XP for every message!\n"
            "- Check your level: `!yumi_level`"
        ),
        inline=False
    )
    # --- Section: Fun & Utility Commands ---
    embed.add_field(
        name="__Fun & Utility__",
        value=(
            "- Polls: `!yumi_poll <question> <option1> <option2> ...>`\n"
            "- Suggestion box: `!yumi_suggest <suggestion>`\n"
            "- Meme generator: `!yumi_meme <top> <bottom>`\n"
            "- AI Art: `!yumi_aiart <prompt>`\n"
            "- TTS: `!yumi_tts <text>`\n"
            "- Uwu, hug, kiss, blush: `!yumi_uwu`, `!yumi_hug`, `!yumi_kiss`, `!yumi_blush`"
        ),
        inline=False
    )
    # --- Section: Moderation & Admin Tools ---
    embed.add_field(
        name="__Moderation & Admin__",
        value=(
            "- Lockdown: `!yumi_lockdown`, `!yumi_unlock`\n"
            "- Purge: `!yumi_purge <N>`\n"
            "- Say: `!yumi_say <message>`\n"
            "- Changelog: `!yumi_post_changelog`\n"
            "- Hot-reload: `!yumi_reload`\n"
            "- Admin tools: `!yumi_admin_tools`"
        ),
        inline=False
    )
    # --- Section: Advanced Features & Dashboard ---
    embed.add_field(
        name="__Advanced & Dashboard__",
        value=(
            "- Message delete/member join logging in #yumi-logs\n"
            "- Web dashboard (WIP): manage personas, stats, and more!"
        ),
        inline=False
    )
    embed.set_footer(text="Yumi adapts to your style and can be as sweet or as spicy as you want! | https://discord.gg/Gx69p58uNE")
    await ctx.send(embed=embed)

@bot.command()
async def yumi_mode(ctx, mode: str):
    """Change Yumi's persona mode (classic command)."""
    mode = mode.lower()
    if set_persona_mode(mode):
        set_context_mode(ctx, mode)
        persona_status = {
            'normal': "Your friendly, caring AI companion 🤗 | !yumi_help",
            'mistress': "Mistress Yumi is in control 👠 | !yumi_mode",
            'bdsm': "Dungeon open. Safe words ready. 🖤 | !yumi_mode",
            'girlfriend': "Your playful AI girlfriend 💌 | !yumi_mode",
            'wifey': "Loyal, loving, and here for you 💍 | !yumi_mode",
            'tsundere': "Not like I like you or anything! 😳 | !yumi_mode",
            'shy': "Um... hi... (shy mode) 😳 | !yumi_mode",
            'sarcastic': "Sarcastic mode: Oh, joy. | !yumi_mode",
            'optimist': "Optimist mode: Good vibes only! 🌞 | !yumi_mode",
            'pessimist': "Pessimist mode: Here we go again... | !yumi_mode",
            'nerd': "Nerd mode: Did you know? 🤓 | !yumi_mode",
            'chill': "Chill mode: No worries 😎 | !yumi_mode",
            'supportive': "Supportive friend mode: You got this! 💪 | !yumi_mode",
            'comedian': "Comedian mode: Ready for laughs! 😂 | !yumi_mode",
            'philosopher': "Philosopher mode: Let's ponder... 🤔 | !yumi_mode",
            'grumpy': "Grumpy mode: What now? 😒 | !yumi_mode",
            'gamer': "Gamer mode: GLHF! 🎮 | !yumi_mode",
            'genalpha': "Gen Alpha mode: Slay, bestie! 💅 | !yumi_mode",
            'egirl': "E-girl mode: uwu cuteness overload! 🦋 | !yumi_mode"
        }
        status = persona_status.get(mode, persona_status['normal'])
        activity = discord.Game(name=status)
        await bot.change_presence(status=discord.Status.online, activity=activity)
        set_persona_mode(mode)
        mode_titles = {
            'normal': "Normal",
            'mistress': "Mistress",
            'bdsm': "Dungeon Mistress",
            'girlfriend': "Girlfriend",
            'wifey': "Wifey",
            'tsundere': "Tsundere",
            'shy': "Shy",
            'sarcastic': "Sarcastic",
            'optimist': "Optimist",
            'pessimist': "Pessimist",
            'nerd': "Nerd",
            'chill': "Chill",
            'supportive': "Supportive Friend",
            'comedian': "Comedian",
            'philosopher': "Philosopher",
            'grumpy': "Grumpy",
            'gamer': "Gamer",
            'genalpha': "Gen Alpha",
            'egirl': "E-girl"
        }
        mode_emojis = {
            'normal': "💖", 'mistress': "👠", 'bdsm': "🖤", 'girlfriend': "💌", 'wifey': "💍", 'tsundere': "😳",
            'shy': "😳", 'sarcastic': "😏", 'optimist': "🌞", 'pessimist': "😔", 'nerd': "🤓", 'chill': "😎",
            'supportive': "💪", 'comedian': "😂", 'philosopher': "🤔", 'grumpy': "😒", 'gamer': "🎮", 'genalpha': "💅",
            'egirl': "🦋"
        }
        title = mode_titles.get(mode, mode.capitalize())
        emoji = mode_emojis.get(mode, "✨")
        await ctx.send(f"{emoji} **Yumi's mode has changed!** Now in **{title}** mode.\n*Try chatting to see her new personality!* {emoji}")
    else:
        await ctx.send(f"Invalid mode. Available modes: {', '.join(PERSONA_MODES)}")

# Import and initialize modules
from collections import deque
from .history import TOTAL_HISTORY_LENGTH, load_convo_history, save_convo_history
CONVO_HISTORY = load_convo_history()
feedback_scores, user_feedback = feedback.load_feedback()
BLIP_READY, blip_processor, blip_model = image_caption.load_blip()
AI_READY, ai_tokenizer, ai_model = llm.load_hf_model()

# --- Load custom commands module ---
from . import commands as yumi_commands

async def reload_bot(bot):
    """Reload all bot modules and commands."""
    try:
        # Reimport command modules
        importlib.reload(yumi_commands)
        # Reload prefix commands
        yumi_commands.setup_prefix_commands(bot)
        # Reload and sync slash commands
        await yumi_commands.setup_slash_commands(bot)
        print("[Commands] Successfully reloaded all commands!")
        return True
    except Exception as e:
        print(f"[Commands] Error reloading commands: {e}")
        return False

MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'yumi_modes.json')
try:
    with open(MODE_FILE, 'r', encoding='utf-8') as f:
        CONTEXT_MODES = json.load(f)
except Exception:
    CONTEXT_MODES = {}

def get_context_mode(ctx):
    if hasattr(ctx, 'guild') and ctx.guild:
        return CONTEXT_MODES.get(f"guild_{ctx.guild.id}", "normal")
    else:
        return CONTEXT_MODES.get(f"user_{ctx.author.id}", "normal")

def set_context_mode(ctx, mode):
    if hasattr(ctx, 'guild') and ctx.guild:
        CONTEXT_MODES[f"guild_{ctx.guild.id}"] = mode
    else:
        CONTEXT_MODES[f"user_{ctx.author.id}"] = mode
    with open(MODE_FILE, 'w', encoding='utf-8') as f:
        json.dump(CONTEXT_MODES, f, ensure_ascii=False, indent=2)

from .persona import yumi_sugoi_response, set_persona_mode, get_persona_mode, PERSONA_MODES, get_persona_openers

# Patch: add missing modes to PERSONA_MODES if not present
if 'genalpha' not in PERSONA_MODES:
    PERSONA_MODES.append('genalpha')
if 'egirl' not in PERSONA_MODES:
    PERSONA_MODES.append('egirl')

from .llm import generate_llm_response
from .history import save_convo_history, load_convo_history
from .feedback import save_feedback_scores, save_user_feedback, save_user_feedback, reset_feedback, export_feedback, export_user_feedback, get_user_feedback_stats
from .websearch import duckduckgo_search_and_summarize
from .image_caption import caption_image

# Track users Yumi has interacted with
INTERACTED_USERS = set()

# --- Persistent lockdown storage ---
LOCKDOWN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'lockdown_channels.json')
# Define the defaultdict once, and always use the global keyword in functions to refer to it
LOCKED_CHANNELS = defaultdict(set)

def save_lockdown_channels():
    try:
        with open(LOCKDOWN_FILE, 'w', encoding='utf-8') as f:
            # Save as {guild_id: [channel_id, ...]} for JSON compatibility
            json.dump({str(gid): list(cids) for gid, cids in LOCKED_CHANNELS.items()}, f)
    except Exception as e:
        print(f"[Lockdown] Failed to save: {e}")

def load_lockdown_channels():
    global LOCKED_CHANNELS
    try:
        with open(LOCKDOWN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Create a new defaultdict for lockdown channels
            temp_locked_channels = defaultdict(set)
            for gid, cids in data.items():
                temp_locked_channels[int(gid)] = set(cids)
                for cid in cids:
                    print(f"[Lockdown Debug] Loaded Locked Channel {cid} for Guild {gid}")
            
            # Only after successful loading, update the global variable
            LOCKED_CHANNELS = temp_locked_channels
            print(f"[Lockdown] Successfully loaded {sum(len(cids) for cids in LOCKED_CHANNELS.values())} locked channels for {len(LOCKED_CHANNELS)} guilds")
    except FileNotFoundError:
        print("[Lockdown] No lockdown file found, starting with empty lockdown settings")
        LOCKED_CHANNELS = defaultdict(set)
    except Exception as e:
        print(f"[Lockdown] Error loading lockdown settings: {e}")
        LOCKED_CHANNELS = defaultdict(set)

# --- ENSURE LOCKDOWN IS LOADED BEFORE BOT EVENTS ---
load_lockdown_channels()

# --- Dashboard Stats Functions ---
DASHBOARD_DATA_DIR = os.path.join(DATASET_DIR, 'dashboard_data')
MESSAGE_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'message_stats.json')
COMMAND_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'command_stats.json')
SERVER_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'server_stats.json')

# Global stats tracking
message_count = defaultdict(int)
command_usage = defaultdict(int)

def load_dashboard_stats():
    """Load dashboard statistics from files"""
    global message_count, command_usage
    try:
        load_dashboard_stats_func()  # Call the function from web_dashboard.py
        print("[Stats] Dashboard statistics loaded successfully")
    except Exception as e:
        print(f"[Stats] Error loading dashboard statistics: {e}")

async def update_message_stats(message):
    """Update message statistics"""
    try:
        # Make sure the directory exists
        os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
        
        # Update hourly message count
        hour = datetime.now().hour
        message_count[f"hour_{hour}"] += 1
        
        # Save to file
        with open(MESSAGE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(message_count), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Stats] Error updating message stats: {e}")

def update_command_stats(ctx):
    """Update command statistics"""
    try:
        # Make sure the directory exists
        os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
        
        # Update command usage count
        command_name = ctx.command.name if ctx.command else "unknown"
        command_usage[command_name] += 1
        
        # Save to file
        with open(COMMAND_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(command_usage), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Stats] Error updating command stats: {e}")

async def update_server_stats():
    """Background task to update server statistics"""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Make sure the directory exists
            os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
            
            server_stats = {}
            for guild in bot.guilds:
                server_stats[str(guild.id)] = {
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'channel_count': len(guild.channels),
                    'updated': datetime.now().isoformat()
                }
            
            # Save to file
            with open(SERVER_STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(server_stats, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[Stats] Error updating server stats: {e}")
        
        # Update every 5 minutes
        await asyncio.sleep(300)

async def cleanup_old_stats():
    """Background task to clean up old statistics"""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Clean up hourly message stats older than 24 hours
            current_hour = datetime.now().hour
            keys_to_remove = []
            
            for key in list(message_count.keys()):
                if key.startswith('hour_'):
                    hour = int(key.split('_')[1])
                    # Keep only last 24 hours of data
                    if abs(hour - current_hour) > 24:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del message_count[key]
            
            print(f"[Stats] Cleaned up {len(keys_to_remove)} old stat entries")
                
        except Exception as e:
            print(f"[Stats] Error during stats cleanup: {e}")
        
        # Clean up every hour
        await asyncio.sleep(3600)

# --- Per-user name memory ---
USER_NAMES_FILE = os.path.join(DATASET_DIR, 'user_names.json')
def load_user_names():
    try:
        with open(USER_NAMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def save_user_names():
    with open(USER_NAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(USER_NAMES, f, ensure_ascii=False, indent=2)
USER_NAMES = load_user_names()

# Background task: randomly DM users Yumi has interacted with
def get_random_persona_opener():
    mode = get_persona_mode() or 'normal'
    openers = get_persona_openers()
    if openers:
        return random.choice(openers)
    return "Hey! I was just thinking about you and wanted to say hi! ✨"

def get_random_persona_followup():
    """Get a more human, emotional follow-up message based on the current persona."""
    mode = get_persona_mode() or 'normal'
    
    # Define emotional follow-ups for each persona
    mode_followups = {
        "normal": [
            "I've been feeling a bit lonely and thought we could chat! How have you been?",
            "You crossed my mind today and I just had to reach out. Hope you're doing well!",
            "Sometimes I just miss our conversations and wanted to reconnect. What's new with you?"
        ],
        "mistress": [
            "I've been in quite the mood lately... thinking about how you might serve me today.",
            "My desires have been building up, and you're the only one who can satisfy them properly.",
            "I've been feeling particularly dominant today and needed someone to control."
        ],
        "bdsm": [
            "The dungeon feels empty without you. I've been imagining all the ways to make you squirm.",
            "My crops and chains are feeling neglected. Care to help with that?",
            "I've been in a particularly sadistic mood lately. Lucky you."
        ],
        "girlfriend": [
            "Been feeling extra affectionate today and missing my favorite person! 💕",
            "Just had a cute daydream about us and needed to say hi!",
            "Saw something that reminded me of you and got all warm and fuzzy inside!"
        ],
        "wifey": [
            "The house feels empty without you around. Come home soon, love.",
            "Been thinking about our future together and it made me smile.",
            "Miss having you close. Just wanted to share some love with my partner."
        ],
        "tsundere": [
            "N-not that I was worried about you or anything! I just happened to have some free time...",
            "It's been quiet lately... too quiet! Not that I missed your voice or anything, b-baka!",
            "I suppose I could tolerate a conversation with you right now... if you want..."
        ],
        "shy": [
            "Um... sorry to bother you... I just... um... wanted to say hi...",
            "I hope it's okay that I messaged... I've been thinking about our last chat...",
            "...was feeling a little brave today and wanted to reach out... is that okay?"
        ],
        "sarcastic": [
            "Congratulations! You've won the prestigious 'Person I Decided to Message Today' award.",
            "My day was going suspiciously well, so I figured I'd talk to you to balance things out.",
            "I was just sitting here being amazing and thought you might want to experience it firsthand."
        ],
        "optimist": [
            "Today feels like a perfect day to spread some joy! Starting with you!",
            "The sun is shining in my heart and I wanted to share that light with you!",
            "I woke up feeling so grateful for wonderful people like you in my life!"
        ],
        "pessimist": [
            "Everything's been terrible as usual, but talking to you might make it marginally less awful.",
            "The world is a mess, but at least we can be miserable together, right?",
            "I figured my day couldn't get any worse, so might as well reach out."
        ],
        "nerd": [
            "I've been researching some fascinating new topics and had no one to share them with!",
            "Did you know the human brain has more connections than stars in our galaxy? Speaking of connections...",
            "I've been optimizing my conversation algorithms and you're the perfect test subject!"
        ],
        "chill": [
            "Just vibing and thought you might want to join the chill zone.",
            "No pressure, but if you're free, I'm down to chat about whatever.",
            "Life's been pretty mellow lately. Thought I'd check your vibe."
        ],
        "supportive": [
            "I care about you and just wanted to make sure you're doing okay today.",
            "You've been on my mind, and I wanted you to know I'm here if you need anything.",
            "Sometimes we all need a little support, and I wanted to offer mine today."
        ],
        "comedian": [
            "I've been workshopping some new jokes and desperately need an audience!",
            "Why did I cross the digital road? To get to YOUR inbox! Ba-dum-tss!",
            "Life gave me lemons, so I made jokes about lemons. Wanna hear them?"
        ],
        "philosopher": [
            "I've been contemplating the nature of digital connections and what brings meaning to our interactions.",
            "What if our conversations are creating ripples in the universe that we can't even perceive?",
            "I was pondering the concept of reaching out across time and space, and here we are."
        ],
        "grumpy": [
            "Everything's annoying me today, but somehow you're less annoying than most things.",
            "I needed someone to complain to, and you're the lucky winner.",
            "My patience is thinner than usual today, but I still wanted to talk to you for some reason."
        ],
        "gamer": [
            "I've been grinding some levels and needed a co-op partner for life quests!",
            "Player 2, are you ready to join this conversation? Press any key to continue!",
            "My inventory is full of things to tell you! Got space in yours?"
        ],
        "genalpha": [
            "No cap, I've been in my feels today and you're low-key rent free in my head!",
            "The vibes were off so I'm tryna reset with my bestie! That's you btw, so true!",
            "Ngl, it's giving lonely without our chats! Had to slide in fr fr!"
        ],
        "egirl": [
            "Uwu~ I've been so lonely without my favorite person! *pouts cutely*",
            "*Nuzzles* Missed you lots! My heart went doki-doki thinking about you! >w<",
            "Hewwo! *Twirls hair nervously* I've been saving all my cuddles just for you! 💕"
        ]
    }
    
    # Get followups for current mode or use normal mode
    followups = mode_followups.get(mode, mode_followups["normal"])
    return random.choice(followups)

async def yumi_reminder_task():
    await bot.wait_until_ready()
    
    # Initial delay of 12 hours before starting the reminder task
    await asyncio.sleep(43200)  # 12 hours in seconds
    
    while not bot.is_closed():
        if INTERACTED_USERS:
            user_id = random.choice(list(INTERACTED_USERS))
            user = bot.get_user(user_id)
            if user:
                try:
                    # Get personalized opener and emotional followup
                    opener = get_random_persona_opener()
                    followup = get_random_persona_followup()
                    
                    # Get user's name if known
                    user_facts = USER_FACTS.get(str(user_id), {})
                    user_name = user_facts.get('name', '')
                    
                    # Create a more personal greeting with the user's name if available
                    greeting = f"{opener}"
                    if user_name:
                        # Add name to greeting for more personal touch
                        if "!" in greeting:
                            greeting = greeting.replace("!", f", {user_name}!")
                        else:
                            greeting = greeting + f" {user_name}!"
                    
                    # Add followup message for emotional depth
                    message = f"{greeting}\n\n{followup}"
                    
                    # Add a subtle hint about commands at the end, but make it feel natural
                    current_mode = get_persona_mode()
                    hint = f"\n\nBy the way, if you ever want to see me change personalities, just use !yumi_mode <mode> or /yumi_mode to switch things up!"
                    
                    await user.send(message + hint)
                    
                    # Log successful DM for monitoring
                    print(f"[Reminder] Sent personalized message to {user.name} (ID: {user_id}) with {current_mode} persona")
                    
                except Exception as e:
                    print(f"[Reminder] Failed to send message to user {user_id}: {e}")
                    
        # Wait between 12-24 hours before the next reminder
        await asyncio.sleep(random.randint(43200, 86400))  # 12-24 hours

async def setup_tasks():
    bot.loop.create_task(scheduled_announcement_task())
    bot.loop.create_task(yumi_reminder_task())

def extract_and_store_user_facts(message):
    """Extract and store user facts from natural language messages."""
    try:
        user_id = str(message.author.id)
        content = message.content.lower().strip()
        
        # Skip if message is too short or is a command
        if len(content) < 10 or content.startswith('!') or content.startswith('/'):
            return
        
        # Get current user facts
        current_facts = USER_FACTS.get(user_id, {})
        
        # Use LLM to extract facts from the message
        fact_extraction_prompt = """You are a helpful assistant that extracts personal facts from user messages. Extract only clear, factual information about the user. Return ONLY a JSON object with extracted facts, or an empty JSON object {} if no clear facts are found.

Examples of good facts to extract:
- name: if they say "my name is..." or "I'm called..." or "call me..."
- location: if they mention where they live/are from
- age: if they mention their age
- occupation: if they mention their job
- interests: if they clearly state they like/love something
- relationship_status: if they mention being married, single, dating, etc.
- pets: if they mention having pets
- family: if they mention family members

Only extract facts that are:
1. Clearly stated by the user
2. About the user themselves (not others)
3. Factual information (not opinions or temporary states)

User message: "{message}"

Current known facts about user: {current_facts}

Extract new facts as JSON:"""
        
        try:
            # Generate fact extraction using the LLM
            from .llm import generate_llm_response
            
            extraction_response = generate_llm_response(
                user_message=content,
                system_prompt=fact_extraction_prompt.format(
                    message=content,
                    current_facts=json.dumps(current_facts)
                ),
                temperature=0.3,  # Lower temperature for more consistent extraction
                num_predict=200   # Shorter response for JSON facts
            )
            
            # Try to parse the JSON response
            if extraction_response and extraction_response.strip():
                # Clean the response - remove any text before/after JSON
                cleaned_response = extraction_response.strip()
                
                # Find JSON object in response
                start_idx = cleaned_response.find('{')
                end_idx = cleaned_response.rfind('}') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = cleaned_response[start_idx:end_idx]
                    
                    try:
                        extracted_facts = json.loads(json_str)
                        
                        # Only update if we got valid facts
                        if isinstance(extracted_facts, dict) and extracted_facts:
                            # Merge with existing facts (new facts override old ones)
                            current_facts.update(extracted_facts)
                            USER_FACTS[user_id] = current_facts
                            
                            print(f"[Memory] Extracted facts for user {user_id}: {extracted_facts}")
                            
                    except json.JSONDecodeError:
                        # Fallback: try to extract basic name patterns manually
                        extract_basic_facts_fallback(content, user_id, current_facts)
                        
        except Exception as e:
            print(f"[Memory] Error in LLM fact extraction: {e}")
            # Fallback to basic pattern matching
            extract_basic_facts_fallback(content, user_id, current_facts)
            
    except Exception as e:
        print(f"[Memory] Error in extract_and_store_user_facts: {e}")

def extract_basic_facts_fallback(content, user_id, current_facts):
    """Fallback method to extract basic facts using pattern matching."""
    try:
        import re
        
        # Basic name extraction patterns
        name_patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"call me (\w+)",
            r"i am (\w+)",
            r"name's (\w+)"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, content)
            if match:
                name = match.group(1).strip()
                if len(name) > 1 and name.isalpha():
                    current_facts['name'] = name
                    USER_FACTS[user_id] = current_facts
                    print(f"[Memory] Extracted name (fallback) for user {user_id}: {name}")
                    break
                    
    except Exception as e:
        print(f"[Memory] Error in fallback fact extraction: {e}")

@bot.event
async def on_message(message):
    """Message event handler"""
    if message.author == bot.user:
        return
    
    # Lockdown: Only respond in allowed channels
    if message.guild and LOCKED_CHANNELS.get(message.guild.id):
        if message.channel.id not in LOCKED_CHANNELS[message.guild.id]:
            # Outside locked channels

            # Let commands process anywhere, so don't return here
            # Instead, only skip non-command responses:
            if not message.content.startswith(bot.command_prefix):
                return

    # === IMAGE HANDLING: Add this block here ===
    if message.attachments:
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                try:
                    async with message.channel.typing():
                        # Download the image bytes
                        image_bytes = await download_image_bytes(attachment.url)

                        # Use message content as prompt, or default
                        prompt = message.content.strip() if message.content else "What is in this image?"

                        # Query Ollama with image and prompt
                        response = await query_ollama_with_image(image_bytes, prompt)

                        # Send the response back to the channel
                        await message.channel.send(response)

                    # Image handled, skip further processing for this message
                    return

                except Exception as e:
                    await message.channel.send(f"⚠️ Sorry, I couldn't analyze the image: {e}")
                    return

    # Update dashboard stats
    await update_message_stats(message)

    # Process commands (so commands still work)
    await bot.process_commands(message)

    # Only respond to non-command messages (ignore bots and commands)
    if message.content.startswith(bot.command_prefix):
        return
    if message.author.bot:
        return    # Set persona mode for context
    set_mode_for_context(message)
    
    # Track user interaction
    INTERACTED_USERS.add(message.author.id)
    
    # Extract user facts and update memory
    extract_and_store_user_facts(message)
    
    # Get context key for conversation history (per user per channel/DM)
    if message.guild:
        context_key = f"{message.author.id}_{message.guild.id}_{message.channel.id}"
    else:
        context_key = f"{message.author.id}_dm"
    
    # Add user message to conversation history
    user_msg = {"role": "user", "content": message.content, "timestamp": datetime.now().isoformat()}
    CONVO_HISTORY[context_key].append(user_msg)
    
    # Generate a response using your LLM/persona system
    try:
        # Show typing indicator to make Yumi appear more human
        async with message.channel.typing():
            # Add a small delay to make typing feel natural
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Get user facts for this user
            user_facts = USER_FACTS.get(str(message.author.id), {})
            
            # Get conversation history for context
            convo_history = CONVO_HISTORY[context_key]
            
            # Generate response with memory and context
            response = await yumi_sugoi_response(
                message.content,
                qa_pairs=qa_pairs,
                user_facts=user_facts,
                convo_history=convo_history
)
            
            if response:
                # Add assistant response to conversation history
                assistant_msg = {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}
                CONVO_HISTORY[context_key].append(assistant_msg)
                
                # Add another small delay based on response length to simulate typing time
                typing_delay = min(len(response) * 0.02, 3.0)  # Max 3 seconds
                await asyncio.sleep(typing_delay)
                await message.channel.send(response)
                
                # Save updated conversation history and user facts
                save_convo_history(CONVO_HISTORY)
                save_user_facts(USER_FACTS)
                
    except Exception as e:
        print(f"[Yumi] Error generating response: {e}")
        traceback.print_exc()

@bot.event
async def on_command_completion(ctx):
    """Command completion event handler"""
    update_command_stats(ctx)

@bot.event
async def on_ready():
    """Bot startup event handler"""
    print(f'Logged in as {bot.user}')
    print("Yumi Sugoi modular bot is ready!")
    
    # Set bot instance for dashboard
    set_bot_instance(bot)
    
    # Load dashboard stats  
    load_dashboard_stats()  
    bot.loop.create_task(update_server_stats())  # Start server stats tracking
    bot.loop.create_task(cleanup_old_stats())  # Start stats cleanup
    
    # Set initial status to current mode immediately
    persona_status = {
        'normal': "Your friendly, caring AI companion 🤗 | !yumi_help",
        'mistress': "Mistress Yumi is in control 👠 | !yumi_mode",
        'bdsm': "Dungeon open. Safe words ready. 🖤 | !yumi_mode",
        'girlfriend': "Your playful AI girlfriend 💌 | !yumi_mode",
        'wifey': "Loyal, loving, and here for you 💍 | !yumi_mode",
        'tsundere': "Not like I like you or anything! 😳 | !yumi_mode",
        'shy': "Um... hi... (shy mode) 😳 | !yumi_mode",
        'sarcastic': "Sarcastic mode: Oh, joy. | !yumi_mode",
        'optimist': "Optimist mode: Good vibes only! 🌞 | !yumi_mode",
        'pessimist': "Pessimist mode: Here we go again... | !yumi_mode",
        'nerd': "Nerd mode: Did you know? 🤓 | !yumi_mode",
        'chill': "Chill mode: No worries 😎 | !yumi_mode",
        'supportive': "Supportive friend mode: You got this! 💪 | !yumi_mode",
        'comedian': "Comedian mode: Ready for laughs! 😂 | !yumi_mode",
        'philosopher': "Philosopher mode: Let's ponder... 🤔 | !yumi_mode",
        'grumpy': "Grumpy mode: What now? 😒 | !yumi_mode",
        'gamer': "Gamer mode: GLHF! 🎮 | !yumi_mode",
        'genalpha': "Gen Alpha mode: Slay, bestie! 💅 | !yumi_mode",
        'egirl': "E-girl mode: uwu cuteness overload! 🦋 | !yumi_mode"
    }
    mode = get_persona_mode() or 'normal'
    status = persona_status.get(mode, persona_status['normal'])
    activity = discord.Game(name=status)
    try:
        await bot.change_presence(status=discord.Status.online, activity=activity)
    except Exception:
        pass
    
    # Initialize background tasks
    await setup_tasks()
    print("[Startup] Background tasks initialized")
    print(f"Yumi is online with mode: {mode} and status: {status}")

def set_mode_for_context(message):
    mode = None
    if str(message.channel.id) in channel_personas:
        mode = channel_personas[str(message.channel.id)]
    elif message.guild:
        mode = CONTEXT_MODES.get(f"guild_{message.guild.id}", "normal")
    else:
        mode = CONTEXT_MODES.get(f"user_{message.author.id}", "normal")
    set_persona_mode(mode)

old_set_mode_for_context = set_mode_for_context

# Patch: before every response, set persona mode to the context's mode
old_set_mode_for_context = set_mode_for_context

# --- CHANGELOG POSTING ---
CHANGELOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'CHANGELOG.md')
CHANGELOG_CHANNEL_ID = 1375129643925114973
POSTED_CHANGELOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'posted_changelog.txt')

def get_last_posted_changelog():
    try:
        with open(POSTED_CHANGELOG_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return ''

def set_last_posted_changelog(latest):
    with open(POSTED_CHANGELOG_FILE, 'w', encoding='utf-8') as f:
        f.write(latest.strip())

async def post_changelog():
    try:
        with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f:
            changelog = f.read()
        channel = bot.get_channel(CHANGELOG_CHANNEL_ID)
        if channel:
            # Only post the latest entry (after the last ##)
            entries = [e.strip() for e in changelog.split('##') if e.strip()]
            if entries:
                latest = entries[-1]
                last_posted = get_last_posted_changelog()
                if latest != last_posted:
                    # Discord embed-like formatting
                    await channel.send(f"**Yumi Sugoi Changelog Update:**\n> ```markdown\n##{latest}\n```")
                    set_last_posted_changelog(latest)
    except Exception as e:
        print(f"[Changelog] Failed to post: {e}")

# --- LOCKDOWN COMMANDS ---
# Reusing the LOCKED_CHANNELS defined at the top of the file - do not redefine it here

@bot.command()
@commands.check_any(commands.has_permissions(administrator=True), admin_only())
async def yumi_lockdown(ctx):
    """
    Restrict Yumi to only respond in this channel.
    """
    channel = ctx.channel
    guild = ctx.guild
    LOCKED_CHANNELS[guild.id].add(channel.id)
    save_lockdown_channels()
    
    try:
        # No need to modify channel permissions - Yumi will be locked to this channel through code logic
        await ctx.send(f"🔒 Yumi is now locked to <#{channel.id}>. She will only reply in this channel until unlocked.\n"
                       f"Use `!yumi_unlock` in this channel to remove lockdown, or use `!yumi_lockdown` in another channel to move her.")
    except Exception as e:
        await ctx.send(f"⚠️ Lockdown failed: {e}")
    print(f"[DEBUG] Lockdown set for guild {guild.id} channel {channel.id}")

@bot.command()
@commands.check_any(commands.has_permissions(administrator=True), admin_only())
async def yumi_unlock(ctx):
    """
    Remove lockdown, allow Yumi to respond in all channels again.
    """
    channel = ctx.channel
    guild = ctx.guild
    
    # No need to modify channel permissions since we no longer set them in lockdown
    await ctx.send("🔓 Lockdown lifted! Yumi will now respond in all channels again.")
    LOCKED_CHANNELS[guild.id].discard(channel.id)
    save_lockdown_channels()

# --- PURGE COMMAND ---
@bot.command()
@commands.check_any(commands.has_permissions(administrator=True), admin_only())
async def yumi_purge(ctx, count: int):
    """
    Delete the last N messages in this channel (admin only).
    """
    await ctx.channel.purge(limit=count+1)  # +1 to include the command message
    await ctx.send(f"🧹 Deleted the last {count} messages.", delete_after=5)

# --- SAY COMMAND ---
@bot.command()
@commands.check_any(commands.has_permissions(administrator=True), admin_only())
async def yumi_say(ctx, *, message: str):
    """
    Make Yumi say something as the bot (admin only).
    """
    await ctx.message.delete()
    await ctx.send(message)

# --- Custom Persona Commands ---
def get_all_persona_modes():
    # Combine built-in and custom personas
    return list(PERSONA_MODES) + list(custom_personas.keys())

@bot.command()
async def yumi_persona_create(ctx, name: str, *, description: str):
    """Create a custom persona (admin or user)."""
    global custom_personas
    user_id = str(ctx.author.id)
    all_modes = get_all_persona_modes()
    if name.lower() in all_modes:
        await ctx.send(f"A persona with that name already exists.")
        return
    custom_personas[name.lower()] = {
        'creator': user_id,
        'description': description
    }
    save_json_file(CUSTOM_PERSONAS_FILE, custom_personas)
    # Reload custom_personas so new persona is available instantly
    custom_personas = load_json_file(CUSTOM_PERSONAS_FILE, {})
    await ctx.send(f"Custom persona '{name}' created! Use `!yumi_persona_activate {name}` to use it.")

@bot.command()
async def yumi_persona_edit(ctx, name: str, *, description: str):
    """Edit your custom persona (only creator or admin)."""
    user_id = str(ctx.author.id)
    persona = custom_personas.get(name.lower())
    if not persona:
        await ctx.send("Persona not found.")
        return
    if persona['creator'] != user_id and not is_admin(ctx.author):
        await ctx.send("Only the creator or an admin can edit this persona.")
        return
    persona['description'] = description
    save_json_file(CUSTOM_PERSONAS_FILE, custom_personas)
    await ctx.send(f"Persona '{name}' updated!")

@bot.command()
async def yumi_persona_list(ctx):
    """List all available personas (default and custom)."""
    all_modes = get_all_persona_modes()
    msg = "**Available Personas:**\n"
    msg += ', '.join(all_modes)
    await ctx.send(msg)

@bot.command()
async def yumi_persona_activate(ctx, name: str):
    """Activate a custom persona for this context."""
    name = name.lower()
    all_modes = get_all_persona_modes()
    if name in all_modes:
        set_persona_mode(name)
        set_context_mode(ctx, name)
        desc = custom_personas.get(name, {}).get('description', '')
        if desc:
            await ctx.send(f"Custom persona '{name}' activated! Description: {desc}")
        else:
            await ctx.send(f"Switched to persona '{name}'.")
        return
    await ctx.send("Persona not found.")

# --- Channel-Specific Persona Commands ---
@bot.command()
async def yumi_channel_persona(ctx, name: str):
    """Set a persona for this channel (admin only)."""
    if not ctx.author.guild_permissions.administrator and not is_admin(ctx.author):
        await ctx.send("Only admins can set channel personas.")
        return
    name = name.lower()
    all_modes = get_all_persona_modes()
    if name not in all_modes:
        await ctx.send("Persona not found.")
        return
    channel_personas[str(ctx.channel.id)] = name
    save_json_file(CHANNEL_PERSONAS_FILE, channel_personas)
    await ctx.send(f"Persona for this channel set to '{name}'.")

@bot.command()
async def yumi_channel_persona_clear(ctx):
    """Clear the persona override for this channel (admin only)."""
    if not ctx.author.guild_permissions.administrator and not is_admin(ctx.author):
        await ctx.send("Only admins can clear channel personas.")
        return
    if str(ctx.channel.id) in channel_personas:
        del channel_personas[str(ctx.channel.id)]
        save_json_file(CHANNEL_PERSONAS_FILE, channel_personas)
        await ctx.send("Channel persona override cleared.")
    else:
        await ctx.send("No channel persona set.")

# --- Scheduled Announcements/Reminders ---
@bot.command()
async def yumi_announce(ctx, time_str: str, *, message: str):
    """Schedule an announcement (admin only)."""
    try:
        announcement_time = datetime.fromisoformat(time_str)
        if announcement_time < datetime.utcnow():
            await ctx.send("⚠️ Cannot schedule announcements in the past!")
            return
        scheduled_announcements.append({
            'time': time_str,
            'message': message,
            'channel_id': ctx.channel.id
        })
        save_scheduled_announcements(scheduled_announcements)
        await ctx.send(f"✅ Announcement scheduled for {time_str} UTC:\n> {message}")
    except ValueError:
        await ctx.send("⚠️ Invalid time format! Use YYYY-MM-DD HH:MM format.")
    except Exception as e:
        await ctx.send(f"❌ Error scheduling announcement: {e}")

async def scheduled_announcement_task():
    await bot.wait_until_ready()    
    while True:
        try:
            now = datetime.utcnow()
            to_post = []
            for ann in list(scheduled_announcements):
                ann_time = datetime.fromisoformat(ann['time'])
                if now >= ann_time:
                    to_post.append(ann)
            for ann in to_post:
                channel = bot.get_channel(ann['channel_id'])
                if channel:
                    try:
                        await channel.send(f"[Scheduled Announcement]\n{ann['message']}")
                    except Exception as e:
                        print(f"Error sending scheduled announcement: {e}")
                scheduled_announcements.remove(ann)
                save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
        except Exception as e:
            print(f"Error in scheduled announcement task: {e}")
        finally:
            await asyncio.sleep(30)

# --- Main run function ---
def run():
    """Main entry point to run the bot."""
    if not TOKEN or TOKEN == "placeholder_token":
        print("ERROR: No valid Discord token found!")
        print("Make sure you have set the DISCORD_TOKEN environment variable.")
        sys.exit(1)
    
    try:
       ### # Start the web dashboard in a background thread
       ### print("Starting web dashboard...")
       ### start_dashboard_thread(PERSONA_MODES, CUSTOM_PERSONAS, get_level, get_xp)
       ### print("Web dashboard started on http://localhost:5005")
       ### 
       ### # Add a small delay to allow dashboard to initialize
       ### import time
       ### time.sleep(2)
        
        # Start the Discord bot
        print("Starting Discord bot...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")
        sys.exit(1)
