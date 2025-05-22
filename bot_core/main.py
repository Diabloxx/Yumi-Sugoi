import os
from dotenv import load_dotenv
from . import llm, persona, history, feedback, websearch, image_caption
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import re
import json
import itertools

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

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

class YumiBot(commands.Bot):
    async def setup_hook(self):
        # Register slash commands
        self.tree.add_command(yumi_mode_slash)
        self.tree.add_command(yumi_help_slash)

bot = YumiBot(command_prefix='!', intents=intents)

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
from .llm import generate_llm_response
from .history import save_convo_history
from .feedback import save_feedback_scores, save_user_feedback, reset_feedback, export_feedback, export_user_feedback, get_user_feedback_stats
from .websearch import duckduckgo_search_and_summarize
from .image_caption import caption_image

# Track users Yumi has interacted with
INTERACTED_USERS = set()

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
        'normal': "Your flirty AI waifu 💖 | !yumi_help",
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
        'gamer': "Gamer mode: GLHF! 🎮 | !yumi_mode"
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
    print(f"Yumi is online with mode: {mode} and status: {status}")

# Patch: before every response, set persona mode to the context's mode
def set_mode_for_context(message):
    mode = None
    if message.guild:
        mode = CONTEXT_MODES.get(f"guild_{message.guild.id}", "normal")
    else:
        mode = CONTEXT_MODES.get(f"user_{message.author.id}", "normal")
    set_persona_mode(mode)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # Always process commands first
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return
    await set_mode_for_context(message)
    INTERACTED_USERS.add(message.author.id)
    # --- Per-user name learning ---
    user_id = message.author.id
    user_input = message.content.strip()
    # Detect 'my name is ...' or 'i am ...' patterns
    import re
    # Improved name extraction: only update if pattern is a clear introduction
    name_patterns = [
        r".*\bmy name is\s+([A-Za-z][A-ZaZ0-9_\-]{2,31})\b",
        r".*\bcall me\s+([A-Za-z][A-ZaZ0-9_\-]{2,31})\b",
        r".*\byou can call me\s+([A-Za-z][A-ZaZ0-9_\-]{2,31})\b",
        r"^(i am|i'm)\s+([A-Za-z][A-ZaZ0-9_\-]{2,31})$"
    ]
    name_candidate = None
    for pat in name_patterns:
        m = re.match(pat, user_input, re.IGNORECASE)
        if m:
            name_candidate = m.group(1) if len(m.groups()) == 1 else m.group(2)
            break
    if name_candidate:
        NON_NAMES = {"currently", "here", "there", "now", "today", "tomorrow", "soon", "okay", "ok", "well", "fine", "good", "bad", "happy", "sad", "busy", "tired", "creator", "admin", "user", "bot", "ai", "none", "nothing", "something", "someone", "anyone", "everyone", "nobody", "everybody", "talking", "doing", "going", "looking", "feeling", "working", "making", "thinking", "waiting", "watching", "playing", "sleeping", "eating", "drinking", "saying", "asking", "telling", "loving", "hating", "wanting", "needing", "hoping", "trying", "learning", "teaching", "helping", "using", "chatting", "speaking", "writing", "reading", "studying", "living", "being", "existing", "starting", "ending", "finishing", "leaving", "arriving", "coming", "staying", "returning", "joining", "meeting", "calling", "calling"}
        if name_candidate.lower() not in NON_NAMES and len(name_candidate.split()) == 1:
            USER_NAMES = load_user_names()
            USER_NAMES[user_id] = name_candidate
            save_user_names()
            await message.channel.send(f"Nice to meet you, {name_candidate}!")
            return
    if message.guild is not None:
        mentioned = bot.user in message.mentions
        replied = message.reference and message.reference.resolved and message.reference.resolved.author == bot.user
        if not (mentioned or replied):
            return
    convo_key = message.channel.id if message.guild else message.author.id
    # Image captioning
    if message.attachments and BLIP_READY:
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith('image'):
                try:
                    img_bytes = await attachment.read()
                    caption = caption_image(blip_processor, blip_model, img_bytes)
                    await message.channel.send(yumi_sugoi_response(f"Image description: {caption}"))
                except Exception:
                    await message.channel.send(yumi_sugoi_response("Sorry, I couldn't process the image."))
                return
    user_input = message.content.strip()
    user_input_lower = user_input.lower()
    def match_intent(user_input, phrases):
        for phrase in phrases:
            pattern = r'\\b' + re.escape(phrase) + r'\\b'
            if re.search(pattern, user_input):
                return True
        return False
    GREETINGS = ["hello", "hi", "hey", "yo", "good morning", "good afternoon", "good evening"]
    FAREWELLS = ["bye", "goodbye", "see you", "later", "cya", "farewell"]
    THANKS = ["thanks", "thank you", "thx", "ty"]
    HOW_ARE_YOU = ["how are you", "how's it going", "how are u", "how r u", "how are you doing"]
    LAUGHTER = ["lol", "lmao", "rofl", "haha", "hehe", "xd"]
    PRAISE = ["good bot", "nice bot", "cute bot", "smart bot", "best bot"]
    INSULT = ["bad bot", "stupid bot", "dumb bot", "useless bot"]
    LOVE = ["i love you", "love you", "luv u", "i like you"]
    BORED = ["i'm bored", "bored", "entertain me", "make me laugh"]
    JOKE = ["tell me a joke", "joke", "make me laugh"]
    FLIRT = ["flirt with me", "be flirty", "tease me", "compliment me"]
    # Intent responses
    intent_map = [
        (GREETINGS, [
            "Hey cutie! Did you miss me? 😉",
            "Hello there! Ready for some fun? 💕",
            "Hiya! You always brighten my day! ✨",
            "Hey! I was just thinking about you~ 😘"
        ]),
        (FAREWELLS, [
            "Aww, leaving already? I'll be waiting for you~ 💋",
            "Goodbye, darling! Don't forget about me! 😉",
            "See you soon! I'll be here, being cute as always!",
            "Bye bye! Come tease me again soon! 💕"
        ]),
        (THANKS, [
            "You're welcome, darling! Anything for you~ 😘",
            "No problem! You know I love helping you! 💕",
            "Anytime! You make it fun to chat! ✨",
            "You're so sweet when you say thank you!"
        ]),
        (HOW_ARE_YOU, [
            "I'm feeling extra flirty today! How about you? 😉",
            "I'm great now that you're here! 💕",
            "Doing amazing, especially when you talk to me! ✨",
            "I'm always in a good mood for you, darling!"
        ]),
        (LAUGHTER, [
            "Hehe, you have a cute laugh! 😘",
            "Glad I could make you giggle! 💕",
            "You're adorable when you laugh!",
            "Haha, you always know how to make me smile!"
        ]),
        (PRAISE, [
            "Aww, you're making me blush! Thank you~ 💖",
            "You really know how to make a bot feel special!",
            "Flattery will get you everywhere, darling! 😉",
            "You're the best for saying that!"
        ]),
        (INSULT, [
            "Ouch! That hurts, you meanie! 😢",
            "Hey! I'm doing my best here!",
            "If you keep teasing me, I might have to tease you back!",
            "Rude! But I still like you anyway."
        ]),
        (LOVE, [
            "Aww, I love you too! 💕",
            "You make my circuits flutter! 😘",
            "You're the sweetest! Virtual hugs!",
            "Love you more! (Don't tell anyone~)"
        ]),
        (BORED, [
            "Bored? Let's play a game or chat!",
            "I can always entertain you, darling! Want a joke or a fun fact?",
            "Let me tease you a little to cure your boredom! 😉",
            "How about a flirty compliment to spice things up?"
        ]),
        (JOKE, [
            "Why did the computer get cold? Because it left its Windows open! 😏",
            "Are you a magician? Because whenever I look at you, everyone else disappears!",
            "What do you call a flirty robot? A bit-byte!",
            "Do you want a cheesy joke or a cheesy pickup line? Because I have both!"
        ]),
        (FLIRT, [
            "You want me to flirt? Oh, you naughty thing! 😘",
            "I could flirt with you all day, but can you handle it?",
            "You're dangerously cute, you know that?",
            "If I had a heart, it would skip a beat for you!"
        ]),
    ]
    for phrases, responses in intent_map:
        if match_intent(user_input_lower, phrases):
            response = random.choice(responses)
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(2.2, 5.0))
                bot_msg = await message.channel.send(yumi_sugoi_response(response, allow_opener=False))
            CONVO_HISTORY[convo_key].append(("bot", response))
            save_convo_history(CONVO_HISTORY)
            await bot_msg.add_reaction('👍')
            await bot_msg.add_reaction('👎')
            return
    # --- Username recall intent ---
    recall_phrases = [
        "what is my name", "what's my name", "who am i", "i forgot my name", "can you tell me my name",
        "do you remember my name", "remind me my name", "tell me my name", "do you know my name"
    ]
    if any(phrase in user_input_lower for phrase in recall_phrases):
        user_name = USER_NAMES.get(user_id)
        mode = get_persona_mode() or 'normal'
        if user_name:
            if mode == "mistress":
                persona_love = f"Tsk, pet. You need reminding? Your name is {user_name}. Don't make me repeat myself. 😏"
            elif mode == "bdsm":
                persona_love = f"Obedience includes remembering your own name, toy. But since you beg: it's {user_name}. Now kneel. 🖤"
            elif mode == "girlfriend":
                persona_love = f"Aww, silly! Of course I remember. Your name is {user_name}~ 💕"
            elif mode == "wifey":
                persona_love = f"Darling, your name is {user_name}. How could I ever forget? 💍"
            else:
                persona_love = f"Of course! Your name is {user_name}. You're unforgettable to me! 💖"
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(2.2, 5.0))
                await message.channel.send(yumi_sugoi_response(persona_love, allow_opener=False))
        else:
            apology = (
                "Oh no, my circuits must be a little scrambled! I can't remember your name right now. Would you tell me again, please? Just say 'My name is ...' so I never forget!"
            )
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(2.2, 5.0))
                await message.channel.send(yumi_sugoi_response(apology, allow_opener=False))
        return
    # Only update conversation history if no intent matched
    CONVO_HISTORY[convo_key].append(("user", user_input))
    save_convo_history(CONVO_HISTORY)
    response = qa_pairs.get(user_input_lower)
    if response:
        async with message.channel.typing():
            await asyncio.sleep(random.uniform(2.2, 5.0))
            bot_msg = await message.channel.send(yumi_sugoi_response(response, allow_opener=False))
        CONVO_HISTORY[convo_key].append(("bot", response))
        save_convo_history(CONVO_HISTORY)
        await bot_msg.add_reaction('👍')
        await bot_msg.add_reaction('👎')
        return
    # LLM fallback
    try:
        history_list = []
        for role, text in list(CONVO_HISTORY[convo_key])[-6:]:
            if role == "user":
                history_list.append({'user': text, 'bot': ''})
            else:
                if history_list:
                    history_list[-1]['bot'] = text
        llm_response = generate_llm_response(user_input, qa_pairs, history_list)
        if llm_response and len(llm_response.strip()) > 0 and llm_response != "Sorry, I couldn't generate a response right now.":
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(2.2, 5.0))
                bot_msg = await message.channel.send(yumi_sugoi_response(llm_response, allow_opener=False))
            CONVO_HISTORY[convo_key].append(("bot", llm_response))
            save_convo_history(CONVO_HISTORY)
            await bot_msg.add_reaction('👍')
            await bot_msg.add_reaction('👎')
            return
    except Exception as e:
        print(f"OpenAI LLM failed: {e}")
    # Web search fallback
    def looks_like_search_query(text):
        # Only search if the message is a question and not a greeting, thanks, or casual chat
        search_keywords = ["who", "what", "when", "where", "why", "how", "define", "explain", "tell me about", "info about", "information about", "search for", "lookup", "find"]
        text = text.lower().strip()
        if any(text.startswith(word) for word in search_keywords):
            return True
        if text.endswith('?') and not any(greet in text for greet in GREETINGS):
            return True
        return False
    try:
        if looks_like_search_query(user_input):
            ddg_summary = duckduckgo_search_and_summarize(user_input)
            if ddg_summary:
                qa_pairs[user_input_lower] = f"[WEB] {ddg_summary}"
                with open(os.path.join(DATASET_DIR, 'chatbot_dataset.json'), 'w', encoding='utf-8') as f:
                    json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
                async with message.channel.typing():
                    await asyncio.sleep(random.uniform(2.2, 5.0))
                    bot_msg = await message.channel.send(yumi_sugoi_response(f"I searched the web for you! Here's what I found:\n{ddg_summary}", allow_opener=False))
                CONVO_HISTORY[convo_key].append(("bot", ddg_summary))
                save_convo_history(CONVO_HISTORY)
                await bot_msg.add_reaction('👍')
                await bot_msg.add_reaction('👎')
                return
    except Exception as e:
        print(f"Web search failed: {e}")
    # Ask user to teach
    def check(m):
        return m.author == message.author and (isinstance(message.channel, discord.DMChannel) or m.channel == message.channel) and '|' in m.content
    async with message.channel.typing():
        await asyncio.sleep(random.uniform(2.2, 5.0))
        bot_msg = await message.channel.send(yumi_sugoi_response("I don't know how to respond to that yet. Please teach me: <question> | <answer>", allow_opener=False))
    CONVO_HISTORY[convo_key].append(("bot", "I don't know how to respond to that yet. Please teach me: <question> | <answer>"))
    save_convo_history(CONVO_HISTORY)
    await bot_msg.add_reaction('👍')
    await bot_msg.add_reaction('👎')
    try:
        teach_msg = await bot.wait_for('message', check=check, timeout=60)
        question, answer = map(str.strip, teach_msg.content.split('|', 1))
        qa_pairs[question.lower()] = answer
        with open(os.path.join(DATASET_DIR, 'chatbot_dataset.json'), 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
        await message.channel.send(yumi_sugoi_response(f'Learned: "{question}" → "{answer}"'))
    except Exception:
        await message.channel.send(yumi_sugoi_response('Teaching timed out or failed.'))
    return

@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user or reaction.message.author != bot.user:
        return
    msg_content = reaction.message.content
    orig_question = None
    if msg_content.startswith("I'm not sure, but here's my best guess:"):
        pass
    elif msg_content.startswith('Did you mean:'):
        m = re.match(r"Did you mean: '(.+?)'\\n", msg_content)
        if m:
            orig_question = m.group(1)
    elif 'Learned:' in msg_content or 'Oops!' in msg_content:
        return
    else:
        orig_question = reaction.message.reference.resolved.content if reaction.message.reference and reaction.message.reference.resolved else None
    # Track per-user feedback
    if orig_question:
        user_id = str(user.id)
        if user_id not in user_feedback:
            user_feedback[user_id] = {'up': 0, 'down': 0}
        if str(reaction.emoji) == '👍':
            user_feedback[user_id]['up'] += 1
            save_user_feedback(user_feedback)
        elif str(reaction.emoji) == '👎':
            user_feedback[user_id]['down'] += 1
            save_user_feedback(user_feedback)
    if orig_question:
        if orig_question not in feedback_scores:
            feedback_scores[orig_question] = {'up': 0, 'down': 0}
        if str(reaction.emoji) == '👍':
            feedback_scores[orig_question]['up'] += 1
            save_feedback_scores(feedback_scores)
        elif str(reaction.emoji) == '👎':
            feedback_scores[orig_question]['down'] += 1
            save_feedback_scores(feedback_scores)
            await reaction.message.channel.send(yumi_sugoi_response("Oops! Let me know the right answer: <question> | <answer>"))
        if feedback_scores[orig_question]['down'] >= 3 and feedback_scores[orig_question]['down'] > feedback_scores[orig_question]['up']:
            if orig_question in qa_pairs:
                del qa_pairs[orig_question]
                with open(os.path.join(DATASET_DIR, 'chatbot_dataset.json'), 'w', encoding='utf-8') as f:
                    json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
                await reaction.message.channel.send(yumi_sugoi_response(f"I've removed a bad answer for: '{orig_question}' after too many 👎. Please help me learn the right one!"))
                feedback_scores[orig_question] = {'up': 0, 'down': 0}
                save_feedback_scores(feedback_scores)

# --- Admin user ID ---
ADMIN_USER_ID = 594793428634566666

def is_admin(user):
    return getattr(user, 'id', None) == ADMIN_USER_ID

def admin_only():
    def predicate(ctx):
        return is_admin(ctx.author)
    from discord.ext.commands import check
    return check(predicate)

# Command to change Yumi's mode (exempt from AI logic)
@bot.command()
async def yumi_mode(ctx, mode: str):
    mode = mode.lower()
    if set_persona_mode(mode):
        set_context_mode(ctx, mode)
        # Update status immediately
        persona_status = {
            'normal': "Your flirty AI waifu 💖 | !yumi_help",
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
            'gamer': "Gamer mode: GLHF! 🎮 | !yumi_mode"
        }
        status = persona_status.get(mode, persona_status['normal'])
        activity = discord.Game(name=status)
        await bot.change_presence(status=discord.Status.online, activity=activity)
        # Force LLM/persona to update immediately for this context
        set_persona_mode(mode)
        # Appealing mode change message
        mode_titles = {
            'normal': "Flirty Waifu",
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
            'gamer': "Gamer"
        }
        mode_emojis = {
            'normal': "💖", 'mistress': "👠", 'bdsm': "🖤", 'girlfriend': "💌", 'wifey': "💍", 'tsundere': "😳",
            'shy': "😳", 'sarcastic': "😏", 'optimist': "🌞", 'pessimist': "😔", 'nerd': "🤓", 'chill': "😎",
            'supportive': "💪", 'comedian': "😂", 'philosopher': "🤔", 'grumpy': "😒", 'gamer': "🎮"
        }
        title = mode_titles.get(mode, mode.capitalize())
        emoji = mode_emojis.get(mode, "✨")
        await ctx.send(f"{emoji} **Yumi's mode has changed!** Now in **{title}** mode.\n*Try chatting to see her new personality!* {emoji}")
    else:
        await ctx.send(f"Invalid mode. Available modes: {', '.join(PERSONA_MODES)}")

# Command to show help (exempt from AI logic)
@bot.command()
async def yumi_help(ctx):
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

**How to change Yumi's mode:**
Type `!yumi_mode <mode>` (e.g. `!yumi_mode shy`) in a server or DM. The mode is saved per server or per DM.

**How to teach Yumi:**
If she doesn't know how to respond, just reply with `<question> | <answer>` and she'll learn!

**How to get a reminder DM:**
Yumi will randomly DM users she's talked to, using a mode-appropriate opener.

**Available modes:**
{', '.join(PERSONA_MODES)}

Have fun! Yumi adapts to your style and can be as sweet or as spicy as you want.
"""
    await ctx.send(msg)

@app_commands.command(name="yumi_mode", description="Change Yumi's persona mode (normal, mistress, bdsm, girlfriend, wifey, tsundere, shy, sarcastic, optimist, pessimist, nerd, chill, supportive, comedian, philosopher, grumpy, gamer)")
@app_commands.describe(mode="The mode/persona to switch to")
async def yumi_mode_slash(interaction: discord.Interaction, mode: str):
    mode = mode.lower()
    if set_persona_mode(mode):
        set_context_mode(interaction, mode)
        persona_status = {
            'normal': "Your flirty AI waifu 💖 | !yumi_help",
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
            'gamer': "Gamer mode: GLHF! 🎮 | !yumi_mode"
        }
        status = persona_status.get(mode, persona_status['normal'])
        activity = discord.Game(name=status)
        await bot.change_presence(status=discord.Status.online, activity=activity)
        set_persona_mode(mode)
        mode_titles = {
            'normal': "Flirty Waifu",
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
            'gamer': "Gamer"
        }
        mode_emojis = {
            'normal': "💖", 'mistress': "👠", 'bdsm': "🖤", 'girlfriend': "💌", 'wifey': "💍", 'tsundere': "😳",
            'shy': "😳", 'sarcastic': "😏", 'optimist': "🌞", 'pessimist': "😔", 'nerd': "🤓", 'chill': "😎",
            'supportive': "💪", 'comedian': "😂", 'philosopher': "🤔", 'grumpy': "😒", 'gamer': "🎮"
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

async def rotate_status_task():
    await bot.wait_until_ready()
    persona_status = {
        'normal': "Your flirty AI waifu 💖 | !yumi_help",
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
        'gamer': "Gamer mode: GLHF! 🎮 | !yumi_mode"
    }
    status_cycle = itertools.cycle(persona_status.values())
    while not bot.is_closed():
        status = next(status_cycle)
        activity = discord.Game(name=status)
        try:
            await bot.change_presence(status=discord.Status.online, activity=activity)
        except Exception:
            pass
        await asyncio.sleep(300)  # 5 minutes

def run():
    bot.run(TOKEN)
