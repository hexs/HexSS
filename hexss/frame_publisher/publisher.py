from __future__ import annotations
import io
import os
import platform
import sys
import time
import subprocess
import webbrowser
from pathlib import Path
from typing import Union, Optional
from urllib import request as urlreq, parse as urlparse

import hexss

hexss.check_packages('numpy', 'opencv-python', 'Pillow', auto_install=True)

import numpy as np
import cv2
from PIL import Image as PILImage

SourceType = Union[np.ndarray, PILImage.Image, bytes, bytearray, memoryview]


def _encode_pil_to_jpeg(img: PILImage.Image, quality: int) -> bytes:
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=int(quality), optimize=True, subsampling=0)
    return bio.getvalue()


def _encode_ndarray_to_jpeg(arr: np.ndarray, quality: int) -> bytes:
    if arr is None:
        raise ValueError("ndarray is None")
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
    ok, buf = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("cv2.imencode failed")
    return buf.tobytes()


class FramePublisher:
    def __init__(
            self,
            host: Optional[str] = None,
            port: Optional[int] = None,
            *,
            autostart: bool = True,
            wait_ready: float = 8.0,
            jpeg_quality: int = 80,
            open_browser: bool = False
    ):
        if host is None or port is None:
            from hexss.config import load_config
            cfg = load_config("frame_publisher_server", {
                "ipv4": "0.0.0.0",
                "port": 2004
            })
            host = host or cfg.get("ipv4")
            port = port or cfg.get("port")

        self.host = host
        self.port = int(port)
        self.jpeg_quality = int(max(1, min(100, jpeg_quality)))
        self.base_url = (
            f"http://127.0.0.1:{self.port}"
            if host in ("0.0.0.0", "::", "localhost", "127.0.0.1")
            else f"http://{host}:{self.port}"
        )

        if autostart and not self._is_up():
            self._spawn_server(open_browser=open_browser)
            self._wait_until_up(timeout=wait_ready)

    def show(self, name: str, source: SourceType, *, timeout: float = 1.0) -> bool:
        """
        Encode `source` to JPEG bytes and POST to /push.

        Supports:
          - numpy.ndarray (BGR/GRAY/BGRA or float arrays)
          - PIL.Image.Image (any mode; encoded to JPEG)
          - bytes/bytearray/memoryview (assumed already JPEG)

        Returns True on success, False otherwise.
        """
        try:
            if isinstance(source, np.ndarray):
                data = _encode_ndarray_to_jpeg(source, self.jpeg_quality)
            elif isinstance(source, PILImage.Image):
                data = _encode_pil_to_jpeg(source, self.jpeg_quality)
            elif isinstance(source, (bytes, bytearray, memoryview)):
                data = bytes(source)
            else:
                return False

            url = f"{self.base_url}/push?name={urlparse.quote(name)}"
            req = urlreq.Request(url, data=data, headers={"Content-Type": "image/jpeg"}, method="POST")
            with urlreq.urlopen(req, timeout=timeout) as r:
                _ = r.read(1)
            return True

        except Exception as e:
            print(e)
            return False

    def publish(self, name: str, source: SourceType, *, timeout: float = 1.0) -> bool:
        return self.show(name, source, timeout=timeout)

    def _is_up(self) -> bool:
        try:
            with urlreq.urlopen(self.base_url + "/api/health", timeout=0.5):
                return True
        except Exception:
            return False

    def _spawn_server(self, open_browser: bool = False):
        exe = sys.executable
        script = str(Path(__file__).with_name("server.py"))
        if not os.path.exists(script):
            return

        cmd = [exe, script, str(self.port)]
        os_name = platform.system()

        if os_name == 'Windows':
            flags = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(cmd, creationflags=flags)

        elif os_name == 'Darwin':
            cmd_str = " ".join(f"'{c}'" for c in cmd)
            subprocess.Popen([
                "osascript", "-e",
                f'tell application "Terminal" to do script "{cmd_str}"'
            ])

        elif os_name == 'Linux':
            cmd_str = " ".join(cmd)
            terminals = [
                ["gnome-terminal", "--"],  # Ubuntu/Gnome
                ["x-terminal-emulator", "-e"],  # Debian standard
                ["xfce4-terminal", "-e"],  # XFCE
                ["konsole", "-e"],  # KDE
                ["xterm", "-e"]  # Basic X11
            ]
            started = False
            for term in terminals:
                try:
                    full_cmd = term + [cmd_str]
                    if "gnome-terminal" in term[0]:
                        full_cmd = term + cmd
                    subprocess.Popen(full_cmd)
                    started = True
                    break
                except FileNotFoundError:
                    continue
            if not started:
                print("No compatible terminal found, running in background...")
                subprocess.Popen(cmd)

        else:
            subprocess.Popen(cmd)

        if open_browser:
            time.sleep(1)
            try:
                webbrowser.open(self.base_url)
            except Exception:
                print('Error opening browser')
                pass

    def _wait_until_up(self, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._is_up():
                return True
            time.sleep(0.2)
        return False
