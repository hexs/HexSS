import json
import time
from flask import Flask, render_template, request, jsonify, abort, Response
from hexss.constants import GREEN, RED, ENDC
from hexss.network import get_all_ipv4, get_hostname
from hexss.serial import get_comport
from hexss.control_robot.robot import Robot
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
robot = None


def initialize_robot():
    global robot
    if robot is None:
        try:
            comport = get_comport('ATEN USB to Serial', 'USB-Serial Controller')
            robot = Robot(comport, baudrate=38400)
            logger.info(f"{GREEN}Robot initialized successfully{ENDC}")
        except Exception as e:
            logger.error(f"Failed to initialize robot: {e}")
            return False

    def run_robot():
        while True:
            try:
                robot.run()
            except Exception as e:
                logger.error(f"Error in robot.run(): {e}")

    robot_thread = threading.Thread(target=run_robot, daemon=True)
    robot_thread.start()
    return True


if not initialize_robot():
    logger.error("Failed to initialize robot. Exiting.")
    exit(1)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/servo', methods=['POST'])
def servo():
    try:
        on = request.json.get('on')
        if on is None:
            abort(400, description="Missing 'on' parameter")
        robot.servo(on)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in servo: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/alarm_reset', methods=['POST'])
def alarm_reset():
    try:
        robot.alarm_reset()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in alarm_reset: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/pause', methods=['POST'])
def pause():
    try:
        pause = request.json.get('pause')
        if pause is None:
            abort(400, description="Missing 'pause' parameter")
        robot.pause(pause)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in pause: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/home', methods=['POST'])
def home():
    try:
        robot.home()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in home: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/jog', methods=['POST'])
def jog():
    try:
        data = request.json
        required_fields = ['slave', 'positive_side', 'move']
        if not all(field in data for field in required_fields):
            abort(400, description="Missing required fields")
        robot.jog(data['slave'], data['positive_side'], data['move'])
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in jog: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/current_position', methods=['GET', 'POST'])
def current_position():
    try:
        robot.current_position()
        return jsonify({'status': 'success', 'data': robot.current_position_vel})
    except Exception as e:
        logger.error(f"Error in current_position: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/move_to', methods=['POST'])
def move_to():
    try:
        row = request.json.get('row')
        if row is None:
            abort(400, description="Missing 'row' parameter")
        robot.move_to(row)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in move_to: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/set_to', methods=['POST'])
def set_to():
    try:
        data = request.json
        required_fields = ['slave', 'row', 'position', 'speed', 'acc', 'dec']
        if not all(field in data for field in required_fields):
            abort(400, description="Missing required fields")
        robot.set_to(data['slave'], data['row'], data['position'], data['speed'], data['acc'], data['dec'])
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in set_to: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# new function
@app.route('/socket/current_position', methods=['GET', 'POST'])
def current_position_socket():
    def generate():
        result = ''
        while True:
            robot.current_position()
            old_result = result
            result = f"data: {json.dumps(robot.current_position_vel)}\n\n"
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


def run(data):
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.config['data'] = data
    ipv4 = data['config']['ipv4']
    port = data['config']['port']
    if ipv4 == '0.0.0.0':
        for ipv4_ in {'127.0.0.1', *get_all_ipv4(), get_hostname()}:
            logging.info(f"Running on http://{ipv4_}:{port}")
    else:
        logging.info(f"Running on http://{ipv4}:{port}")

    app.run(ipv4, port, debug=True, use_reloader=False)
