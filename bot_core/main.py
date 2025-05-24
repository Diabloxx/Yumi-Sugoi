import os
from . import llm, persona, history, feedback, websearch, image_caption
from .web_dashboard import start_dashboard_thread
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import re
import json
import itertools
from collections import defaultdict
import datetime
import threading
import importlib

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
CONVO_HISTORY = history.load_convo_history()
feedback_scores, user_feedback = feedback.load_feedback()
BLIP_READY, blip_processor, blip_model = image_caption.load_blip()
AI_READY, ai_tokenizer, ai_model = llm.load_hf_model()

import json

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
            # Always convert to defaultdict(set) of sets
            LOCKED_CHANNELS = defaultdict(set)
            for gid, cids in data.items():
                LOCKED_CHANNELS[int(gid)] = set(cids)
                for cid in cids:
                    print(f"[Lockdown Debug] Loaded Locked Channel {cid} for Guild {gid}")
    except Exception:
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
    bot.loop.create_task(yumi_reminder_task())
    bot.loop.create_task(rotate_status_task())
    bot.loop.create_task(scheduled_announcement_task())
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

@bot.command()
@commands.check_any(commands.has_permissions(administrator=True), admin_only())
async def yumi_post_changelog(ctx):
    """Post the latest changelog entry to the changelog channel (only if new)."""
    await post_changelog()
    await ctx.send("Changelog posted (if new update found)!")

# --- PER-USER CONTEXT LOGIC ---
# Use a per-user, per-channel context key for conversation history
USER_CHANNEL_CONTEXT = defaultdict(dict)  # {guild_id: {user_id: convo_key}}

@bot.command()
@commands.check_any(commands.has_permissions(administrator=True), admin_only())
async def yumi_admin_tools(ctx):
    """
    Show available admin tools and commands for Yumi Sugoi.
    """
    await ctx.send(
        "**Yumi Admin Tools:**\n"
        "- `!yumi_lockdown` — Restrict Yumi to only respond in the current channel\n"
        "- `!yumi_unlock` — Allow Yumi to respond in all channels again\n"
        "- `!yumi_purge <N>` — Delete the last N messages (admin only)\n"
        "- `!yumi_say <message>` — Make Yumi say something (admin only)\n"
        "- `!yumi_admin_tools` — Show this help message\n"
    )

# --- LOCKDOWN COMMANDS ---
LOCKED_CHANNELS = defaultdict(set)  # {guild_id: set(channel_ids)}

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
    while not bot.is_closed():
        now = datetime.datetime.utcnow()
        to_post = []
        for ann in list(scheduled_announcements):
            ann_time = datetime.datetime.fromisoformat(ann['time'])
            if now >= ann_time:
                to_post.append(ann)
        for ann in to_post:
            channel = bot.get_channel(ann['channel_id'])
            if channel:
                try:
                    await channel.send(f"[Scheduled Announcement]\n{ann['message']}")
                except Exception:
                    pass
            scheduled_announcements.remove(ann)
            save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
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

@bot.event
async def on_message(message):
    global LOCKED_CHANNELS
    if message.author == bot.user:
        return
    # --- Lockdown enforcement ---
    # ENSURE LOCKED_CHANNELS is always a defaultdict(set) and up to date
    if not isinstance(LOCKED_CHANNELS, defaultdict):
        temp = defaultdict(set)
        for gid, chans in LOCKED_CHANNELS.items():
            temp[gid] = set(chans)
        LOCKED_CHANNELS = temp
    # Only enforce lockdown if there are locked channels for this guild
    if message.guild:
        locked = LOCKED_CHANNELS.get(message.guild.id)
        if locked and len(locked) > 0:
            # Only allow commands in any channel, otherwise only respond in locked channels
            if not message.content.startswith(bot.command_prefix) and message.channel.id not in locked:
                return  # Ignore all non-command messages in non-locked channels during lockdown
    add_xp(message.author.id, 5)
    ctx = await bot.get_context(message)
    await bot.process_commands(message)
    if ctx.valid or message.content.startswith(bot.command_prefix):
        return
    try:
        import random, asyncio
        async with message.channel.typing():
            await asyncio.sleep(random.uniform(0.7, 2.0))
            # --- Conversation memory logic ---
            key = get_history_key(message)
            history_deque = CONVO_HISTORY[key]
            history = list(history_deque)
            response = llm.generate_llm_response(message.content, qa_pairs=qa_pairs, history=history)
            if response:
                await message.channel.send(response)
                history_deque.append({'user': message.content, 'bot': response})
                save_convo_history(CONVO_HISTORY)
    except Exception as e:
        print(f"[Yumi Response Error] {e}")

# --- Fun/Utility Commands ---
@bot.command()
async def yumi_poll(ctx, question: str, *options):
    """Create a poll. Usage: !yumi_poll <question> <option1> <option2> ..."""
    if len(options) < 2:
        await ctx.send("You need at least two options.")
        return
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    if len(options) > len(emojis):
        await ctx.send("Too many options (max 10).")
        return
    desc = '\n'.join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))
    embed = discord.Embed(title=question, description=desc, color=discord.Color.pink())
    poll_msg = await ctx.send(embed=embed)
    for i in range(len(options)):
        await poll_msg.add_reaction(emojis[i])

@bot.command()
async def yumi_suggest(ctx, *, suggestion: str):
    """Submit a suggestion to the bot admin."""
    admin_user = bot.get_user(ADMIN_USER_ID)
    if admin_user:
        await admin_user.send(f"Suggestion from {ctx.author}: {suggestion}")
    await ctx.send("Suggestion sent! Thank you.")

# --- Meme Generator (simple text meme) ---
@bot.command()
async def yumi_meme(ctx, top: str, bottom: str):
    """Generate a simple meme (text only)."""
    meme = f"┌{'─'*max(len(top),len(bottom))}┐\n│{top.center(max(len(top),len(bottom)))}│\n│{bottom.center(max(len(top),len(bottom)))}│\n└{'─'*max(len(top),len(bottom))}┘"
    await ctx.send(f"```{meme}```")

@bot.command()
async def yumi_aiart(ctx, *, prompt: str):
    """Generate AI art (placeholder)."""
    await ctx.send(f"[AI Art Placeholder] Would generate art for: {prompt}")

@bot.command()
async def yumi_tts(ctx, *, text: str):
    """Text-to-speech (placeholder)."""
    await ctx.send(f"[TTS Placeholder] Would speak: {text}")

# --- Advanced Moderation (auto-moderation, logging) ---
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

# Start the web dashboard in a background thread when the bot starts
start_dashboard_thread(PERSONA_MODES, custom_personas, get_level, get_xp)

async def rotate_status_task():
    await bot.wait_until_ready()
    persona_status = {
        'normal': "Your friendly, caring AI companion 🤗 | !yumi_help",
        'mistress': "Mistress Yumi is in control 👠 | !yumi_mode",
        'bdsm': "Dungeon open. Safe words ready. 🖤 | !yumi_mode",
        'girlfriend': "Your playful AI girlfriend 💌 | !yumi_mode",
        'wifey': "Loyal, loving, and here for you 💍 | !yumi_mode",
        'tsundere': "Not like I like you or anything! 😳 | !yumi_mode",
        'shy': "Um... hi... (shy mode) 😳 | !yumi_mode",
        'sarcastic': "Oh, joy. | !yumi_mode",
        'optimist': "Good vibes only! 🌞 | !yumi_mode",
        'pessimist': "Here we go again... | !yumi_mode",
        'nerd': "Did you know? 🤓 | !yumi_mode",
        'chill': "No worries 😎 | !yumi_mode",
        'supportive': "You got this! 💪 | !yumi_mode",
        'comedian': "Ready for laughs! 😂 | !yumi_mode",
        'philosopher': "Let's ponder... 🤔 | !yumi_mode",
        'grumpy': "What now? 😒 | !yumi_mode",
        'gamer': "GLHF! 🎮 | !yumi_mode",
        'genalpha': "Slay, bestie! 💅 | !yumi_mode",
        'egirl': "uwu cuteness overload! 🦋 | !yumi_mode"
    }
    status_cycle = itertools.cycle(persona_status.values())
    while not bot.is_closed():
        status = next(status_cycle)
        activity = discord.Game(name=status)
        try:
            await bot.change_presence(status=discord.Status.online, activity=activity)
        except Exception:
            pass
        await asyncio.sleep(60)  # 1 minutes

@bot.command()
async def yumi_uwu(ctx):
    """Yumi sends an uwu message."""
    uwu_lines = [
        "Uwu~! You're the cutest! (✿◕ᴗ◕)ﾉ✧",
        "Nyaa~ what's up, cutie? (｡♥‿♥｡)",
        "Hehe, did I make you blush? UwU",
        "*giggles* You're so precious! (づ｡◕‿‿◕｡)づ"
    ]
    await ctx.send(random.choice(uwu_lines))

@bot.command()
async def yumi_hug(ctx):
    """Yumi gives you a big virtual hug."""
    hugs = [
        "*hugs you tightly* (づ｡◕‿‿◕｡)づ",
        "Come here, let me give you a big hug! 🤗",
        "You deserve all the hugs! 💖",
        "*wraps arms around you* Stay cozy! 🦋"
    ]
    await ctx.send(random.choice(hugs))

@bot.command()
async def yumi_kiss(ctx):
    """Yumi blows you a kiss."""
    kisses = [
        "*blows you a kiss* 😘",
        "Mwah~! 💋",
        "You get a special kiss from Yumi! (｡♥‿♥｡)",
        "*kisses your cheek* You're adorable! 💕"
    ]
    await ctx.send(random.choice(kisses))

@bot.command()
async def yumi_blush(ctx):
    """Yumi blushes cutely."""
    blushes = [
        "*blushes deeply* S-stop looking at me like that! >///<",
        "Omg, you're making me blush! (⁄ ⁄•⁄ω⁄•⁄ ⁄)⁄",
        "Hehe, you're too sweet! (〃＾▽＾〃)",
        "*hides face* Nyaa~ so embarrassing! 🦋"
    ]
    await ctx.send(random.choice(blushes))

@bot.command()
@commands.check_any(commands.has_permissions(administrator=True), admin_only())
async def yumi_reload(ctx):
    """
    Reload the entire bot: all modules, datasets, dashboard, and restart all background tasks (admin only).
    """
    import importlib
    import sys
    import asyncio
    modules = ['llm', 'persona', 'history', 'feedback', 'websearch', 'image_caption', 'web_dashboard']
    reloaded = []
    failed = []
    for mod in modules:
        try:
            importlib.reload(sys.modules[f'bot_core.{mod}'])
            reloaded.append(mod)
        except Exception as e:
            failed.append(f"{mod} ({e})")
    # Reload datasets and persistent data
    global custom_personas, channel_personas, user_facts, user_xp, scheduled_announcements, CONTEXT_MODES, LOCKED_CHANNELS
    custom_personas = load_json_file(CUSTOM_PERSONAS_FILE, {})
    channel_personas = load_json_file(CHANNEL_PERSONAS_FILE, {})
    user_facts = load_json_file(USER_FACTS_FILE, {})
    user_xp = load_json_file(USER_XP_FILE, {})
    scheduled_announcements = load_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, [])
    try:
        import json
        MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'yumi_modes.json')
        with open(MODE_FILE, 'r', encoding='utf-8') as f:
            CONTEXT_MODES = json.load(f)
    except Exception:
        CONTEXT_MODES = {}
    try:
        LOCKDOWN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'lockdown_channels.json')
        with open(LOCKDOWN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Always convert to defaultdict(set) of sets after reload
            LOCKED_CHANNELS = defaultdict(set)
            for gid, cids in data.items():
                LOCKED_CHANNELS[int(gid)] = set(cids)
    except Exception:
        LOCKED_CHANNELS = defaultdict(set)
    # Restart dashboard thread to refresh dashboard state
    try:
        start_dashboard_thread(PERSONA_MODES, custom_personas, get_level, get_xp)
        dashboard_status = "Dashboard thread restarted."
    except Exception as e:
        dashboard_status = f"Dashboard restart failed: {e}"
    # Restart background tasks (status, reminders, announcements)
    try:
        bot.loop.create_task(rotate_status_task())
        bot.loop.create_task(yumi_reminder_task())
        bot.loop.create_task(scheduled_announcement_task())
        tasks_status = "Background tasks restarted."
    except Exception as e:
        tasks_status = f"Background task restart failed: {e}"
    msg = f"✅ Reloaded modules: {', '.join(reloaded)}.\n{dashboard_status}\n{tasks_status}"
    if failed:
        msg += f"\n❌ Failed: {', '.join(failed)}"
    else:
        msg += "\nAll persistent data reloaded."
    await ctx.send(msg)

def run():
    bot.run(TOKEN)