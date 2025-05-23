import threading
from flask import Flask, jsonify, render_template, request
import os

# --- Static files and template setup ---
from flask import send_from_directory

def create_dashboard_app(PERSONA_MODES, custom_personas, get_level, get_xp):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    app = Flask('yumi_dashboard', static_folder=static_dir, template_folder=template_dir)

    # --- API Endpoints ---
    @app.route('/api/personas')
    def api_personas():
        return jsonify({
            'default': PERSONA_MODES,
            'custom': list(custom_personas.keys())
        })

    @app.route('/api/persona', methods=['POST'])
    def api_add_persona():
        data = request.json
        name = data.get('name', '').strip().lower()
        if not name:
            return jsonify({'error': 'No name'}), 400
        from .main import custom_personas, save_json_file, CUSTOM_PERSONAS_FILE
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

    @app.route('/api/user/<int:user_id>/xp')
    def api_user_xp(user_id):
        return jsonify({
            'level': get_level(user_id),
            'xp': get_xp(user_id)
        })

    @app.route('/api/servers')
    def api_servers():
        # Import bot from main.py
        from .main import bot
        servers = []
        for guild in bot.guilds:
            servers.append({
                'id': guild.id,
                'name': guild.name,
                'member_count': guild.member_count
            })
        return jsonify(servers)

    @app.route('/api/server/<int:server_id>/settings', methods=['GET', 'POST'])
    def api_server_settings(server_id):
        OFFICIAL_SERVER_ID = 123456789012345678  # <-- Replace with your actual server ID
        if server_id != OFFICIAL_SERVER_ID:
            return jsonify({'error': 'Not allowed'}), 403
        from .main import CONTEXT_MODES, LOCKED_CHANNELS, PERSONA_MODES, custom_personas, save_lockdown_channels
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
                    # If enabling lockdown but no channels, add a placeholder (must be set by user)
                    LOCKED_CHANNELS[server_id] = set()
                if not data['lockdown']:
                    LOCKED_CHANNELS[server_id] = set()
            # Save changes
            import json, os
            MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'yumi_modes.json')
            with open(MODE_FILE, 'w', encoding='utf-8') as f:
                json.dump(CONTEXT_MODES, f, ensure_ascii=False, indent=2)
            save_lockdown_channels()
            return jsonify({'success': True})

    @app.route('/api/server/<int:server_id>/logs')
    def api_server_logs(server_id):
        # TODO: Replace with real log retrieval logic
        # Example: Only allow for official server
        OFFICIAL_SERVER_ID = 123456789012345678  # <-- Replace with your actual server ID
        if server_id != OFFICIAL_SERVER_ID:
            return jsonify({'error': 'Not allowed'}), 403
        # Placeholder: return mock logs
        logs = [
            "[2025-05-23 12:00] User123 deleted a message in #general.",
            "[2025-05-23 12:05] User456 joined the server.",
            "[2025-05-23 12:10] Yumi was locked down to #bot-commands."
        ]
        return jsonify({'logs': logs})

    # --- LIVE CHAT CONSOLE ---
    @app.route('/api/servers_channels')
    def api_servers_channels():
        from .main import bot
        servers = []
        for guild in bot.guilds:
            channels = [
                {'id': c.id, 'name': c.name, 'type': str(c.type)}
                for c in guild.text_channels
            ]
            servers.append({'id': guild.id, 'name': guild.name, 'channels': channels})
        return jsonify(servers)

    @app.route('/api/send_message', methods=['POST'])
    def api_send_message():
        data = request.json
        server_id = int(data['server_id'])
        channel_id = int(data['channel_id'])
        content = data['content']
        from .main import bot
        channel = None
        for guild in bot.guilds:
            if guild.id == server_id:
                channel = guild.get_channel(channel_id)
                break
        if channel:
            bot.loop.create_task(channel.send(content))
            return jsonify({'success': True})
        return jsonify({'error': 'Channel not found'}), 404

    @app.route('/api/recent_messages/<int:server_id>/<int:channel_id>')
    def api_recent_messages(server_id, channel_id):
        # Placeholder: return empty or mock data
        # Real implementation would require message cache or DB
        return jsonify({'messages': []})

    # --- USER MANAGEMENT ---
    @app.route('/api/users/search')
    def api_user_search():
        q = request.args.get('q', '').lower()
        from .main import bot
        users = []
        for guild in bot.guilds:
            for member in guild.members:
                if q in member.name.lower() or q in str(member.id):
                    users.append({'id': member.id, 'name': member.name, 'guild': guild.name})
        return jsonify(users)

    @app.route('/api/user/<int:user_id>')
    def api_user_info(user_id):
        from .main import user_xp, user_facts
        # Find user in any guild
        from .main import bot
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
            'infractions': []  # TODO: Add real infractions
        }
        return jsonify(info)

    @app.route('/api/user/<int:user_id>/action', methods=['POST'])
    def api_user_action(user_id):
        data = request.json
        action = data.get('action')
        from .main import bot
        user = None
        for guild in bot.guilds:
            m = guild.get_member(user_id)
            if m:
                user = m
                break
        if not user:
            return jsonify({'error': 'User not found'}), 404
        # Only allow actions if bot has permission (placeholder logic)
        if action == 'kick':
            bot.loop.create_task(user.kick())
        elif action == 'ban':
            bot.loop.create_task(user.ban())
        elif action == 'unban':
            # Unban logic would need to find ban object
            pass
        else:
            return jsonify({'error': 'Unknown action'}), 400
        return jsonify({'success': True})

    # --- SCHEDULED TASKS ---
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

    # --- PLACEHOLDERS for analytics, moderation, audit log, etc. ---
    @app.route('/api/analytics')
    def api_analytics():
        return jsonify({'message': 'Analytics coming soon.'})

    @app.route('/api/auditlog')
    def api_auditlog():
        return jsonify({'message': 'Audit log coming soon.'})

    # --- Dashboard UI ---
    @app.route('/')
    def dashboard_home():
        return render_template('dashboard.html')

    # --- Static files (CSS, JS, icons) ---
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
