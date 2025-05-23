import openai
import os
import json
from dotenv import load_dotenv
from .persona import get_persona_prompt

# Always load .env from project root, not cwd
DOTENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
# Warn if OPENAI_API_KEY is already set in the environment
if 'OPENAI_API_KEY' in os.environ:
    print('[WARNING] OPENAI_API_KEY is already set in the environment and will be overridden by .env')
load_dotenv(DOTENV_PATH, override=True)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
print(f"[DEBUG] Loaded OPENAI_API_KEY: {OPENAI_API_KEY[:16]}... (length: {len(OPENAI_API_KEY) if OPENAI_API_KEY else 0})")
if not OPENAI_API_KEY:
    raise RuntimeError('OPENAI_API_KEY must be set in your .env file')
openai.api_key = OPENAI_API_KEY

def generate_llm_response(user_message, qa_pairs=None, history=None):
    if qa_pairs is None:
        qa_pairs = {}
    system_prompt = get_persona_prompt()
    context = ""
    if qa_pairs:
        for q, a in list(qa_pairs.items())[:5]:
            context += f"Q: {q}\nA: {a}\n"
    if history:
        for h in history:
            context += f"User: {h['user']}\nYumi: {h['bot']}\n"
    prompt = f"{context}\nUser: {user_message}\nYumi:"
    try:
        # For openai>=1.0.0
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=256,
            temperature=0.7
        )
        llm_reply = response.choices[0].message.content.strip()
        # Save the prompt and LLM reply to the dataset for self-reliance
        DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets')
        DATASET_FILE = os.path.join(DATASET_DIR, 'chatbot_dataset.json')
        if user_message and llm_reply:
            qa_pairs[user_message.lower()] = llm_reply
            with open(DATASET_FILE, 'w', encoding='utf-8') as f:
                json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
        return llm_reply
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return "Sorry, I couldn't generate a response right now."

def load_hf_model():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    try:
        ai_tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
        ai_model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")
        return True, ai_tokenizer, ai_model
    except Exception as e:
        print(f"AI model could not be loaded: {e}")
        return False, None, None
