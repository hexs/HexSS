import json
import traceback
from functools import wraps

import hexss

hexss.check_packages('pandas', 'Flask', auto_install=True)

from flask import Flask, render_template, request, jsonify, abort, Response
from werkzeug.exceptions import HTTPException
from hexss import get_hostname
from hexss.network import get_all_ipv4
from .robot import Robot

app = Flask(__name__, static_folder='static', template_folder='templates')


@app.errorhandler(HTTPException)
def handle_http_error(e):
    response = jsonify({'status': 'error', 'message': e.description})
    return response, e.code


def handle_errors(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            # print(f"Error in {fn.__name__}: {traceback.format_exc()}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return wrapper


def validate_params(*required_params):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                abort(400, description='JSON body required')
            payload = request.get_json()
            missing = [p for p in required_params if p not in payload]
            if missing:
                abort(400, description=f"Missing parameters: {', '.join(missing)}")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


@app.route('/api/alarm_reset', methods=['POST'])
@validate_params('slave')
@handle_errors
def robot_alarm_reset():
    robot: Robot = app.config['robot']
    slave = request.json.get('slave')
    robot.slaves[slave].alarm_reset()
    return jsonify(status='success')


@app.route('/api/servo', methods=['POST'])
@validate_params('slave', 'on')
@handle_errors
def robot_servo():
    robot: Robot = app.config['robot']
    slave = request.json.get('slave')
    on = request.json.get('on')
    robot.slaves[slave].servo(bool(on))
    return jsonify(status='success')


@app.route('/api/home', methods=['POST'])
@validate_params('slave')
@handle_errors
def robot_home():
    robot: Robot = app.config['robot']
    slave = request.json.get('slave')
    robot.slaves[slave].home()
    return jsonify(status='success')


@app.route('/api/pause', methods=['POST'])
@validate_params('slave', 'pause')
@handle_errors
def robot_pause():
    robot: Robot = app.config['robot']
    slave = request.json.get('slave')
    pause = request.json.get('pause')
    robot.slaves[slave].pause(bool(pause))
    return jsonify(status='success')


@app.route('/api/move', methods=['POST'])
@validate_params('slave', 'value')
@handle_errors
def robot_move():
    robot: Robot = app.config['robot']
    slave = request.json.get('slave')
    value = request.json.get('value')
    robot.slaves[slave].move(value)
    return jsonify(status='success')


@app.route('/api/socket/register', methods=['GET'])
def read_register_socket():
    robot: Robot = app.config['robot']
    slave = request.args.get('slave', type=int)

    def generate():
        last = None
        while True:
            robot.update_registers(slave, show_results=False)
            json_data = robot.to_json(slave).replace('\n', '').replace('  ', '')
            if json_data != last:
                yield f"data: {json_data}\n\n"
                last = json_data
            else:
                yield ": keep-alive\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/socket/current_position', methods=['GET'])
def current_position_socket():
    robot = app.config['robot']
    num_slaves = app.config.get('num_slaves', 1)

    def generate():
        last_data = ''
        while True:
            out = {}
            for slave_id in range(num_slaves):
                slave = robot.slaves[slave_id]
                out[slave_id] = {
                    'position': slave.get_position(),
                    'emergency_status': slave.is_emergency(),
                    'servo_on': slave.is_servo_on(),
                    'pause_status': slave.is_paused()
                }
            data = f"data: {json.dumps(out)}\n\n"
            if data != last_data:
                yield data
                last_data = data
            else:
                yield ": keep-alive\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/', methods=['GET'])
def index():
    return render_template(
        'index.html',
        num_slaves=app.config.get('num_slaves', 1),
        min_max_position=app.config.get('min_max_position', {0: (0, 4000)}),
    )


@app.route('/register')
def register():
    return render_template('register.html', num_slaves=app.config.get('num_slaves', 1))


def run(data, robot):
    app.config['data'] = data
    app.config['robot'] = robot
    app.config['num_slaves'] = 4
    app.config['min_max_position'] = {
        0: (0, 40000),
        1: (0, 20000),
        2: (0, 15000),
        3: (-5000, 5000)
    }

    ipv4 = data['config']['ipv4']
    port = data['config']['port']
    if ipv4 == '0.0.0.0':
        for host in {'127.0.0.1', *get_all_ipv4(), get_hostname()}:
            print(f"Running on http://{host}:{port}")
    else:
        print(f"Running on http://{ipv4}:{port}")

    app.run(ipv4, port, debug=True, use_reloader=False)
