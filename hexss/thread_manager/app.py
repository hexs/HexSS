import json
import time
from flask import Flask, render_template, request, jsonify, Response
from waitress import serve

def run_server(manager, host='0.0.0.0', port=2000):
    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/status')
    def status():
        def status_stream():
            last_dump = None
            while True:
                current_dump = json.dumps(manager.get_status())
                if current_dump != last_dump:
                    yield f"data: {current_dump}\n\n"
                    last_dump = current_dump
                time.sleep(0.5)

        return Response(status_stream(), mimetype='text/event-stream')

    @app.route('/api/action', methods=['POST'])
    def action():
        req = request.get_json()
        task_id = req.get('task_id')
        action_type = req.get('action')

        if action_type == 'stop':
            manager.stop_task(task_id)
        elif action_type == 'restart':
            manager.restart_task(task_id)

        return jsonify({"success": True})

    print(f"🌐 Web Monitor started at: http://127.0.0.1:{port} (Silent Mode)")
    serve(app, host=host, port=port)