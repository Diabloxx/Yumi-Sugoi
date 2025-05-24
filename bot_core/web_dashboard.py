import threading
from flask import Flask, jsonify, render_template, request, send_from_directory
import os

def create_dashboard_app(PERSONA_MODES, custom_personas, get_level, get_xp):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    app = Flask('yumi_dashboard', static_folder=static_dir, template_folder=template_dir)

    # --- Persona Management ---
    @app.route('/api/personas')
    def api_personas():
        return jsonify({'default': PERSONA_MODES, 'custom': list(custom_personas.keys())})

    @app.route('/api/persona', methods=['POST'])
    def api_add_persona():
        from .main import custom_personas, save_json_file, CUSTOM_PERSONAS_FILE
        data = request.json
        name = data.get('name', '').strip().lower()
        if not name:
            return jsonify({'error': 'No name'}), 400
        if name in custom_personas:
            return jsonify({'error': 'Persona exists'}), 400
        custom_personas[name] = {'creator': 'dashboard', 'description': ''}
        save_json_file(CUSTOM_PERSONAS_FILE, custom_personas)
        return jsonify({'success': True})

    @app.route('/api/persona/<name>', methods=['DELETE'])
    def api_delete_persona(name):
        from .main import custom_personas, save_json_file, CUSTOM_PERSONAS_FILE
        if name in custom_personas:
            del custom_personas[name]
            save_json_file(CUSTOM_PERSONAS_FILE, custom_personas)
            return jsonify({'success': True})
        return jsonify({'error': 'Not found'}), 404

    # --- Server and Channel Info (merged) ---
    @app.route('/api/servers')
    def api_servers():
        from .main import bot
        servers = []
        for guild in bot.guilds:
            channels = [
                {'id': c.id, 'name': c.name, 'type': str(c.type)}
                for c in guild.text_channels
            ]
            servers.append({
                'id': guild.id,
                'name': guild.name,
                'member_count': guild.member_count,
                'channels': channels
            })
        return jsonify(servers)

    # --- Server Settings ---
    @app.route('/api/server/<int:server_id>/settings', methods=['GET', 'POST'])
    def api_server_settings(server_id):
        from .main import CONTEXT_MODES, LOCKED_CHANNELS, PERSONA_MODES, custom_personas, save_lockdown_channels
        OFFICIAL_SERVER_ID = 1375103404493373510
        if server_id != OFFICIAL_SERVER_ID:
            return jsonify({'error': 'Not allowed'}), 403
        all_modes = list(PERSONA_MODES) + list(custom_personas.keys())
        if request.method == 'GET':
            settings = {
                'mode': CONTEXT_MODES.get(f"guild_{server_id}", 'normal'),
                'locked_channels': list(LOCKED_CHANNELS.get(server_id, [])),
                'lockdown': bool(LOCKED_CHANNELS.get(server_id)),
                'all_modes': all_modes
            }
            return jsonify(settings)
        elif request.method == 'POST':
            data = request.json
            if 'mode' in data:
                CONTEXT_MODES[f"guild_{server_id}"] = data['mode']
            if 'locked_channels' in data:
                LOCKED_CHANNELS[server_id] = set(data['locked_channels'])
            if 'lockdown' in data:
                if data['lockdown'] and not LOCKED_CHANNELS.get(server_id):
                    LOCKED_CHANNELS[server_id] = set()
                if not data['lockdown']:
                    LOCKED_CHANNELS[server_id] = set()
            import json
            MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'yumi_modes.json')
            with open(MODE_FILE, 'w', encoding='utf-8') as f:
                json.dump(CONTEXT_MODES, f, ensure_ascii=False, indent=2)
            save_lockdown_channels()
            return jsonify({'success': True})

    # --- User Management (grouped) ---
    @app.route('/api/users/search')
    def api_user_search():
        from .main import bot
        q = request.args.get('q', '').lower()
        users = []
        for guild in bot.guilds:
            for member in guild.members:
                if q in member.name.lower() or q in str(member.id):
                    users.append({'id': member.id, 'name': member.name, 'guild': guild.name})
        return jsonify(users)

    @app.route('/api/user/<int:user_id>')
    def api_user_info(user_id):
        from .main import user_xp, user_facts, bot
        user = None
        for guild in bot.guilds:
            m = guild.get_member(user_id)
            if m:
                user = m
                break
        if not user:
            return jsonify({'error': 'User not found'}), 404
        info = {
            'id': user.id,
            'name': user.name,
            'xp': user_xp.get(str(user.id), {}).get('xp', 0),
            'level': user_xp.get(str(user.id), {}).get('level', 1),
            'facts': user_facts.get(str(user.id), ''),
            'joined_at': str(user.joined_at) if hasattr(user, 'joined_at') else '',
            'infractions': []
        }
        return jsonify(info)

    @app.route('/api/user/<int:user_id>/action', methods=['POST'])
    def api_user_action(user_id):
        from .main import bot
        data = request.json
        action = data.get('action')
        user = None
        for guild in bot.guilds:
            m = guild.get_member(user_id)
            if m:
                user = m
                break
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if action == 'kick':
            bot.loop.create_task(user.kick())
        elif action == 'ban':
            bot.loop.create_task(user.ban())
        elif action == 'unban':
            pass
        else:
            return jsonify({'error': 'Unknown action'}), 400
        return jsonify({'success': True})

    @app.route('/api/user/<int:user_id>/xp')
    def api_user_xp(user_id):
        from .main import get_level, get_xp
        return jsonify({'level': get_level(user_id), 'xp': get_xp(user_id)})

    # --- Scheduled Tasks ---
    @app.route('/api/scheduled', methods=['GET', 'POST'])
    def api_scheduled():
        from .main import scheduled_announcements, save_json_file, SCHEDULED_ANNOUNCEMENTS_FILE
        if request.method == 'GET':
            return jsonify(scheduled_announcements)
        elif request.method == 'POST':
            data = request.json
            scheduled_announcements.append(data)
            save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
            return jsonify({'success': True})

    @app.route('/api/scheduled/<int:index>', methods=['DELETE', 'PUT'])
    def api_scheduled_edit(index):
        from .main import scheduled_announcements, save_json_file, SCHEDULED_ANNOUNCEMENTS_FILE
        if request.method == 'DELETE':
            if 0 <= index < len(scheduled_announcements):
                scheduled_announcements.pop(index)
                save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
                return jsonify({'success': True})
            return jsonify({'error': 'Not found'}), 404
        elif request.method == 'PUT':
            data = request.json
            if 0 <= index < len(scheduled_announcements):
                scheduled_announcements[index] = data
                save_json_file(SCHEDULED_ANNOUNCEMENTS_FILE, scheduled_announcements)
                return jsonify({'success': True})
            return jsonify({'error': 'Not found'}), 404

    # --- Moderation, Analytics, Audit Log, Chat Logs ---
    @app.route('/api/moderation_logs')
    def api_moderation_logs():
        import json
        logs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'moderation_logs.json')
        try:
            with open(logs_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except Exception:
            logs = []
        # Add fallback: if logs is a dict, convert to list
        if isinstance(logs, dict):
            logs = list(logs.values())
        return jsonify({'logs': logs})

    @app.route('/api/analytics')
    def api_analytics():
        from .main import bot
        analytics = {
            'guild_count': len(bot.guilds),
            'user_count': sum(len(guild.members) for guild in bot.guilds),
            'message_count': sum(getattr(guild, 'message_count', 0) for guild in bot.guilds),
            'channels': sum(len(guild.text_channels) for guild in bot.guilds),
        }
        return jsonify(analytics)

    @app.route('/api/auditlog')
    def api_auditlog():
        import json
        logs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'audit_log.json')
        try:
            with open(logs_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except Exception:
            logs = []
        if isinstance(logs, dict):
            logs = list(logs.values())
        return jsonify({'logs': logs})

    @app.route('/api/chat_logs')
    def api_chat_logs():
        import json
        convo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'convo_history.json')
        try:
            with open(convo_path, 'r', encoding='utf-8') as f:
                convo = json.load(f)
        except Exception:
            return jsonify({'error': 'Could not read chat logs'}), 500
        # If convo is a dict, flatten to list
        if isinstance(convo, dict):
            convo = [v for v in convo.values() if isinstance(v, list)]
        return jsonify({'logs': convo})

    # --- Live Chat ---
    @app.route('/api/live_chat', methods=['GET', 'POST'])
    def api_live_chat():
        from .main import bot
        if request.method == 'GET':
            server_id = int(request.args.get('server_id', 0))
            channel_id = int(request.args.get('channel_id', 0))
            guild = next((g for g in bot.guilds if g.id == server_id), None)
            channel = None
            if guild:
                channel = next((c for c in guild.text_channels if c.id == channel_id), None)
            messages = []
            if channel:
                try:
                    # Only fetch last 50 messages for performance
                    history = []
                    async def fetch_history():
                        async for msg in channel.history(limit=50):
                            history.append(msg)
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(fetch_history())
                    for msg in reversed(history):
                        messages.append({
                            'author': msg.author.name,
                            'content': msg.content,
                            'timestamp': str(msg.created_at),
                            'id': msg.id
                        })
                except Exception:
                    pass
            return jsonify({'messages': messages})
        elif request.method == 'POST':
            data = request.json
            server_id = int(data.get('server_id', 0))
            channel_id = int(data.get('channel_id', 0))
            message = data.get('message', '')
            from .main import bot
            guild = next((g for g in bot.guilds if g.id == server_id), None)
            channel = None
            if guild:
                channel = next((c for c in guild.text_channels if c.id == channel_id), None)
            if channel and message:
                try:
                    bot.loop.create_task(channel.send(message))
                    return jsonify({'success': True})
                except Exception:
                    return jsonify({'error': 'Failed to send message'}), 500
            return jsonify({'error': 'Invalid server/channel/message'}), 400

    # --- Dashboard UI ---
    @app.route('/')
    def dashboard_home():
        return render_template('dashboard.html')

    @app.route('/static/<path:path>')
    def send_static(path):
        return send_from_directory('static', path)

    return app

# --- Threaded runner ---
def run_dashboard(PERSONA_MODES, custom_personas, get_level, get_xp):
    app = create_dashboard_app(PERSONA_MODES, custom_personas, get_level, get_xp)
    app.run(port=5005)

def start_dashboard_thread(PERSONA_MODES, custom_personas, get_level, get_xp):
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        args=(PERSONA_MODES, custom_personas, get_level, get_xp),
        daemon=True
    )
    dashboard_thread.start()
