# run_server.py
import json
import time
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)


@app.route("/")
def index():
    data = app.config.get("data") or {}
    inputs = data.get("inputs") or []
    outputs = data.get("outputs") or []
    return render_template("index.html", inputs=inputs, outputs=outputs)


@app.route("/api/socket/status")
def api_socket_status():
    """
    SSE endpoint:
    Sends a snapshot of inputs/outputs whenever the payload changes.
    """
    data = app.config.get("data") or {}

    def generate():
        last_payload = None
        try:
            while True:
                snapshot = {
                    "inputs": data.get("inputs") or [],
                    "outputs": data.get("outputs") or [],
                }
                payload = json.dumps(snapshot, ensure_ascii=False)

                # Only send when payload changes to reduce traffic/CPU
                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"

                time.sleep(0.05)
        except GeneratorExit:
            # Client closed the connection
            return

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Avoid buffering on reverse proxies
        },
    )


@app.route("/api/control", methods=["POST"])
def control():
    """
    Accepts output commands in the form:
    {
        "outputs": {
            "Y0": 1,
            "Y1": 0
        }
    }
    Then writes a block of Y0..Yn to the PLC.
    """
    data = app.config.get("data") or {}
    client = data.get("client")

    if client is None:
        return jsonify({"ok": False, "error": "PLC client is not ready"}), 500

    payload = request.get_json(silent=True) or {}
    req_outputs = payload.get("outputs") or {}

    # Current outputs from shared data
    current_list = data.get("outputs") or []
    reg_to_val = {item["register"]: int(item["value"]) for item in current_list}

    # Update with requested values
    for reg, v in req_outputs.items():
        try:
            reg_to_val[reg] = 1 if int(v) else 0
        except Exception:
            reg_to_val[reg] = 0

    # Collect all Y registers
    y_regs = [k for k in reg_to_val.keys() if k.startswith("Y")]
    if not y_regs:
        return jsonify({"ok": False, "error": "No Y register found"}), 400

    max_index = max(int(r[1:]) for r in y_regs)
    values_list = [reg_to_val.get(f"Y{i}", 0) for i in range(max_index + 1)]

    # Write to PLC
    try:
        client.write("Y0", values_list)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    # Sync data['outputs'] to current values
    io_labels = data.get("IO_LABELS") or {}
    new_outputs = []
    for i, v in enumerate(values_list):
        reg = f"Y{i}"
        new_outputs.append(
            {
                "register": reg,
                "label": io_labels.get(reg, reg),
                "value": int(v),
            }
        )

    data["outputs"] = new_outputs

    return jsonify({"ok": True, "outputs": new_outputs})


def run_server(data, host: str = "0.0.0.0", port: int = 5000, debug: bool = True):
    app.config["data"] = data
    app.run(host=host, port=port, debug=debug, use_reloader=False)
