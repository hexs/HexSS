from flask import Flask, render_template, send_from_directory, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    images_list = os.listdir('images')
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    images_list = [img for img in images_list if any(img.lower().endswith(ext) for ext in valid_extensions)]
    return render_template('index.html', images=images_list)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('images', filename)

@app.route('/get_images')
def get_images():
    images_list = os.listdir('images')
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    images_list = [img for img in images_list if any(img.lower().endswith(ext) for ext in valid_extensions)]
    return jsonify(images_list)

if __name__ == '__main__':
    app.run(debug=True)