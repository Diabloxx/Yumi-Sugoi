import os
import json
import requests
import time
from typing import Tuple, Optional, Dict, List

# Load environment variables for Ollama configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://10.0.0.28:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistralrp")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.9"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

def validate_response(response: str, user_message: str) -> Tuple[bool, str]:
    """Validate the LLM response for quality and appropriateness."""
    if not response:
        return False, "Empty response"
    if len(response.split()) < 3:
        return False, "Response too short"
    if response == user_message:
        return False, "Response matches user message"
    return True, "OK"

def get_fallback_response(error_type: str) -> str:
    """Get a fallback response based on the type of error."""
    fallbacks = {
        "connection": "I'm having trouble connecting to my language model right now. Could you please try again in a moment?",
        "timeout": "I'm taking longer than usual to process your message. Could you please try again?",
        "validation": "I wasn't able to generate a good response. Could you please rephrase your message?",
        "default": "I apologize, but I'm having some technical difficulties. Could you please try again?"
    }
    return fallbacks.get(error_type, fallbacks["default"])

def generate_llm_response(
    user_message: str,
    system_prompt: str,
    qa_pairs: Optional[Dict] = None,
    history: Optional[List] = None,
    temperature: Optional[float] = None,
    num_predict: Optional[int] = None,
    user_facts: Optional[Dict] = None,
    convo_history: Optional[List] = None
) -> str:
    """Generate a response using the Ollama LLM"""
    if qa_pairs is None:
        qa_pairs = {}
    
    context = ""
    
    # Add user facts to context
    if user_facts:
        facts_str = ", ".join(f"{k.capitalize()}: {v}" for k, v in user_facts.items())
        context += f"User facts: {facts_str}\n"
    
    # Add Q&A pairs
    if qa_pairs:
        for q, a in list(qa_pairs.items())[:5]:
            context += f"Q: {q}\nA: {a}\n"
    
    # Add conversation history
    if convo_history:
        context += "\nRecent conversation:\n"
        for msg in convo_history[-5:]:  # Last 5 messages
            context += f"{msg}\n"
    
    # Prepare the prompt with all available context
    full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nUser: {user_message}\nYumi:"
    
    # Set up request parameters
    params = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "temperature": temperature or OLLAMA_TEMPERATURE,
        "num_predict": num_predict or OLLAMA_NUM_PREDICT,
        "stream": False
    }
    
    # Try to get a response with retries
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(OLLAMA_URL, json=params, timeout=30)
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            if "response" in result:
                generated_text = result["response"].strip()
                
                # Validate the response
                is_valid, message = validate_response(generated_text, user_message)
                if is_valid:
                    return generated_text
                    
            # If we get here, either validation failed or response was empty
            if attempt < MAX_RETRIES - 1:  # Not the last attempt
                time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                continue
                
            return get_fallback_response("validation")
                
        except requests.exceptions.Timeout:
            if attempt == MAX_RETRIES - 1:  # Last attempt
                return get_fallback_response("timeout")
            time.sleep(RETRY_DELAY * (attempt + 1))
            
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if attempt == MAX_RETRIES - 1:  # Last attempt
                return get_fallback_response("connection")
            time.sleep(RETRY_DELAY * (attempt + 1))
    
    return get_fallback_response("default")

# Add compatibility function for the old HF model loading call
def load_hf_model():
    """Compatibility function that returns placeholders since we're using Ollama now"""
    print("Using Ollama LLM at", OLLAMA_URL, "with model", OLLAMA_MODEL)
    return True, None, None
