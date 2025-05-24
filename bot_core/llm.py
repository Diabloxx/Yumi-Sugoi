import os
import json
import requests
from .persona import get_persona_prompt

# Load environment variables for Ollama configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://10.0.0.28:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))

def generate_llm_response(user_message, qa_pairs=None, history=None, temperature=None, num_predict=None):
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
    prompt = f"{system_prompt}\n{context}\nUser: {user_message}\nYumi:"
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else OLLAMA_TEMPERATURE,
                "num_predict": num_predict if num_predict is not None else OLLAMA_NUM_PREDICT
            }
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        llm_reply = data.get("response", "Sorry, I couldn't generate a response right now.").strip()
        # Save the prompt and LLM reply to the dataset for self-reliance
        DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets')
        DATASET_FILE = os.path.join(DATASET_DIR, 'chatbot_dataset.json')
        if user_message and llm_reply:
            qa_pairs[user_message.lower()] = llm_reply
            with open(DATASET_FILE, 'w', encoding='utf-8') as f:
                json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
                
        # Optional: log every prompt/response
        with open(os.path.join(DATASET_DIR, "ollama_log.txt"), "a", encoding="utf-8") as logf:
            logf.write(json.dumps({"prompt": prompt, "response": llm_reply}) + "\n")
            
        return llm_reply
    except Exception as e:
        print(f"Ollama API error: {e}")
        return f"Sorry, I couldn't generate a response right now. (Error: {str(e)[:100]})"

# Add compatibility function for the old HF model loading call
def load_hf_model():
    """Compatibility function that returns placeholders since we're using Ollama now"""
    print("Using Ollama LLM at", OLLAMA_URL, "with model", OLLAMA_MODEL)
    return True, None, None
