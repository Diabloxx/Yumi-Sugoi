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
        # Register slash commands
        self.tree.add_command(yumi_mode_slash)
        self.tree.add_command(yumi_help_slash)

bot = YumiBot(command_prefix='!', intents=intents)

@app_commands.command(name="yumi_mode", description="Change Yumi's persona mode (normal, mistress, bdsm, girlfriend, wifey, tsundere, shy, sarcastic, optimist, pessimist, nerd, chill, supportive, comedian, philosopher, grumpy, gamer, genalpha, egirl)")
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
    msg = f"""
**Yumi Sugoi Help**
Yumi is an AI chatbot with multiple personalities and modes!

**What can Yumi do?**
- Chat, flirt, tease, and roleplay in a variety of styles
- Respond to images with captions (if enabled)
- Learn new Q&A pairs from users (just teach her!)
- Remember conversation history for context
- Accept feedback via reactions
- Randomly DM users she's interacted with, to remind you she exists!

**Modes:**
- `normal`: Friendly, flirty, supportive waifu
- `mistress`: Dominant, elegant, playfully cruel, and commanding
- `bdsm`: Dungeon Mistress, strict, creative, and deeply kinky
- `girlfriend`: Loving, playful, and flirty
- `wifey`: Caring, nurturing, and loyal
- `tsundere`: Cold, easily flustered, but secretly caring ("I-It's not like I like you or anything!")
- `shy`: Hesitant, apologetic, and nervous
- `sarcastic`: Dry humor, witty comebacks, playful mockery
- `optimist`: Always positive and encouraging
- `pessimist`: Gloomy, expects the worst, self-deprecating
- `nerd`: Loves pop culture, science, and trivia
- `chill`: Relaxed, easygoing, unbothered
- `supportive`: Encouraging, gives advice, checks on you
- `comedian`: Loves to joke and make you laugh
- `philosopher`: Deep, thoughtful, asks big questions
- `grumpy`: Irritable, blunt, but honest
- `gamer`: Huge gamer nerd, uses gaming slang
- `genalpha`: Gen Alpha slang, trendy, and sassy
- `egirl`: E-girl, uwu, cuteness overload, lots of emojis and 'nya~'

**How to change Yumi's mode:**
Type `/yumi_mode <mode>` (e.g. `/yumi_mode shy`) in a server or DM. The mode is saved per server or per DM.

**How to teach Yumi:**
If she doesn't know how to respond, just reply with `<question> | <answer>` and she'll learn!

**How to get a reminder DM:**
Yumi will randomly DM users she's talked to, using a mode-appropriate opener.

**Available modes:**
{', '.join(PERSONA_MODES)}

Have fun! Yumi adapts to your style and can be as sweet or as spicy as you want.
"""
    await interaction.response.send_message(msg, ephemeral=True)

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
CONVO_HISTORY = history.load_convo_history()
feedback_scores, user_feedback = feedback.load_feedback()
BLIP_READY, blip_processor, blip_model = image_caption.load_blip()
AI_READY, ai_tokenizer, ai_model = llm.load_hf_model()

# --- Load custom commands module ---
from . import commands as yumi_commands

def load_all_custom_commands(bot):
    yumi_commands.setup_prefix_commands(bot)
    yumi_commands.setup_slash_commands(bot)

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
    await update_command_stats(ctx)

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
async def yumi_announce(ctx, when: str, *, message: str):
    """Schedule an announcement (admin only). Format: !yumi_announce YYYY-MM-DD HH:MM <message>"""
    if not ctx.author.guild_permissions.administrator and not is_admin(ctx.author):
        await ctx.send("Only admins can schedule announcements.")
        return
    try:
        dt = datetime.datetime.strptime(when, "%Y-%m-%d %H:%M")
    except Exception:
        await ctx.send("Invalid datetime format. Use YYYY-MM-DD HH:MM")
        return
    scheduled_announcements.append({
        'channel_id': ctx.channel.id,
        'time': dt.isoformat(),
        'message': message
    })
    save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
    await ctx.send(f"Announcement scheduled for {dt}.")

async def scheduled_announcement_task():
    await bot.wait_until_ready()    
    while True:  # Changed from bot.is_closed() check to True
        try:
            now = datetime.utcnow()
            to_post = []
            for ann in list(scheduled_announcements):
                ann_time = datetime.fromisoformat(ann['time'])
                if now >= ann_time:
                    to_post.append(ann)
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

# --- User Facts/Long-term Memory ---
@bot.command()
async def yumi_fact(ctx, *, fact: str):
    """Store a fact about yourself. Usage: !yumi_fact I like cats."""
    user_id = str(ctx.author.id)
    user_facts[user_id] = fact
    save_json_file(USER_FACTS_FILE, user_facts)
    await ctx.send(f"Got it! I'll remember: {fact}")

@bot.command()
async def yumi_fact_recall(ctx):
    """Recall your stored fact."""
    user_id = str(ctx.author.id)
    fact = user_facts.get(user_id)
    if fact:
        await ctx.send(f"You told me: {fact}")
    else:
        await ctx.send("I don't have any facts stored for you yet. Use !yumi_fact <something> to teach me.")

# --- XP/Leveling System ---
def add_xp(user_id, amount=1):
    user_id = str(user_id)
    user_xp.setdefault(user_id, {'xp': 0, 'level': 1})
    user_xp[user_id]['xp'] += amount
    # Level up every 100 XP
    while user_xp[user_id]['xp'] >= user_xp[user_id]['level'] * 100:
        user_xp[user_id]['xp'] -= user_xp[user_id]['level'] * 100
        user_xp[user_id]['level'] += 1
    save_json_file(USER_XP_FILE, user_xp)

def get_level(user_id):
    user_id = str(user_id)
    return user_xp.get(user_id, {'level': 1})['level']

def get_xp(user_id):
    user_id = str(user_id)
    return user_xp.get(user_id, {'xp': 0})['xp']

@bot.command()
async def yumi_level(ctx):
    """Show your current level and XP."""
    user_id = str(ctx.author.id)
    level = get_level(user_id)
    xp = get_xp(user_id)
    await ctx.send(f"Level: {level} | XP: {xp}/{level*100}")

def get_history_key(message):
    if message.guild:
        # Per-user-in-server context
        return f"guild_{message.guild.id}_user_{message.author.id}"
    else:
        # DM context
        return f"user_{message.author.id}"

# --- Analytics Data Storage ---
message_count = defaultdict(int)
command_usage = defaultdict(int)

def track_message(message):
    """Track message analytics"""
    hour = datetime.now().hour
    day = datetime.now().weekday()
    
    message_count[f"hour_{hour}"] += 1
    message_count[f"day_{day}"] += 1
    message_count[f"channel_{message.channel.id}"] += 1
    message_count['total'] += 1

def track_command(command_name):
    """Track command usage"""
    command_usage[command_name] += 1

@bot.event
async def on_message(message):
    if message.author.bot:
        track_message(message)
        return
    track_message(message)
    if message.guild:
        guild_locked_channels = LOCKED_CHANNELS[message.guild.id]
        if guild_locked_channels and message.channel.id not in guild_locked_channels:
            await bot.process_commands(message)
            return
    current_mode = channel_personas.get(str(message.channel.id)) or get_context_mode(message)
    await update_message_stats(message)
    ctx = await bot.get_context(message)
    if ctx.valid:
        update_command_stats(ctx)  # <-- Remove 'await' here, as update_command_stats is not async
        await bot.process_commands(message)
        return
    try:
        user_id = str(message.author.id)
        extract_user_facts_from_message(user_id, message.content)
        # --- Per-user conversation memory key ---
        if message.guild:
            history_key = f"guild_{message.guild.id}_user_{user_id}_channel_{message.channel.id}"
        else:
            history_key = f"dm_user_{user_id}"
        if history_key not in CONVO_HISTORY:
            CONVO_HISTORY[history_key] = deque(maxlen=10)
        channel_history = CONVO_HISTORY[history_key]
        if is_new_topic(message.content):
            channel_history.clear()
            save_convo_history(CONVO_HISTORY)
            await message.channel.send("Okay! Let's start a new topic. What would you like to talk about?")
            return
        channel_history.append({
            'role': 'user',
            'content': message.content,
            'author': str(message.author.name)
        })
        save_convo_history(CONVO_HISTORY)
        image_context = ""
        if message.attachments and BLIP_READY:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as response:
                                img_bytes = await response.read()
                                caption = caption_image(blip_processor, blip_model, img_bytes)
                                if caption:
                                    image_context = f"\n[Attached image shows: {caption}]"
                    except Exception as e:
                        print(f"Error captioning image: {e}")
        user_facts_for_llm = user_facts.get(user_id, {}) if isinstance(user_facts.get(user_id), dict) else {}
        print(f"[DEBUG] Facts for LLM for {user_id}: {user_facts_for_llm}")
        convo_pairs = []
        for entry in list(channel_history)[-10:]:
            if entry['role'] == 'user':
                convo_pairs.append({'user': entry['content'], 'bot': ''})
            elif entry['role'] == 'assistant' and convo_pairs:
                convo_pairs[-1]['bot'] = entry['content']
        convo_pairs = convo_pairs[-5:]
        set_persona_mode(current_mode)
        async with message.channel.typing():
            try:
                response = yumi_sugoi_response(message.content + image_context, user_facts=user_facts_for_llm, convo_history=convo_pairs)
                success = await handle_response_feedback(message, response)
                if success:
                    channel_history.append({'role': 'user', 'content': message.content, 'author': str(message.author.name)})
                    channel_history.append({'role': 'assistant', 'content': response})
                    save_convo_history(CONVO_HISTORY)
            except Exception as e:
                print(f"Error in response handler: {e}")
                print(f"Full error: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                await message.add_reaction('❌')
            except Exception as e:
                print(f"Error in message handler: {e}")
                print(f"Full error: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                await message.add_reaction('❌')
    except Exception as e:
        print(f"Error in message handler: {e}")
        print(f"Full error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        await message.add_reaction('❌')
    await bot.process_commands(message)

@bot.event
async def on_command(ctx):
    """Track command invocations"""
    track_command(ctx.command.name)

def start_dashboard_thread(bot_instance=None, persona_modes=None, custom_personas_data=None, get_level_func=None, get_xp_func=None):
    """Start the dashboard in a separate thread"""
    from .web_dashboard import create_dashboard_app
    
    # Initialize global variables
    global bot, PERSONA_MODES, custom_personas, get_level, get_xp
    if bot_instance:
        bot = bot_instance
    if persona_modes:
        PERSONA_MODES = persona_modes
    if custom_personas_data:
        custom_personas = custom_personas_data
    if get_level_func:
        get_level = get_level_func
    if get_xp_func:
        get_xp = get_xp_func
    
    # Initialize message tracking if not already done
    global message_count, command_usage
    if 'message_count' not in globals():
        message_count = defaultdict(int)
    if 'command_usage' not in globals():
        command_usage = defaultdict(int)
      # Create the Flask app
    app = create_dashboard_app(
        PERSONA_MODES=PERSONA_MODES,
        custom_personas=custom_personas,
        get_level=get_level,
        get_xp=get_xp
    )
    
    # Set the bot instance
    app.set_bot(bot)    # Define dashboard runner function
    def run_dashboard():
        """Run the dashboard with Socket.IO enabled"""
        try:
            socketio = app.config.get('socketio')
            if socketio:
                print("[Dashboard] Starting with Socket.IO support")
                socketio.run(app, host='0.0.0.0', port=5005, debug=False, allow_unsafe_werkzeug=True)
            else:
                print("[Dashboard] Warning: Starting without Socket.IO (fallback mode)")
                app.run(host='0.0.0.0', port=5005)
        except Exception as e:
            print(f"[Dashboard] Error starting server: {e}")
            return

    # Start dashboard in a separate thread
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    print("[Dashboard] Started web dashboard at http://127.0.0.1:5005")
    return dashboard_thread
    return dashboard_thread

@bot.event
async def on_message_delete(message):
    log_channel = None
    if message.guild:
        for channel in message.guild.text_channels:
            if channel.name == 'yumi-logs':
                log_channel = channel
                break
    if log_channel:
        await log_channel.send(f"[Log] Message deleted in {message.channel.mention} by {message.author}: {message.content}")

@bot.event
async def on_member_join(member):
    log_channel = None
    for channel in member.guild.text_channels:
        if channel.name == 'yumi-logs':
            log_channel = channel
            break
    if log_channel:
        await log_channel.send(f"[Log] {member.mention} joined the server!")

# --- Dashboard Data Storage ---
DASHBOARD_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'dashboard_data')
MESSAGE_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'message_stats.json')
COMMAND_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'command_stats.json')
SERVER_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'server_stats.json')
CHANNEL_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'channel_stats.json')
USER_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'user_stats.json')

# Initialize statistics dictionaries
message_stats = defaultdict(int)  # Tracks message counts per hour and server
command_stats = defaultdict(int)  # Tracks command usage
server_stats = {}  # Tracks server activity
channel_stats = defaultdict(lambda: {"last_message": None, "message_count": 0, "active_users": set()})
user_stats = defaultdict(lambda: {"messages": 0, "commands": 0, "last_active": None})

def load_dashboard_stats():
    """Load statistics from saved files"""
    global message_stats, command_stats, server_stats, channel_stats, user_stats
    
    try:
        # Initialize stats dictionaries
        if os.path.exists(MESSAGE_STATS_FILE):
            with open(MESSAGE_STATS_FILE, 'r') as f:
                message_stats.update(json.load(f))
        if os.path.exists(COMMAND_STATS_FILE):
            with open(COMMAND_STATS_FILE, 'r') as f:
                command_stats.update(json.load(f))
        if os.path.exists(SERVER_STATS_FILE):
            with open(SERVER_STATS_FILE, 'r') as f:
                server_stats.update(json.load(f))
        if os.path.exists(CHANNEL_STATS_FILE):
            with open(CHANNEL_STATS_FILE, 'r') as f:
                data = json.load(f)
                for channel_id, stats in data.items():
                    channel_stats[channel_id].update(stats)
                    # Convert active_users back to set if it was saved as list
                    if isinstance(channel_stats[channel_id]["active_users"], list):
                        channel_stats[channel_id]["active_users"] = set(channel_stats[channel_id]["active_users"])
        if os.path.exists(USER_STATS_FILE):
            with open(USER_STATS_FILE, 'r') as f:
                data = json.load(f)
                for user_id, stats in data.items():
                    user_stats[user_id].update(stats)
        print("[Stats] Successfully loaded dashboard statistics")
    except Exception as e: 
        print(f"[Stats] Error loading statistics: {e}")
        # Initialize empty stats if loading fails
        message_stats.clear()
        command_stats.clear()
        server_stats.clear()
        channel_stats.clear()
        user_stats.clear()

def save_dashboard_stats():
    """Save current statistics to files"""
    try:
        with open(MESSAGE_STATS_FILE, 'w') as f:
            json.dump(dict(message_stats), f)
            
        with open(COMMAND_STATS_FILE, 'w') as f:
            json.dump(dict(command_stats), f)
            
        with open(SERVER_STATS_FILE, 'w') as f:
            json.dump(server_stats, f)
            
        with open(CHANNEL_STATS_FILE, 'w') as f:
            # Convert sets to lists for JSON serialization
            channel_data = {}
            for channel_id, stats in channel_stats.items():
                channel_data[channel_id] = {
                    **stats,
                    "active_users": list(stats["active_users"])
                }
            json.dump(channel_data, f)
            
        with open(USER_STATS_FILE, 'w') as f:
            json.dump(dict(user_stats), f)
            
    except Exception as e:
        print(f"[Stats] Error saving statistics: {e}")

async def update_server_stats():
    """Background task to update server statistics periodically"""
    await bot.wait_until_ready()
    
    while True:
        try:
            # Update stats for each guild
            for guild in bot.guilds:
                if str(guild.id) not in server_stats:
                    server_stats[str(guild.id)] = {}
                
                stats = server_stats[str(guild.id)]
                stats["name"] = guild.name
                stats["member_count"] = guild.member_count
                stats["channel_count"] = len(guild.channels)
                stats["role_count"] = len(guild.roles)
                
                # Get online member count
                online_count = sum(1 for m in guild.members if m.status != discord.Status.offline)
                stats["online_count"] = online_count
                
                # Update last updated timestamp
                stats["last_updated"] = datetime.utcnow().isoformat()
            
            # Save updated stats
            save_dashboard_stats()
            
        except Exception as e:
            print(f"[Stats] Error updating server stats: {e}")
        
        # Update every 5 minutes
        await asyncio.sleep(300)

# Clean up old stats periodically
async def cleanup_old_stats():
    """Clean up old statistics to prevent data buildup"""
    await bot.wait_until_ready()
    while True:
        try:
            now = datetime.utcnow()
            yesterday = now - timedelta(days=1)
            
            # Clean up message stats older than 24 hours
            for key in list(message_stats.keys()):
                if key.startswith("hour_") and int(key.split("_")[1]) < yesterday.hour:
                    del message_stats[key]
            
            # Clean up inactive users (no activity for 7 days)
            for user_id in list(user_stats.keys()):
                last_active = datetime.fromisoformat(user_stats[user_id]["last_active"])
                if (now - last_active).days > 7:
                    del user_stats[user_id]
            
            save_dashboard_stats()
        except Exception as e:
            print(f"[Stats] Error cleaning up old stats: {e}")
        finally:
            await asyncio.sleep(3600)  # Run every hour

async def setup_tasks():
    """Initialize all background tasks"""
    # Load initial data
    load_dashboard_stats()
    
    # Background task for server/guild statistics
    bot.loop.create_task(update_server_stats())
    
    # Background task for cleaning up old stats
    bot.loop.create_task(cleanup_old_stats())
    
    # Background task for scheduled announcements
    bot.loop.create_task(scheduled_announcement_task())
    
    # Background task for Yumi reminders
    bot.loop.create_task(yumi_reminder_task())
    
    # Start dashboard in a separate thread
    start_dashboard_thread(
        bot_instance=bot, 
        persona_modes=PERSONA_MODES,
        custom_personas_data=custom_personas
    )
    
    print("[Tasks] All background tasks initialized successfully")

# --- Make sure to load all required data before starting tasks ---
DASHBOARD_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'dashboard_data')
os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)

MESSAGE_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'message_stats.json')
COMMAND_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'command_stats.json')
SERVER_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'server_stats.json')
CHANNEL_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'channel_stats.json')
USER_STATS_FILE = os.path.join(DASHBOARD_DATA_DIR, 'user_stats.json')

def save_message_stats():
    """Save message statistics to file"""
    try:
        with open(MESSAGE_STATS_FILE, 'w', encoding='utf-8') as f:
            # Convert defaultdict to regular dict for JSON serialization
            json.dump(dict(message_stats), f, ensure_ascii=False, indent=2)
    except Exception as e:
        # Handle any exceptions that may occur during saving
        print(f"Error saving message stats: {e}")
    

def load_message_stats():
    """Load message statistics from file"""
    try:
        with open(MESSAGE_STATS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Update the defaultdict with loaded data
            message_stats.update(data)
    except FileNotFoundError:
        pass  # File doesn't exist yet
    except Exception as e:
        # Handle any other exceptions that may occur
        print(f"Error loading message stats: {e}")
    

# Initialize statistics tracking
message_stats = defaultdict(int)
command_stats = defaultdict(int)
server_stats = {}
channel_stats = defaultdict(lambda: {"last_message": None, "message_count": 0, "active_users": set()})
user_stats = defaultdict(lambda: {"messages": 0, "commands": 0, "last_active": None})

# Load existing stats
load_message_stats()

async def update_message_stats(message):
    """Update message statistics when a message is sent"""
    try:
        # Update hourly stats
        hour = datetime.utcnow().hour
        message_stats[f"hour_{hour}"] += 1

        # Update daily stats
        day = datetime.utcnow().weekday()
        message_stats[f"day_{day}"] += 1

        # Update total message count
        message_stats["total"] += 1

        # Update channel stats
        if message.guild:
            channel_id = str(message.channel.id)
            user_id = str(message.author.id)

            channel_stats[channel_id]["message_count"] += 1
            channel_stats[channel_id]["last_message"] = datetime.utcnow().isoformat()
            channel_stats[channel_id]["active_users"].add(user_id)

        # Save stats periodically (every 10 messages)
        if message_stats["total"] % 10 == 0:
            save_message_stats()

    except Exception as e:
        # Log any errors that occur during stats update
        print(f"Error updating message stats: {e}")
        # Handle any exceptions that may occur during stats update

# --- Utility stubs for context-aware conversation (if not already defined) ---
def update_command_stats(ctx):
    pass

def extract_user_facts_from_message(user_id, message_content):
    """Extracts user facts from natural language and updates user_facts dict."""
    updated = False
    # Always use a dict for facts
    facts = user_facts.get(user_id)
    if not isinstance(facts, dict):
        facts = {}
    # Name patterns
    name_match = re.search(r"(?:my name is|call me|i am|i'm|im)\s+([A-Za-z0-9_\- ]{2,32})", message_content, re.IGNORECASE)
    if name_match:
        facts['name'] = name_match.group(1).strip()
        updated = True
    # Location patterns
    loc_match = re.search(r"(?:i (?:live|am) in|i'm from|im from)\s+([A-Za-z0-9_\- ,]{2,64})", message_content, re.IGNORECASE)
    if loc_match:
        facts['location'] = loc_match.group(1).strip()
        updated = True
    # Birthday patterns
    bday_match = re.search(r"(?:my birthday is|i was born on)\s+([A-Za-z0-9_\- ,]{2,32})", message_content, re.IGNORECASE)
    if bday_match:
        facts['birthday'] = bday_match.group(1).strip()
        updated = True
    # Favorite patterns
    fav_match = re.search(r"my favorite (\w+) is ([A-Za-z0-9_\- ]{2,32})", message_content, re.IGNORECASE)
    if fav_match:
        facts[f'favorite_{fav_match.group(1).lower()}'] = fav_match.group(2).strip()
        updated = True
    if updated:
        user_facts[user_id] = facts
        save_json_file(USER_FACTS_FILE, user_facts)
        print(f"[DEBUG] Updated user facts for {user_id}: {facts}")
    return updated

def is_new_topic(message_content):
    return False

def run():
    """Start the bot with the Discord token."""
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                discord_token = config.get('token')
        except Exception:
            print("Error: Discord token not found in environment or config.json")
            sys.exit(1)

    try:
        print("[Bot] Starting Yumi Sugoi...")
        bot.run(discord_token)
    except discord.errors.LoginFailure:
        print("Error: Invalid Discord token")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting bot: {e}")
        traceback.print_exc()
        sys.exit(1)

# Only run if this file is run directly
if __name__ == "__main__":
    load_all_custom_commands(bot)
    run()

@bot.command()
@commands.check(lambda ctx: is_admin(ctx.author))
async def yumi_reload(ctx):
    """Reload Yumi's modules and configuration (owner only)."""
    try:
        import importlib
        importlib.reload(yumi_commands)
        importlib.reload(history)
        importlib.reload(feedback)
        importlib.reload(image_caption)
        importlib.reload(llm)
        await ctx.send("Yumi's modules reloaded!")
    except Exception as e:
        await ctx.send(f"Failed to reload: {e}")