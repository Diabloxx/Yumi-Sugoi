import os
import json
import datasets

DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets')

def ensure_dataset(dataset_name, filename):
    if not os.path.exists(filename):
        print(f"Downloading {dataset_name} dataset...")
        # Pass trust_remote_code=True for datasets that require it
        if dataset_name in ['daily_dialog', 'cornell_movie_dialog', 'conv_ai_2', 'multi_woz_v22', 'empathetic_dialogues']:
            ds = datasets.load_dataset(dataset_name, trust_remote_code=True)
        else:
            ds = datasets.load_dataset(dataset_name)
        qa = {}
        if dataset_name == 'persona_chat':
            for dialog in ds['train']:
                for utterance in dialog['utterances']:
                    history = utterance['history']
                    candidates = utterance['candidates']
                    if history and candidates:
                        qa[history[-1].lower()] = candidates[0]
        elif dataset_name == 'daily_dialog':
            for dialog in ds['train']:
                utterances = dialog['dialog']
                for i in range(len(utterances)-1):
                    qa[utterances[i].lower()] = utterances[i+1]
        elif dataset_name == 'cornell_movie_dialog':
            print(f"cornell_movie_dialog: ds['train'] length = {len(ds['train'])}")
            if len(ds['train']) > 0:
                print(f"cornell_movie_dialog: first item keys = {list(ds['train'][0].keys())}")
            for conv in ds['train']:
                lines = conv.get('utterance', {}).get('text', [])
                if not isinstance(lines, list) or len(lines) < 2:
                    continue
                for i in range(len(lines)-1):
                    q = lines[i].strip().lower()
                    a = lines[i+1].strip()
                    if q and a:
                        qa[q] = a
        elif dataset_name == 'empathetic_dialogues':
            for row in ds['train']:
                context = row.get('context', '').strip().lower()
                utterance = row.get('utterance', '').strip()
                if context and utterance:
                    qa[context] = utterance
        elif dataset_name == 'multi_woz_v22':
            for dialog in ds['train']:
                dialogue = dialog.get('dialogue', [])
                for i in range(len(dialogue)-1):
                    q = dialogue[i].get('text', '') if isinstance(dialogue[i], dict) else str(dialogue[i])
                    a = dialogue[i+1].get('text', '') if isinstance(dialogue[i+1], dict) else str(dialogue[i+1])
                    q = q.strip().lower()
                    a = a.strip()
                    if q and a:
                        qa[q] = a
        elif dataset_name == 'conv_ai_2':
            for dialog in ds['train']:
                utterances = dialog.get('dialog', [])
                for i in range(len(utterances)-1):
                    q = utterances[i].get('text', '').strip().lower()
                    a = utterances[i+1].get('text', '').strip()
                    if q and a:
                        qa[q] = a
        elif dataset_name == 'OpenAssistant/oasst1':
            if len(ds['train']) > 0:
                print(f"oasst1: first item = {json.dumps(ds['train'][0], indent=2)}")
            for conv in ds['train']:
                messages = conv.get('messages', [])
                for i in range(len(messages)-1):
                    q = messages[i].get('content', '').strip().lower()
                    a = messages[i+1].get('content', '').strip()
                    if q and a and messages[i].get('role') == 'user' and messages[i+1].get('role') == 'assistant':
                        qa[q] = a
        elif dataset_name == 'OpenAssistant/guanaco':
            for conv in ds['train']:
                messages = conv.get('conversations', [])
                for i in range(len(messages)-1):
                    q = messages[i].get('value', '').strip().lower()
                    a = messages[i+1].get('value', '').strip()
                    if q and a and messages[i].get('from') == 'human' and messages[i+1].get('from') == 'gpt':
                        qa[q] = a
        elif dataset_name == 'sharegpt':
            for conv in ds['train']:
                messages = conv.get('conversations', [])
                for i in range(len(messages)-1):
                    q = messages[i].get('value', '').strip().lower()
                    a = messages[i+1].get('value', '').strip()
                    if q and a and messages[i].get('from') == 'human' and messages[i+1].get('from') == 'gpt':
                        qa[q] = a
        elif dataset_name == 'HuggingFaceH4/ultrachat_200k':
            for conv in ds['train']:
                messages = conv.get('messages', [])
                for i in range(len(messages)-1):
                    q = messages[i].get('content', '').strip().lower()
                    a = messages[i+1].get('content', '').strip()
                    if q and a and messages[i].get('role') == 'user' and messages[i+1].get('role') == 'assistant':
                        qa[q] = a
        elif dataset_name == 'Anthropic/hh-rlhf':
            for row in ds['train']:
                chosen = row.get('chosen', {}).get('messages', [])
                for i in range(len(chosen)-1):
                    q = chosen[i].get('content', '').strip().lower()
                    a = chosen[i+1].get('content', '').strip()
                    if q and a and chosen[i].get('role') == 'user' and chosen[i+1].get('role') == 'assistant':
                        qa[q] = a
        elif dataset_name == 'tatsu-lab/alpaca':
            for row in ds['train']:
                q = row.get('instruction', '').strip().lower()
                a = row.get('output', '').strip()
                if q and a:
                    qa[q] = a
        elif dataset_name == 'databricks/databricks-dolly-15k':
            for row in ds['train']:
                q = row.get('instruction', '').strip().lower()
                a = row.get('response', '').strip()
                if q and a:
                    qa[q] = a
        elif dataset_name == 'stanfordnlp/SHP':
            for row in ds['train']:
                history = row.get('history', [])
                prompt = row.get('prompt', '').strip().lower()
                chosen = row.get('chosen', '').strip()
                if history and prompt and chosen:
                    q = ' '.join(history + [prompt])
                    qa[q] = chosen
        elif dataset_name == 'yizhongw/self-instruct':
            for row in ds['train']:
                q = row.get('instruction', '').strip().lower()
                a = row.get('output', '').strip()
                if q and a:
                    qa[q] = a
        elif dataset_name == 'facebook/blenderbot-3B':
            for row in ds['train']:
                q = row.get('context', '').strip().lower()
                a = row.get('response', '').strip()
                if q and a:
                    qa[q] = a
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(qa, f, ensure_ascii=False, indent=2)
        print(f"Saved {dataset_name} to {filename} with {len(qa)} Q&A pairs.")
    else:
        print(f"{filename} already exists. Skipping download.")

def load_py_qa_dataset(pyfile):
    import importlib.util
    import sys
    module_name = os.path.splitext(os.path.basename(pyfile))[0]
    spec = importlib.util.spec_from_file_location(module_name, pyfile)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    for var in dir(module):
        value = getattr(module, var)
        if isinstance(value, dict):
            return value
    return {}

def load_all_datasets():
    DATASET_FILE = os.path.join(DATASET_DIR, 'chatbot_dataset.json')
    ADDITIONAL_DATASETS = [
        ("empathetic_dialogues", os.path.join(DATASET_DIR, "empathetic_dialogues.json")),
        ("conv_ai_2", os.path.join(DATASET_DIR, "conv_ai_2.json")),
        ("multi_woz_v22", os.path.join(DATASET_DIR, "multi_woz_v22.json")),
        ("OpenAssistant/oasst1", os.path.join(DATASET_DIR, "oasst1.json")),
        ("ShareGPT/sharegpt", os.path.join(DATASET_DIR, "sharegpt.json")),
        ("HuggingFaceH4/ultrachat_200k", os.path.join(DATASET_DIR, "ultrachat_200k.json")),
        ("Anthropic/hh-rlhf", os.path.join(DATASET_DIR, "hh_rlhf.json")),
        ("tatsu-lab/alpaca", os.path.join(DATASET_DIR, "alpaca.json")),
        ("databricks/databricks-dolly-15k", os.path.join(DATASET_DIR, "dolly_15k.json")),
        ("stanfordnlp/SHP", os.path.join(DATASET_DIR, "shp.json")),
        ("yizhongw/self-instruct", os.path.join(DATASET_DIR, "self_instruct.json")),
        ("facebook/blenderbot-3B", os.path.join(DATASET_DIR, "blenderbot-3B.json")),
        # ("dialogsum", os.path.join(DATASET_DIR, "dialogsum.json")),  # Removed, not available
    ]
    # Download core datasets
    try:
        ensure_dataset('daily_dialog', 'daily_dialog.json')
    except Exception as e:
        print(f"Could not download daily_dialog: {e}")
    try:
        ensure_dataset('cornell_movie_dialog', 'cornell_movie_dialog.json')
    except Exception as e:
        print(f"Could not download cornell_movie_dialog: {e}")
    for dataset_name, filename in ADDITIONAL_DATASETS:
        try:
            ensure_dataset(dataset_name, filename)
        except Exception as e:
            print(f"Could not download {dataset_name}: {e}")
    # Merge all datasets
    if os.path.exists(DATASET_FILE):
        with open(DATASET_FILE, 'r', encoding='utf-8') as f:
            qa_pairs = json.load(f)
    else:
        qa_pairs = {}
    for dataset_file in [
        os.path.join(DATASET_DIR, "daily_dialog.py"), os.path.join(DATASET_DIR, "cornell_movie_dialog.py")
    ]:
        if os.path.exists(dataset_file):
            dataset_qa = load_py_qa_dataset(dataset_file)
            for k, v in dataset_qa.items():
                if isinstance(k, str) and isinstance(v, str):
                    qa_pairs[k] = v
    for dataset_file in [
        os.path.join(DATASET_DIR, "daily_dialog.json"), os.path.join(DATASET_DIR, "cornell_movie_dialog.json"), os.path.join(DATASET_DIR, "empathetic_dialogues.json"), os.path.join(DATASET_DIR, "conv_ai_2.json"), os.path.join(DATASET_DIR, "multi_woz_v22.json"),
        os.path.join(DATASET_DIR, "oasst1.json"), os.path.join(DATASET_DIR, "guanaco.json"), os.path.join(DATASET_DIR, "sharegpt.json"), os.path.join(DATASET_DIR, "ultrachat_200k.json"), os.path.join(DATASET_DIR, "hh_rlhf.json"), os.path.join(DATASET_DIR, "alpaca.json"), os.path.join(DATASET_DIR, "dolly_15k.json"),
        os.path.join(DATASET_DIR, "shp.json"), os.path.join(DATASET_DIR, "self_instruct.json"), os.path.join(DATASET_DIR, "blenderbot-3B.json")
        # os.path.join(DATASET_DIR, "dialogsum.json"),  # Removed
    ]:
        if os.path.exists(dataset_file):
            with open(dataset_file, 'r', encoding='utf-8') as f:
                dataset_qa = json.load(f)
                for k, v in dataset_qa.items():
                    if isinstance(k, str) and isinstance(v, str):
                        qa_pairs[k] = v
    mistress_dataset_path = os.path.join(DATASET_DIR, "mistress_dataset.json")
    if os.path.exists(mistress_dataset_path):
        with open(mistress_dataset_path, 'r', encoding='utf-8') as f:
            mistress_qa = json.load(f)
            for k, v in mistress_qa.items():
                if isinstance(k, str) and isinstance(v, str):
                    qa_pairs[k] = v
    with open(DATASET_FILE, 'w', encoding='utf-8') as f:
        json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
    print(f"Yumi loaded {len(qa_pairs)} Q&A pairs from datasets!")
    return qa_pairs
