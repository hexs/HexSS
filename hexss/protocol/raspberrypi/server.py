import json
import time
import logging
from flask import Flask, render_template_string, jsonify, request, Response

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Machine IO Controller</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; padding: 20px; color: #333; }
        h1 { text-align: center; margin-bottom: 5px; }

        .container { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; margin-top: 20px; }
        .panel { background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 20px; width: 400px; }
        .panel h2 { border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 0; }

        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
        th { font-weight: 600; color: #555; }

        /* Status Badges */
        .status { padding: 5px 10px; border-radius: 15px; font-size: 0.85em; font-weight: bold; min-width: 50px; text-align: center; display: inline-block; }
        .status-on { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status-off { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }

        /* Connection Indicator */
        #conn-wrapper { text-align: center; font-size: 0.85rem; color: #666; margin-bottom: 20px; }
        .dot { height: 10px; width: 10px; background-color: #bbb; border-radius: 50%; display: inline-block; margin-right: 6px; }
        .dot.connected { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
        .dot.error { background-color: #dc3545; }

        /* Buttons */
        .btn { 
            background-color: #007bff; color: white; border: none; padding: 6px 14px; 
            border-radius: 4px; cursor: pointer; transition: all 0.2s; font-size: 0.9em;
        }
        .btn:hover { background-color: #0056b3; }
        .btn:active { transform: scale(0.96); }
        .btn:disabled { background-color: #ccc; cursor: not-allowed; }
    </style>
</head>
<body>
    <h1>Machine IO Dashboard</h1>
    <div id="conn-wrapper">
        <span class="dot" id="status-dot"></span>
        <span id="status-text">Connecting...</span>
    </div>

    <div class="container">
        <div class="panel">
            <h2>Inputs</h2>
            <table id="inputs-table">
                <thead><tr><th>Name</th><th>Pin</th><th>State</th></tr></thead>
                <tbody><tr><td colspan="3">Loading...</td></tr></tbody>
            </table>
        </div>

        <div class="panel">
            <h2>Outputs</h2>
            <table id="outputs-table">
                <thead><tr><th>Name</th><th>Pin</th><th>State</th><th>Control</th></tr></thead>
                <tbody><tr><td colspan="4">Loading...</td></tr></tbody>
            </table>
        </div>
    </div>

    <script>
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        let eventSource = null;

        function connectSSE() {
            if (eventSource) eventSource.close();

            eventSource = new EventSource("/api/socket/status");

            eventSource.onopen = function() {
                statusDot.className = 'dot connected';
                statusText.innerText = "Live System Connected";
                enableButtons(true);
            };

            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    renderInputs(data.inputs);
                    renderOutputs(data.outputs);
                } catch (e) {
                    console.error("Data parse error", e);
                }
            };

            eventSource.onerror = function(err) {
                statusDot.className = 'dot error';
                statusText.innerText = "Connection Lost - Reconnecting...";
                enableButtons(false);
            };
        }

        function renderInputs(items) {
            const tbody = document.querySelector('#inputs-table tbody');
            tbody.innerHTML = items.map(item => `
                <tr>
                    <td>${item.name}</td>
                    <td>GPIO ${item.pin}</td>
                    <td><span class="status ${item.value ? 'status-on' : 'status-off'}">
                        ${item.value ? 'HIGH' : 'LOW'}
                    </span></td>
                </tr>
            `).join('');
        }

        function renderOutputs(items) {
            const tbody = document.querySelector('#outputs-table tbody');
            tbody.innerHTML = items.map(item => `
                <tr>
                    <td>${item.name}</td>
                    <td>GPIO ${item.pin}</td>
                    <td><span class="status ${item.value ? 'status-on' : 'status-off'}">
                        ${item.value ? 'ON' : 'OFF'}
                    </span></td>
                    <td>
                        <button class="btn" onclick="toggle('${item.name}')">Toggle</button>
                    </td>
                </tr>
            `).join('');
        }

        function toggle(name) {
            fetch('/api/toggle/' + encodeURIComponent(name), { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if(data.error) alert("Error: " + data.error);
                })
                .catch(err => console.error("Toggle failed", err));
        }

        function enableButtons(enabled) {
            document.querySelectorAll('.btn').forEach(btn => btn.disabled = !enabled);
        }

        connectSSE();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


def get_io_snapshot(io_controller):
    def _serialize_pin(device):
        pin_num = device.pin.number if hasattr(device.pin, 'number') else device.pin
        return {
            'name': device.name,
            'pin': pin_num,
            'value': int(device.value)
        }

    return {
        'inputs': [_serialize_pin(d) for d in io_controller.input.inputs],
        'outputs': [_serialize_pin(d) for d in io_controller.output.outputs]
    }


@app.route('/api/status')
def get_status():
    data = app.config['data']
    return jsonify(get_io_snapshot(data['io']))


@app.route("/api/socket/status")
def api_socket_status():
    data = app.config['data']
    io = data['io']

    def generate():
        last_payload = None
        try:
            while True:
                snapshot = get_io_snapshot(io)
                payload = json.dumps(snapshot, ensure_ascii=False)
                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"

                time.sleep(0.05)
        except GeneratorExit:
            pass

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        },
    )


@app.route('/api/toggle/<name>', methods=['POST'])
def toggle_output(name):
    data = app.config['data']
    io = data['io']

    try:
        device = io.output.get(name)
        device.toggle()
        return jsonify({'success': True, 'new_value': int(device.value)})
    except ValueError:
        return jsonify({'error': f"Device '{name}' not found"}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run(data):
    host = data.get('host', '0.0.0.0')
    port = data.get('port', 2003)
    app.config['data'] = data
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
