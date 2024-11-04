import time
import json
from flask import Flask, render_template, Response, jsonify

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/shutdown', methods=['POST'])
def shutdown():
    data = app.config['data']
    data['play'] = False
    return 'Server shutting down...'


@app.route('/status')
def status():
    def generate():
        while app.config['data']['play']:
            status = app.config['multithread'].get_status()
            yield f"data: {json.dumps(status)}\n\n"
            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/status')
def api_status():
    status = app.config['multithread'].get_status()
    return jsonify(status)


def run_server(data, multithread):
    app.config['data'] = data
    app.config['multithread'] = multithread
    app.run(debug=False, use_reloader=False)
