from __future__ import annotations
import io
import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path
from typing import Union
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
            host: str = "0.0.0.0",
            port: int = 2004,
            *,
            autostart: bool = True,
            wait_ready: float = 8.0,
            jpeg_quality: int = 80,
            open_browser: bool = False,
            unset_proxy: bool | None = None,
    ):
        if unset_proxy: from hexss.env import unset_proxy; unset_proxy()
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

        cmd = [exe, script, "--host", self.host, "--port", str(self.port)]
        kwargs = dict(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(Path(script).parent),
            close_fds=True,
        )

        if os.name == "nt":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            subprocess.Popen(cmd, creationflags=flags, **kwargs)
        else:
            subprocess.Popen(cmd, start_new_session=True, **kwargs)

        if open_browser:
            try:
                webbrowser.open(self.base_url)
            except Exception:
                pass

    def _wait_until_up(self, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._is_up():
                return True
            time.sleep(0.2)
        return False
