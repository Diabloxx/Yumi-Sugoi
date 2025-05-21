import os
import json

FEEDBACK_FILE = 'feedback_scores.json'
USER_FEEDBACK_FILE = 'user_feedback.json'

def load_feedback():
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            feedback_scores = json.load(f)
    else:
        feedback_scores = {}
    if os.path.exists(USER_FEEDBACK_FILE):
        with open(USER_FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            user_feedback = json.load(f)
    else:
        user_feedback = {}
    return feedback_scores, user_feedback

def save_feedback_scores(feedback_scores):
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(feedback_scores, f, ensure_ascii=False, indent=2)

def save_user_feedback(user_feedback):
    with open(USER_FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_feedback, f, ensure_ascii=False, indent=2)

def reset_feedback(feedback_scores, question):
    q = question.lower().strip()
    if q in feedback_scores:
        feedback_scores[q] = {'up': 0, 'down': 0}
        save_feedback_scores(feedback_scores)
        return True
    return False

def export_feedback(feedback_scores, filename='feedback_export.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(feedback_scores, f, ensure_ascii=False, indent=2)
    return filename

def export_user_feedback(user_feedback, filename='user_feedback_export.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(user_feedback, f, ensure_ascii=False, indent=2)
    return filename

def get_user_feedback_stats(user_feedback, user_id):
    return user_feedback.get(str(user_id))
