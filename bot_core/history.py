import os
import json
from collections import defaultdict, deque

CONVO_HISTORY_FILE = 'convo_history.json'

def load_convo_history():
    if os.path.exists(CONVO_HISTORY_FILE):
        with open(CONVO_HISTORY_FILE, 'r', encoding='utf-8') as f:
            raw_history = json.load(f)
            convo_history = defaultdict(lambda: deque(maxlen=10))
            for k, v in raw_history.items():
                convo_history[int(k)] = deque(v, maxlen=10)
            return convo_history
    return defaultdict(lambda: deque(maxlen=10))

def save_convo_history(convo_history):
    serializable = {str(k): list(v) for k, v in convo_history.items()}
    with open(CONVO_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
