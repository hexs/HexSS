import json
import time
import logging
from functools import wraps
import traceback

from flask import Flask, render_template, request, jsonify, abort, Response
from hexss.network import get_all_ipv4, get_hostname

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)


def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {traceback.format_exc()}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return decorated_function


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/servo', methods=['POST'])
@handle_errors
def servo():
    robot = app.config['robot']
    slave = request.json.get('slave')
    on = request.json.get('on')

    if slave is None:
        abort(400, description="Missing 'slave' parameter")
    if on is None:
        abort(400, description="Missing 'on' parameter")

    robot.servo(slave, on)
    return jsonify({'status': 'success'})


@app.route('/api/alarm_reset', methods=['POST'])
@handle_errors
def alarm_reset():
    robot = app.config['robot']
    slave = request.json.get('slave')

    if slave is None:
        abort(400, description="Missing 'slave' parameter")

    robot.alarm_reset(slave)
    return jsonify({'status': 'success'})


@app.route('/api/pause', methods=['POST'])
def pause():
    robot = app.config['robot']
    slave = request.json.get('slave')
    pause = request.json.get('pause')

    if slave is None:
        abort(400, description="Missing 'slave' parameter")
    if pause is None:
        abort(400, description="Missing 'pause' parameter")

    robot.pause(slave, pause)
    return jsonify({'status': 'success'})


@app.route('/api/home', methods=['POST'])
def home():
    robot = app.config['robot']
    slave = request.json.get('slave')

    if slave is None:
        abort(400, description="Missing 'slave' parameter")

    robot.home(slave)
    return jsonify({'status': 'success'})


@app.route('/api/jog', methods=['POST'])
@handle_errors
def jog():
    robot = app.config['robot']
    slave = request.json.get('slave')
    direction = request.json.get('direction')

    if slave is None:
        abort(400, description="Missing 'slave' parameter")
    if direction is None:
        abort(400, description="Missing 'direction' parameter")

    robot.jog(slave, direction)
    return jsonify({'status': 'success'})


@app.route('/api/move_to', methods=['POST'])
def move_to():
    robot = app.config['robot']
    slave = request.json.get('slave')
    row = request.json.get('row')

    if slave is None:
        abort(400, description="Missing 'slave' parameter")
    if row is None:
        abort(400, description="Missing 'row' parameter")

    robot.move_to(slave, row)
    return jsonify({'status': 'success'})


@app.route('/socket/current_position', methods=['GET', 'POST'])
def current_position_socket():
    robot = app.config['robot']

    def generate():
        result = ''
        while True:
            old_result = result
            result = f"data: {json.dumps({
                '01': robot.get_current_position(1),
                '02': robot.get_current_position(2),
                '03': robot.get_current_position(3),
                '04': robot.get_current_position(4),
            })}\n\n"
            if result != old_result:
                yield result
            time.sleep(0.1)

    return Response(generate(), mimetype='text/event-stream')


@app.errorhandler(400)
def bad_request(error):
    return jsonify({'status': 'error', 'message': error.description}), 400


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


def run(data, robot):
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.config['data'] = data
    app.config['robot'] = robot

    ipv4 = data['config']['ipv4']
    port = data['config']['port']
    if ipv4 == '0.0.0.0':
        for ipv4_ in {'127.0.0.1', *get_all_ipv4(), get_hostname()}:
            logging.info(f"Running on http://{ipv4_}:{port}")
    else:
        logging.info(f"Running on http://{ipv4}:{port}")

    app.run(ipv4, port, debug=True, use_reloader=False)
