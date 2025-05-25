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

async def handle_response_feedback(message, response):
    """
    Handle response and feedback for a message.
    Returns True if response was successfully sent.
    """
    try:
        # Send response
        sent_message = await message.channel.send(response)
        
        # Add reaction options for feedback
        await sent_message.add_reaction('👍')  # thumbs up
        await sent_message.add_reaction('👎')  # thumbs down
        
        # Update user feedback tracking
        user_id = str(message.author.id)
        feedback_scores, user_feedback = load_feedback()
        
        if user_id not in user_feedback:
            user_feedback[user_id] = {'responses': 0, 'feedback': {'positive': 0, 'negative': 0}}
        
        user_feedback[user_id]['responses'] += 1
        save_user_feedback(user_feedback)
        
        return True
    except Exception as e:
        print(f"Error handling response feedback: {e}")
        return False

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

async def handle_response_feedback(message, response):
    """
    Handle response and feedback for a message.
    Returns True if response was successfully sent.
    """
    try:
        # Send response
        sent_message = await message.channel.send(response)
        
        # Add reaction options for feedback
        await sent_message.add_reaction('👍')  # thumbs up
        await sent_message.add_reaction('👎')  # thumbs down
        
        # Update user feedback tracking
        user_id = str(message.author.id)
        feedback_scores, user_feedback = load_feedback()
        
        if user_id not in user_feedback:
            user_feedback[user_id] = {'responses': 0, 'feedback': {'positive': 0, 'negative': 0}}
        
        user_feedback[user_id]['responses'] += 1
        save_user_feedback(user_feedback)
        
        return True
    except Exception as e:
        print(f"Error handling response feedback: {e}")
        return False
