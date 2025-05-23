import threading
from flask import Flask, jsonify

def create_dashboard_app(PERSONA_MODES, custom_personas, get_level, get_xp):
    app = Flask('yumi_dashboard')

    @app.route('/api/personas')
    def api_personas():
        return jsonify({
            'default': PERSONA_MODES,
            'custom': list(custom_personas.keys())
        })

    @app.route('/api/user/<int:user_id>/xp')
    def api_user_xp(user_id):
        return jsonify({
            'level': get_level(user_id),
            'xp': get_xp(user_id)
        })

    return app

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
