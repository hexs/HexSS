from flask import Flask, render_template_string, Response, request, redirect, url_for, jsonify
import cv2
from hexss.image.capture import WindowCapture

app = Flask(__name__)

captures = {}  # dict of id -> {'title': ..., 'cap': WindowCapture}
next_id = 1


def add_capture(title_name, hwnd=None):
    global next_id
    cap = WindowCapture(hwnd=hwnd) if hwnd else WindowCapture(title_name=title_name)
    captures[next_id] = {'title': title_name, 'cap': cap}
    next_id += 1


# Initialize with first window
initial_windows = WindowCapture.list_windows()
if initial_windows:
    add_capture(initial_windows[0][1], hwnd=initial_windows[0][0])

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>WindowCapture Streams</title></head>
<body>
  <h1>Capture Streams</h1>
  {% for cid, info in captures.items() %}
    <div id="cap-{{ cid }}" style="border:1px solid #ccc;padding:10px;margin-bottom:10px;">
      <h2>Capture {{ cid }}: {{ info.title }}</h2>
      <img src="{{ url_for('video_feed', cap_id=cid) }}" width="600" alt="Video Feed {{ cid }}">
      <p id="stats-{{ cid }}">Loading stats...</p>
      <form method="post" action="{{ url_for('delete_capture', cap_id=cid) }}" style="display:inline-block;margin-left:10px;">
        <button type="submit">Delete Capture</button>
      </form>
    </div>
  {% endfor %}
  <h2>Add New Capture</h2>
  <form method="post" action="{{ url_for('add') }}">
    <label for="new_window">Select Window:</label>
    <select name="new_window" id="new_window">
      {% for hwnd, title in windows %}
        <option value="{{ title }}" data-hwnd="{{ hwnd }}">{{ title }}</option>
      {% endfor %}
    </select>
    <button type="submit">Add Capture</button>
  </form>

  <script>
    const capIds = [{% for cid in captures.keys() %}{{ cid }}{% if not loop.last %}, {% endif %}{% endfor %}];
    function updateStats(cid) {
      fetch(`/api/stats/${cid}`)
        .then(res => res.json())
        .then(data => {
          document.getElementById(`stats-${cid}`).textContent =
            `HWND: ${data.hwnd} | Resolution: ${data.width}x${data.height} | FPS: ${data.fps.toFixed(2)}`;
        }).catch(console.error);
    }
    setInterval(() => {
      capIds.forEach(updateStats);
    }, 1000);
    // initial load
    capIds.forEach(updateStats);
  </script>
</body>
</html>
"""


@app.route('/', methods=['GET'])
def index():
    windows = WindowCapture.list_windows()
    return render_template_string(TEMPLATE, captures=captures, windows=windows)


@app.route('/api/stats/<int:cap_id>')
def stats(cap_id):
    entry = captures.get(cap_id)
    if not entry:
        return jsonify({'error': 'not found'}), 404
    cap = entry['cap']
    # capture a frame to read stats (without sending image)
    im = cap.capture()
    width, height = im.size
    return jsonify({'hwnd': cap.hwnd, 'width': width, 'height': height, 'fps': cap.fps})


@app.route('/add', methods=['POST'])
def add():
    title = request.form.get('new_window')
    selected = request.form.get('new_window')
    hwnd = request.form.get('new_window').startswith('0x') and int(request.form.get('new_window'), 16) or None
    if title:
        add_capture(title, hwnd=hwnd)
    return redirect(url_for('index'))


@app.route('/delete/<int:cap_id>', methods=['POST'])
def delete_capture(cap_id):
    entry = captures.pop(cap_id, None)
    if entry:
        try:
            entry['cap'].close()
        except:
            pass
    return redirect(url_for('index'))


@app.route('/video_feed/<int:cap_id>')
def video_feed(cap_id):
    def generate_frames(cap_obj):
        while True:
            im = cap_obj.capture()
            frame = im.numpy()
            ret, buf = cv2.imencode('.jpg', frame)
            if not ret: continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

    entry = captures.get(cap_id)
    if not entry:
        return "Capture not found", 404
    return Response(generate_frames(entry['cap']), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
