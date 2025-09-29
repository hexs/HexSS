from __future__ import annotations
import os, sys, time, subprocess
from pathlib import Path
from urllib import request as urlreq, parse as urlparse

import numpy as np
import cv2
import webbrowser


class FramePublisher:
    def __init__(self,
                 host: str = "0.0.0.0",
                 port: int = 2004,
                 autostart: bool = True,
                 wait_ready: float = 8.0,
                 jpeg_quality: int = 80):
        self.host = host
        self.port = int(port)
        self.jpeg_quality = int(max(1, min(100, jpeg_quality)))

        self.base_url = f"http://127.0.0.1:{self.port}" if host in ("0.0.0.0", "::", "localhost", "127.0.0.1") \
            else f"http://{host}:{self.port}"

        if autostart and not self._is_up():
            self._spawn_server()
            self._wait_until_up(timeout=wait_ready)

    # -------- public API --------
    def imshow(self, name: str, img_bgr: np.ndarray):
        if img_bgr is None:
            return
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        if not ok:
            return
        data = buf.tobytes()
        try:
            url = self.base_url + "/push?name=" + urlparse.quote(name)
            req = urlreq.Request(url, data=data, headers={"Content-Type": "image/jpeg"}, method="POST")
            with urlreq.urlopen(req, timeout=1.0) as r:
                r.read(1)
        except Exception:
            pass

    # -------- internals --------
    def _is_up(self) -> bool:
        try:
            with urlreq.urlopen(self.base_url + "/api/health", timeout=0.5):
                return True
        except Exception:
            return False

    def _spawn_server(self):
        exe = sys.executable
        script = str(Path(__file__).with_name("server.py"))
        if not os.path.exists(script):
            return
        cmd = [exe, script, "--host", self.host, "--port", str(self.port)]
        kwargs = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                      cwd=str(Path(script).parent), close_fds=True)
        if os.name == "nt":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            subprocess.Popen(cmd, creationflags=flags, **kwargs)
        else:
            subprocess.Popen(cmd, start_new_session=True, **kwargs)

        webbrowser.open(self.base_url)

    def _wait_until_up(self, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._is_up():
                return True
            time.sleep(0.2)
        return False
