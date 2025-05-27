import os
import json
import re
from collections import defaultdict, deque
from typing import Dict, List, Any, Deque

CONVO_HISTORY_FILE = 'convo_history.json'
# Store last 100 messages, but use a sliding window for context
TOTAL_HISTORY_LENGTH = 100  # Total messages to store
CONTEXT_WINDOW_SIZE = 30    # Messages to use for immediate context

def clean_response(response: str) -> str:
    """Clean the response of any fabricated dialogue and format issues."""
    if not response:
        return ''
    
    # Remove any fabricated dialogue patterns
    response = re.sub(r'\*[^*]+\*', '', response)  # Remove action text
    response = re.sub(r'<[^>]+>', '', response)  # Remove HTML-like tags
    
    # Clean up whitespace
    response = ' '.join(response.split())
    return response.strip()

def get_relevant_history(history_queue: Deque, message_type: str = None) -> List[Dict[str, Any]]:
    """Get relevant history based on message type and recency.
    
    Args:
        history_queue: The full conversation history queue
        message_type: Optional filter for specific types of messages
    
    Returns:
        List of relevant messages with priority to recent context
    """
    if not history_queue:
        return []

    # Convert deque to list for easier manipulation
    full_history = list(history_queue)
    
    # Always include the most recent messages for immediate context
    recent_context = full_history[-CONTEXT_WINDOW_SIZE:] if len(full_history) > CONTEXT_WINDOW_SIZE else full_history
    
    # For the remaining history, sample important messages
    older_history = full_history[:-CONTEXT_WINDOW_SIZE] if len(full_history) > CONTEXT_WINDOW_SIZE else []
    important_messages = []
    
    # Track the last few topics/statements to maintain continuity
    last_topic = None
    for msg in reversed(older_history):
        content = msg.get('content', '').lower()
        
        # Keep recall requests and their context (previous few messages)
        if 'recall' in content or 'remember' in content or 'what were we talking about' in content:
            idx = older_history.index(msg)
            # Get previous context
            start_idx = max(0, idx - 5)
            important_messages.extend(older_history[start_idx:idx + 1])
            
        # Keep questions and their answers
        elif '?' in content or any(w in content for w in ['who', 'what', 'when', 'where', 'why', 'how']):
            important_messages.append(msg)
            # Try to get the answer too if it exists
            idx = older_history.index(msg)
            if idx + 1 < len(older_history):
                important_messages.append(older_history[idx + 1])
        
        # Keep messages that indicate user status or activity
        elif any(w in content for w in ['at work', 'working', 'home', 'busy', 'free', 'available']):
            important_messages.append(msg)
            last_topic = 'status'
        
        # Keep messages with emotional content or user preferences
        elif any(w in content for w in ['love', 'hate', 'feel', 'think', 'believe', 'favorite', 'prefer', 'like', 'dislike']):
            important_messages.append(msg)
            last_topic = 'preferences'
        
        # Keep messages that might contain user facts
        elif any(w in content for w in ['my', 'i am', "i'm", 'i like', 'i want', 'i have', 'i do']):
            important_messages.append(msg)
            last_topic = 'facts'
            
        # Keep topic transitions to maintain context
        elif content.startswith(('so', 'anyway', 'but', 'however', 'speaking of')):
            important_messages.append(msg)
            # Include the previous message for context
            idx = older_history.index(msg)
            if idx > 0:
                important_messages.append(older_history[idx - 1])
        
        # If we're continuing a previous topic, include relevant messages
        elif last_topic:
            if (last_topic == 'status' and any(w in content for w in ['work', 'busy', 'free', 'time'])) or \
               (last_topic == 'preferences' and any(w in content for w in ['like', 'love', 'hate', 'feel'])) or \
               (last_topic == 'facts' and any(w in content for w in ['i', 'my', 'me'])):
                important_messages.append(msg)

    # Combine recent context with important older messages, removing duplicates
    all_relevant = recent_context + [msg for msg in important_messages 
                                   if msg not in recent_context]
    
    return all_relevant

def process_message_queue(queue: Deque) -> List[Dict[str, Any]]:
    """Process a queue of messages to ensure proper conversation flow."""
    processed = []
    current_user_msgs = []
    
    for msg in queue:
        if msg.get('role') == 'user':
            # Check for duplicated content due to double messages
            content = msg.get('content', '').strip()
            if not current_user_msgs or content != current_user_msgs[-1]:
                current_user_msgs.append(content)
        else:
            if current_user_msgs:
                # Combine multiple user messages into one context
                combined = ' '.join(filter(None, current_user_msgs))
                processed.append({'role': 'user', 'content': combined})
                current_user_msgs = []
            if msg.get('content'):
                # Clean assistant responses
                if msg.get('role') == 'assistant':
                    msg = dict(msg)
                    msg['content'] = clean_response(msg['content'])
                processed.append(msg)
    
    # Don't forget any remaining user messages
    if current_user_msgs:
        combined = ' '.join(filter(None, current_user_msgs))
        processed.append({'role': 'user', 'content': combined})
    
    return processed

def load_convo_history():
    """Load and clean conversation history."""
    if os.path.exists(CONVO_HISTORY_FILE):
        with open(CONVO_HISTORY_FILE, 'r', encoding='utf-8') as f:
            raw_history = json.load(f)
            convo_history = defaultdict(lambda: deque(maxlen=TOTAL_HISTORY_LENGTH))
            
            for k, v in raw_history.items():
                try:
                    key = int(k)
                except ValueError:
                    key = k
                
                # Clean and process the message queue
                queue = deque(v, maxlen=TOTAL_HISTORY_LENGTH)
                processed = process_message_queue(queue)
                
                # Clean responses and add to history
                cleaned_messages = []
                for msg in processed:
                    if msg.get('role') == 'assistant':
                        msg = dict(msg)
                        msg['content'] = clean_response(msg['content'])
                    if msg.get('content'):  # Only add non-empty messages
                        cleaned_messages.append(msg)
                
                convo_history[key] = deque(cleaned_messages, maxlen=TOTAL_HISTORY_LENGTH)
            return convo_history
    return defaultdict(lambda: deque(maxlen=TOTAL_HISTORY_LENGTH))

def format_message_for_context(msg: Dict[str, Any]) -> str:
    """Format a message for context in a way that preserves the conversation flow."""
    role = msg.get('role', '')
    content = msg.get('content', '').strip()
    if not content:
        return ''
    
    if role == 'user':
        return f"User said: {content}"
    elif role == 'assistant':
        return f"Yumi replied: {clean_response(content)}"
    return content

def save_convo_history(convo_history):
    """Save cleaned and processed conversation history."""
    cleaned_history = defaultdict(list)
    
    for k, v in convo_history.items():
        # Process and clean the message queue
        processed = process_message_queue(v)
        cleaned_messages = []
        
        for msg in processed:
            if msg.get('role') == 'assistant':
                msg = dict(msg)
                msg['content'] = clean_response(msg['content'])
            if msg.get('content'):  # Only save non-empty messages
                cleaned_messages.append(msg)
        
        cleaned_history[k] = cleaned_messages
    
    serializable = {str(k): v for k, v in cleaned_history.items()}
    with open(CONVO_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
