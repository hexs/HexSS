# server.py
import json
import time
import logging
from flask import Flask, render_template_string, jsonify, request, Response

app = Flask(__name__)

# Suppress default Flask logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PLC IO Controller</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; padding: 20px; color: #333; }
        h1 { text-align: center; margin-bottom: 5px; }

        .container { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; margin-top: 20px; }
        .panel { background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 20px; width: 450px; }
        .panel h2 { border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 0; }

        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
        th { font-weight: 600; color: #555; }

        .row-item { cursor: context-menu; transition: background 0.1s; }
        .row-item:hover { background-color: #f0f8ff; }

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

        /* --- Context Menu Styles --- */
        #context-menu {
            display: none;
            position: absolute;
            z-index: 1000;
            width: 160px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: 1px solid #ddd;
            overflow: hidden;
        }

        .menu-item {
            padding: 10px 15px;
            cursor: pointer;
            font-size: 0.9em;
            color: #333;
        }

        .menu-item:hover {
            background-color: #007bff;
            color: white;
        }

        .menu-divider {
            height: 1px;
            background-color: #eee;
            margin: 0;
            display: none;
        }
    </style>
</head>
<body>
    <h1>Machine IO Dashboard</h1>
    <div id="conn-wrapper">
        <span class="dot" id="status-dot"></span>
        <span id="status-text">Connecting...</span>
    </div>

    <div id="context-menu">
        <div id="menu-on" class="menu-item" onclick="handleMenuAction('on')">Turn On</div>
        <div id="menu-off" class="menu-item" onclick="handleMenuAction('off')">Turn Off</div>
        <div id="menu-toggle" class="menu-item" onclick="handleMenuAction('toggle')">Toggle</div>
        <div id="menu-sep" class="menu-divider"></div>
        <div id="menu-set" class="menu-item" onclick="handleMenuAction('set')">Set Value...</div>
    </div>

    <div class="container">
        <div class="panel">
            <h2>Inputs (X)</h2>
            <table id="inputs-table">
                <thead><tr><th>Name</th><th>Addr</th><th>State</th></tr></thead>
                <tbody><tr><td colspan="3">Waiting for data...</td></tr></tbody>
            </table>
        </div>

        <div class="panel">
            <h2>Outputs (Y)</h2>
            <table id="outputs-table">
                <thead><tr><th>Name</th><th>Addr</th><th>State</th><th>Control</th></tr></thead>
                <tbody><tr><td colspan="4">Waiting for data...</td></tr></tbody>
            </table>
        </div>

        <div class="panel">
            <h2>Registers (D/C/T)</h2>
            <table id="registers-table">
                <thead><tr><th>Name</th><th>Addr</th><th>Value</th></tr></thead>
                <tbody><tr><td colspan="3">Waiting for data...</td></tr></tbody>
            </table>
        </div>
    </div>

    <script>
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        const contextMenu = document.getElementById('context-menu');

        let eventSource = null;
        let selectedItemName = null;

        // --- Context Menu Logic ---
        document.addEventListener('click', () => {
            contextMenu.style.display = 'none';
        });

        function showContextMenu(event, name, type) {
            event.preventDefault();
            selectedItemName = name;

            const isOutput = (type === 'output');

            document.getElementById('menu-on').style.display = isOutput ? 'block' : 'none';
            document.getElementById('menu-off').style.display = isOutput ? 'block' : 'none';
            document.getElementById('menu-toggle').style.display = isOutput ? 'block' : 'none';

            document.getElementById('menu-sep').style.display = 'none';
            document.getElementById('menu-set').style.display = isOutput ? 'none' : 'block';

            contextMenu.style.top = `${event.pageY}px`;
            contextMenu.style.left = `${event.pageX}px`;
            contextMenu.style.display = 'block';
        }

        function handleMenuAction(action) {
            contextMenu.style.display = 'none';
            if (!selectedItemName) return;
            const name = selectedItemName;

            if (action === 'on') sendCommand(name, 1);
            else if (action === 'off') sendCommand(name, 0);
            else if (action === 'toggle') toggle(name);
            else if (action === 'set') {
                setTimeout(() => {
                    const val = prompt(`Enter new value for ${name}:`);
                    if (val !== null && val.trim() !== "") {
                        if (!isNaN(parseInt(val))) {
                            sendCommand(name, parseInt(val));
                        } else {
                            alert("Please enter a valid number.");
                        }
                    }
                }, 50);
            }
        }

        function sendCommand(name, value) {
            fetch('/api/set/' + encodeURIComponent(name), {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ value: value })
            })
            .then(res => res.json())
            .then(data => { if(data.error) alert("Error: " + data.error); })
            .catch(err => console.error("Command failed", err));
        }

        function toggle(name) {
            if(window.event) window.event.stopPropagation();

            fetch('/api/toggle/' + encodeURIComponent(name), { method: 'POST' })
            .then(res => res.json())
            .then(data => { if(data.error) alert("Error: " + data.error); })
            .catch(err => console.error("Toggle failed", err));
        }

        // --- SSE & Rendering ---

        function connectSSE() {
            if (eventSource) eventSource.close();
            eventSource = new EventSource("/api/socket/status");

            eventSource.onopen = function() {
                statusDot.className = 'dot connected';
                statusText.innerText = "System Online";
            };

            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    renderInputs(data.inputs);
                    renderOutputs(data.outputs);
                    renderRegisters(data.registers);
                } catch (e) {
                    console.error("Data parse error", e);
                }
            };

            eventSource.onerror = function() {
                statusDot.className = 'dot error';
                statusText.innerText = "Reconnecting...";
            };
        }

        function renderInputs(items) {
            const tbody = document.querySelector('#inputs-table tbody');
            if (items.length === 0) { tbody.innerHTML = '<tr><td colspan="3">No inputs</td></tr>'; return; }
            tbody.innerHTML = items.map(item => `
                <tr class="row-item">
                    <td>${item.name}</td>
                    <td>${item.pin}</td>
                    <td><span class="status ${item.value ? 'status-on' : 'status-off'}">${item.value ? 'ON' : 'OFF'}</span></td>
                </tr>
            `).join('');
        }

        function renderOutputs(items) {
            const tbody = document.querySelector('#outputs-table tbody');
            if (items.length === 0) { tbody.innerHTML = '<tr><td colspan="4">No outputs</td></tr>'; return; }
            tbody.innerHTML = items.map(item => `
                <tr class="row-item" oncontextmenu="showContextMenu(event, '${item.name}', 'output')">
                    <td>${item.name}</td>
                    <td>${item.pin}</td>
                    <td><span class="status ${item.value ? 'status-on' : 'status-off'}">${item.value ? 'ON' : 'OFF'}</span></td>
                    <td>
                        <button class="btn" onclick="toggle('${item.name}')">Toggle</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderRegisters(items) {
            const tbody = document.querySelector('#registers-table tbody');
            if (items.length === 0) { tbody.innerHTML = '<tr><td colspan="3">No registers</td></tr>'; return; }
            tbody.innerHTML = items.map(item => `
                <tr class="row-item" oncontextmenu="showContextMenu(event, '${item.name}', 'register')">
                    <td>${item.name}</td>
                    <td>${item.pin}</td>
                    <td><b>${item.value}</b></td>
                </tr>
            `).join('');
        }

        connectSSE();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


def get_io_snapshot(client):
    tags = client.get_tags().values()
    inputs, outputs, registers = [], [], []

    for tag in tags:
        item = {'name': tag.name, 'pin': tag.address, 'value': tag.value if tag.value is not None else 0}
        if tag.address.startswith('X'):
            inputs.append(item)
        elif tag.address.startswith('Y'):
            outputs.append(item)
        else:
            registers.append(item)

    inputs.sort(key=lambda x: x['pin'])
    outputs.sort(key=lambda x: x['pin'])
    registers.sort(key=lambda x: x['pin'])

    return {'inputs': inputs, 'outputs': outputs, 'registers': registers}


@app.route("/api/socket/status")
def api_socket_status():
    data = app.config['data']
    client = data['client']

    def generate():
        last_payload = None
        try:
            while True:
                snapshot = get_io_snapshot(client)
                payload = json.dumps(snapshot, ensure_ascii=False)
                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"
                time.sleep(0.01)
        except GeneratorExit:
            pass

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route('/api/toggle/<name>', methods=['POST'])
def toggle_output(name):
    data = app.config['data']
    client = data['client']
    try:
        tag = client.get(name)
        if not tag.address.startswith('Y'): return jsonify({'error': "Not an output"}), 400
        tag.toggle()
        return jsonify({'success': True, 'new_value': tag.value})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/set/<name>', methods=['POST'])
def set_value(name):
    data = app.config['data']
    client = data['client']
    try:
        req_data = request.get_json()
        if 'value' not in req_data: return jsonify({'error': "Missing 'value'"}), 400
        val = int(req_data['value'])
        tag = client.get(name)
        tag.set(val)
        return jsonify({'success': True, 'new_value': val})
    except ValueError:
        return jsonify({'error': "Invalid value"}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run(data):
    host = data.get('host', '0.0.0.0')
    port = data.get('port', 2003)
    app.config['data'] = data
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)