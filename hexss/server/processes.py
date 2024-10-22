import subprocess
import time
import os
from threading import Thread, Event
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_socketio import SocketIO
from hexss import random_str


def count_to_ten(stop_event, *args):
    key, script_path = args
    for i in range(10):
        if stop_event.is_set():
            break
        print(i)
        time.sleep(1)


def run_exe(stop_event, *args):
    key, script_path = args
    try:
        process = subprocess.Popen([f'{script_path}'])
        while not stop_event.is_set():
            if process.poll() is not None:
                break
            time.sleep(0.1)
        if process.poll() is None:
            process.terminate()
    except FileNotFoundError:
        print(f"Error: {script_path} not found.")
    except subprocess.SubprocessError as e:
        print(f"Subprocess error: {e}")


def run_python(stop_event, *args):
    key, script_path = args
    try:
        process = subprocess.Popen(['python', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, bufsize=1, universal_newlines=True)
        while not stop_event.is_set():
            if process.poll() is not None:
                break
            line = process.stdout.readline()
            if line:
                print(line.strip())
                socketio.emit('output', {'data': line.strip(), 'key': key})
            time.sleep(0.1)
        if process.poll() is None:
            process.terminate()
        return_code = process.wait()
        if return_code != 0:
            print(f"Python script exited with error code {return_code}")
            error_output = process.stderr.read()
            print(error_output)
            socketio.emit('output', {'data': error_output, 'key': key})
    except Exception as e:
        print(f"Error running Python script: {e}")
        socketio.emit('output', {'data': str(e), 'key': key})


processes = {}
stop_events = {}


def show_running_processes():
    return [{'key': k, 'name': v['name']} for k, v in processes.items() if v['status']]


def start_process(target, name, key, script_path):
    stop_event = Event()
    processes[key] = {'status': True, 'name': name}
    stop_events[key] = stop_event
    args = (key, script_path)
    thread = Thread(target=target, args=(stop_event, *args))
    thread.start()

    def check_process_status():
        while not stop_event.is_set():
            if not thread.is_alive():
                processes[key]['status'] = False
                del stop_events[key]
                break
            time.sleep(1)

    if target != run_python:  # if run_python don't use auto close
        Thread(target=check_process_status).start()  # auto close if End of work


def close_process(key):
    if key in stop_events:
        stop_events[key].set()
        processes[key]['status'] = False
        del stop_events[key]
        return True
    return False


def close_all_processes():
    for key in list(stop_events.keys()):
        close_process(key)


app = Flask(__name__)
socketio = SocketIO(app)


@app.route('/')
def root():
    return redirect(url_for('process'))


@app.route('/process')
def process():
    return render_template('process.html')


@app.route('/show_running_processes')
def show_processes():
    active_processes = show_running_processes()
    return jsonify({"running_processes": active_processes})


@app.route('/exe/<program_name>')
def start_exe(program_name):
    key = random_str()
    start_process(run_exe, 'run_subprocess', program_name, key, None)
    return jsonify({"message": f"Subprocess started with key: {key}", "key": key})


@app.route('/10')
def start_count():
    key = random_str()
    start_process(count_to_ten, 'count_to_ten', key, None)
    return jsonify({"message": f"Count to ten started with key: {key}", "key": key})


@app.route('/python/<path:path>')
def start_python(path):
    script_path = os.path.abspath(path)
    if not os.path.exists(script_path):
        return jsonify({"error": "Python script not found"}), 404
    key = random_str()
    start_process(run_python, f'run_python: {os.path.basename(script_path)}', key, script_path)
    return jsonify({"message": f"Python script started with key: {key}", "key": key})


@app.route('/close/<key>')
def close_single_process(key):
    success = close_process(key)
    return jsonify({"success": success,
                    "message": f"Process with key {key} closed" if success else f"Process with key {key} not found"})


@app.route('/exit')
def exit_app():
    close_all_processes()
    return jsonify({"message": "All processes closed."})


if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
