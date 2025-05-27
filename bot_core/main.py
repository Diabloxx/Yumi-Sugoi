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
    return "Hey! This is a reminder from Yumi Sugoi!"

async def yumi_reminder_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        if INTERACTED_USERS:
            user_id = random.choice(list(INTERACTED_USERS))
            user = bot.get_user(user_id)
            if user:
                try:
                    opener = get_random_persona_opener()
                    await user.send(f"{opener}\n(This is a reminder from Yumi Sugoi! If you want to change my mode, use !yumi_mode <mode> or /yumi_mode.)")
                except Exception:
                    pass
        await asyncio.sleep(random.randint(3600, 10800))  # 1-3 hours

@bot.event
async def on_ready():
    """Bot startup event handler"""
    print(f"Bot is ready! Logged in as {bot.user.name}")
    load_dashboard_stats()  # Load existing stats
    bot.loop.create_task(update_server_stats())  # Start server stats tracking
    bot.loop.create_task(cleanup_old_stats())  # Start stats cleanup
    await setup_tasks()

async def setup_tasks():
    bot.loop.create_task(scheduled_announcement_task())
    bot.loop.create_task(yumi_reminder_task())

@bot.event
async def on_message(message):
    """Message event handler"""
    if message.author == bot.user:
        return
    
    # Update dashboard stats
    await update_message_stats(message)
    
    # Process commands
    await bot.process_commands(message)

@bot.event
async def on_command_completion(ctx):
    """Command completion event handler"""
    update_command_stats(ctx)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    print("Yumi Sugoi modular bot is ready!")
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
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")
        sys.exit(1)
