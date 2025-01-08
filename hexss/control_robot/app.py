import json
import time
import logging
from functools import wraps
import traceback

import pandas as pd
from flask import Flask, render_template, request, jsonify, abort, Response
from hexss.network import get_all_ipv4, get_hostname
from pretty_dataframe import column_mapping, read_p_df, write_p_df

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


def validate_params(*required_params):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            for param in required_params:
                if request.json.get(param) is None:
                    abort(400, description=f"Required Params: {required_params}\nMissing '{param}' parameter")
            return f(*args, **kwargs)

        return wrapper

    return decorator


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/servo', methods=['POST'])
@validate_params('slave', 'on')
@handle_errors
def servo():
    robot = app.config['robot']
    robot.servo(
        request.json.get('slave'),
        request.json.get('on')
    )
    return jsonify({'status': 'success'})


@app.route('/api/alarm_reset', methods=['POST'])
@validate_params('slave')
@handle_errors
def alarm_reset():
    robot = app.config['robot']
    robot.alarm_reset(
        request.json.get('slave')
    )
    return jsonify({'status': 'success'})


@app.route('/api/pause', methods=['POST'])
@validate_params('slave', 'pause')
@handle_errors
def pause():
    robot = app.config['robot']
    robot.pause(
        request.json.get('slave'),
        request.json.get('pause')
    )
    return jsonify({'status': 'success'})


@app.route('/api/home', methods=['POST'])
@validate_params('slave')
@handle_errors
def home():
    robot = app.config['robot']
    robot.home(
        request.json.get('slave')
    )
    return jsonify({'status': 'success'})


@app.route('/api/jog', methods=['POST'])
@validate_params('slave', 'direction')
@handle_errors
def jog():
    robot = app.config['robot']
    robot.jog(
        request.json.get('slave'),
        request.json.get('direction')
    )
    return jsonify({'status': 'success'})


@app.route('/api/move_to', methods=['POST'])
@validate_params('slave', 'row')
@handle_errors
def move_to():
    robot = app.config['robot']
    robot.move_to(
        request.json.get('slave'),
        request.json.get('row')
    )
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


@app.route("/table")
def show_table():
    return render_template("table_editor.html")


@app.route("/load", methods=["GET"])
def get_data():
    robot = app.config['robot']
    try:
        slave = request.args.get('slave', type=int)
        return jsonify(read_p_df(robot, slave))
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/save", methods=["POST"])
def save_changes():
    robot = app.config['robot']
    try:
        slave = request.args.get('slave', type=int)
        data = request.json
        if not data:
            return jsonify({"error": "No data received"}), 400
        p_df = pd.DataFrame(data)
        p_df.rename(columns=dict(zip(range(len(column_mapping)), column_mapping.keys())), inplace=True)
        write_p_df(robot, slave, p_df)
        return jsonify({"success": True}), 200

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


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
