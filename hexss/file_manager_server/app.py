import ipaddress
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional

import hexss
from hexss import Config
from hexss.constants import *
from hexss.path import iterdir, list_drives, last_component, get_hexss_dir

hexss.check_packages('Flask', auto_install=True, venv_only=False)

from hexss.network import kill_process_on_port
from flask import Flask, request, send_file, redirect, url_for, jsonify, abort

app = Flask(__name__)

PAGE = Path(app.root_path) / 'templates' / 'file_manager.html'
MAX_EDIT_BYTES = 20 * 1024 * 1024

ACTIVE_MIMETYPES = {
    'text/html', 'application/xhtml+xml', 'image/svg+xml', 'text/xml', 'application/xml',
}

ALLOWED_NETS = []


def to_abs(p) -> str:
    """
    แปลง path ที่ client ส่งมา (เช่น 'C:/Users/x', 'D:', '//it/share', '/home/x')
    ให้เป็น absolute path ที่ใช้งานได้จริง
    ถ้า path ว่างหรือไม่ใช่ absolute จะ raise ValueError (-> 400) ไม่ปล่อยให้ตกไปเป็น cwd
    """
    p = (p or '').strip().replace('\\', '/')
    if not p:
        raise ValueError('path is required')
    if re.fullmatch(r'[A-Za-z]:', p):  # "D:" -> "D:/"
        p += '/'
    p = os.path.normpath(p)
    if not (os.path.isabs(p) or p.startswith(('\\\\', '//'))):
        raise ValueError('absolute path required')
    return p


def safe_join(base: str, rel: str) -> str:
    """ต่อ rel เข้ากับ base และกันไม่ให้หลุดออกนอก base (../, D:/x, absolute path)"""
    full = os.path.normpath(os.path.join(base, rel.replace('\\', '/').lstrip('/')))
    b = os.path.normcase(os.path.normpath(base))
    try:
        inside = os.path.commonpath([os.path.normcase(full), b]) == b
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f'invalid path: {rel}')
    return full


def is_root(p: str) -> bool:
    """True ถ้าเป็น root ของไดร์ฟ / UNC share / '/'"""
    return os.path.splitdrive(p)[1].strip('\\/') == ''


def error(msg, code=400, **extra):
    return jsonify(success=False, error=msg, **extra), code


def serve_file(p, **kwargs):
    resp = send_file(p, **kwargs)
    if (resp.mimetype or '') in ACTIVE_MIMETYPES:
        resp.headers['Content-Security-Policy'] = 'sandbox'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@app.before_request
def guard():
    # 1) จำกัด IP (ถ้าตั้ง allowed_networks)
    if ALLOWED_NETS:
        try:
            ip = ipaddress.ip_address(request.remote_addr)
        except ValueError:
            abort(403)
        if not any(ip in net for net in ALLOWED_NETS):
            return error('Forbidden: your IP is not allowed', 403)

    # 2) กัน CSRF: เว็บอื่นยิง POST ข้าม origin มาไม่ได้ เพราะตั้ง header นี้ไม่ได้
    #    (jQuery ใส่ให้เองกับ request ที่ยิงมาที่ origin เดียวกัน)
    if request.method == 'POST' and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return error('Forbidden: missing X-Requested-With header', 403)


@app.errorhandler(ValueError)
def handle_value_error(e):
    return error(str(e), 400)


@app.route('/')
def root():
    return send_file(PAGE)


@app.route('/file')
def raw_file():
    p = to_abs(request.args.get('p', ''))
    if not os.path.isfile(p):
        abort(404, description="File does not exist")
    return serve_file(p)


@app.route('/path/')
@app.route('/path/<path:subpath>')
def path(subpath=''):
    if subpath == '':
        return redirect(url_for('root'))
    if os.name != 'nt' and not subpath.startswith('/'):
        subpath = '/' + subpath
    current = to_abs(subpath)
    if not os.path.exists(current):
        abort(404, description="Path does not exist")
    if os.path.isfile(current):
        return serve_file(current)
    return redirect(url_for('root', p=Path(current).as_posix()))


# ---------------------------------------------------------------- APIs
@app.route('/api/get_list_dir')
def listdir():
    try:
        path_ = Path(to_abs(request.args.get('path', default='', type=str)))
        result = {'path': str(path_), 'folder': [], 'file': []}
        for name in os.listdir(path_):
            (result['folder'] if (path_ / name).is_dir() else result['file']).append(name)
        return jsonify({'success': True, 'listdir': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/iterdir')
def api_path():
    """
    /api/iterdir?p=          # รายชื่อไดร์ฟทั้งหมด (บน Linux/Mac จะเป็น '/')
    /api/iterdir?p=//it      # UNC host root
    /api/iterdir?p=//it/s    # UNC share root
    /api/iterdir?p=C:/       # Local drive
    """
    p = request.args.get('p', default='', type=str).strip()
    response = {'success': True, 'path': p, 'children': []}

    if p == '':
        if os.name != 'nt':
            p = '/'
        else:
            response['children'] = [
                {
                    'path': Path(entry['path']).as_posix(),
                    'name': f"{last_component(Path(entry['path']))} <{entry['type']}>",
                    'type': 'dir',
                    'size': None,
                } for entry in list_drives()
            ]
            return jsonify(response)

    try:
        children = []
        for child in iterdir(Path(to_abs(p))):
            try:
                st = child.stat()
                is_dir = stat.S_ISDIR(st.st_mode)
                size = None if is_dir else st.st_size
            except OSError:
                is_dir, size = True, None
            children.append({
                'path': child.as_posix(),
                'name': last_component(child),
                'type': 'dir' if is_dir else 'file',
                'size': size,
            })
        response['path'] = p
        response['children'] = children
    except Exception as e:
        response['success'] = False
        response['error'] = str(e)

    return jsonify(response)


@app.route('/create_folder', methods=['POST'])
def create_folder():
    folder_path = to_abs(request.form['path'])
    try:
        os.makedirs(folder_path, exist_ok=True)
        return jsonify(success=True)
    except Exception as e:
        return error(str(e), 500)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return error("No files provided")

    files = request.files.getlist('file')
    paths = request.form.getlist('paths')
    base = to_abs(request.form.get('current_path', ''))
    overwrite = request.form.get('overwrite') == '1'

    try:
        targets = []
        for i, file in enumerate(files):
            if file.filename == '':
                continue
            rel_path = paths[i] if i < len(paths) and paths[i] else file.filename
            targets.append((file, safe_join(base, rel_path)))

        exists = [os.path.relpath(t, base).replace('\\', '/') for _, t in targets if os.path.exists(t)]
        if exists and not overwrite:
            return error('Some files already exist', 409, exists=exists[:20], total=len(exists))

        for file, full_path in targets:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
        return jsonify(success=True)
    except ValueError as e:
        return error(str(e), 400)
    except Exception as e:
        return error(str(e), 500)


@app.route('/delete', methods=['POST'])
def delete_item():
    item_path = to_abs(request.form['path'])
    if is_root(item_path):
        return error('Refusing to delete a drive root', 403)
    try:
        if os.path.isfile(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
        else:
            return error('Item not found', 404)
        return jsonify(success=True)
    except Exception as e:
        return error(str(e), 500)


@app.route('/rename', methods=['POST'])
def rename_item():
    old_path = to_abs(request.form['old_path'])
    new_path = to_abs(request.form['new_path'])
    if is_root(old_path):
        return error('Refusing to rename a drive root', 403)
    if not os.path.exists(old_path):
        return error('Item not found', 404)
    if os.path.exists(new_path) and not os.path.samefile(old_path, new_path):
        return error('A file or folder with that name already exists', 409)
    try:
        os.rename(old_path, new_path)
        return jsonify(success=True)
    except Exception as e:
        return error(str(e), 500)


@app.route('/download', methods=['GET'])
def download_item():
    item_path = to_abs(request.args.get('path'))

    if os.path.isfile(item_path):
        return serve_file(item_path, as_attachment=True)

    if os.path.isdir(item_path):
        tmp = tempfile.TemporaryFile()
        skipped = []
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root_, dirs, files in os.walk(item_path,
                                              onerror=lambda e: skipped.append(f'{e.filename}: {e.strerror}')):
                rel_root = os.path.relpath(root_, item_path)
                if not dirs and not files and rel_root != '.':
                    zf.writestr(rel_root.replace(os.sep, '/') + '/', '')  # เก็บโฟลเดอร์ว่างด้วย
                for file in files:
                    file_path = os.path.join(root_, file)
                    try:
                        zf.write(file_path, os.path.relpath(file_path, item_path))
                    except OSError as e:
                        skipped.append(f'{file_path}: {e.strerror or e}')
            if skipped:
                zf.writestr('_skipped_files.txt', '\n'.join(skipped))
        tmp.seek(0)

        name = os.path.basename(item_path.rstrip('\\/'))
        name = re.sub(r'[\\/:*?"<>|]', '_', name) or 'archive'
        return send_file(tmp, mimetype='application/zip', as_attachment=True, download_name=name + '.zip')

    return error('Item not found', 404)


@app.route('/edit', methods=['GET', 'POST'])
def edit_file():
    file_path = to_abs(request.args.get('path'))

    if request.method == 'POST':
        content = request.form.get('content', '')
        # mode=new: ไฟล์ใหม่ / Save As -> ห้ามทับไฟล์เดิมเงียบ ๆ (ต้องส่ง overwrite=1)
        if (request.form.get('mode') == 'new'
                and os.path.exists(file_path)
                and request.form.get('overwrite') != '1'):
            return error('File already exists', 409)
        if os.path.isdir(file_path):
            return error('Target is a directory')
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return jsonify(success=True)
        except Exception as e:
            return error(str(e), 500)

    # GET
    if not os.path.isfile(file_path):
        return jsonify(success=True, content='')
    try:
        if os.path.getsize(file_path) > MAX_EDIT_BYTES:
            return error(f'File is too large to edit here (limit {MAX_EDIT_BYTES // 1024 // 1024} MB)', 413)
        with open(file_path, 'r', encoding='utf-8') as f:
            return jsonify(success=True, content=f.read())
    except UnicodeDecodeError:
        return error('Not a UTF-8 text file', 415)
    except Exception as e:
        return error(str(e), 500)


@app.route('/extract_file', methods=['POST'])
def extract_file():
    zip_path = to_abs(request.form['path'])
    folder_name = (request.form.get('folder_name') or 'extracted_files').strip()
    overwrite = request.form.get('overwrite') == '1'

    if not zipfile.is_zipfile(zip_path):
        return error('Not a valid zip file')
    extract_path = safe_join(os.path.dirname(zip_path), folder_name)

    if os.path.isdir(extract_path) and os.listdir(extract_path) and not overwrite:
        return error('Folder already exists and is not empty', 409)

    try:
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        return jsonify(success=True)
    except Exception as e:
        return error(str(e), 500)


@app.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    threading.Timer(0.3, lambda: os._exit(0)).start()
    return jsonify(success=True)


def run(host: Optional[str] = None, port: Optional[int] = None, background=False):
    global ALLOWED_NETS

    c = Config(get_hexss_dir() / 'config/file_manager_server.py')
    c.host = c.host or '0.0.0.0'
    c.port = c.port or 2001
    if c.kill_port_process is None:
        c.kill_port_process = True  # True = ฆ่า process ที่ใช้พอร์ตนี้อยู่ก่อนสตาร์ต
    c.allowed_networks = c.allowed_networks or []  # เช่น ["127.0.0.1/32", "192.168.1.0/24"]; ว่าง = ทุก IP

    host = host or c.host
    port = port or c.port

    txt = ''
    if host != '0.0.0.0':
        txt += f'🌐 {CYAN}File manager server started at: http://{host}:{port}{END}\n'
    else:
        txt += f'🌐 {CYAN}File manager server started at:{END}\n'
        for _host in hexss.network.get_local_ipv4_hosts():
            txt += f'http://{_host}:{port}\n'

    if background:
        log_dir = Path(get_hexss_dir()) / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'file_manager_server.log'

        cmd = [sys.executable, '-u', str(Path(__file__).resolve()), '--host', host, '--port', str(port)]
        kwargs = {}
        if platform.system() == 'Windows':
            # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
            kwargs['creationflags'] = 0x08000000 | 0x00000200
        else:
            kwargs['start_new_session'] = True

        with open(log_path, 'ab') as log:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **kwargs)

        time.sleep(1.0)
        if proc.poll() is not None:
            print(f'❌ File manager server exited immediately (code {proc.returncode}). See log: {log_path}')
            return
        print(end=txt)
        return

    ALLOWED_NETS = [ipaddress.ip_network(n, strict=False) for n in c.allowed_networks]

    if c.kill_port_process:
        kill_process_on_port(port, host)

    print(end=txt)

    if not ALLOWED_NETS and host not in ('127.0.0.1', 'localhost'):
        print("WARNING: no authentication. Anyone who can reach this port can read/write/delete every file. "
              "Set 'allowed_networks' in the config to restrict access.")

    app.run(host, port, debug=False, use_reloader=False)


if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(description='File manager server')
    ap.add_argument('--host')
    ap.add_argument('--port', type=int)
    ap.add_argument('--background', action='store_true')
    args = ap.parse_args()
    run(host=args.host, port=args.port, background=args.background)
