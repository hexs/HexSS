from __future__ import annotations
import argparse
import asyncio
import json
from dataclasses import dataclass
from time import time
import threading
from typing import Dict, Optional, Set

import numpy as np
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import uvicorn


@dataclass
class _Entry:
    rgb: np.ndarray
    w: int
    h: int
    ts: float


class _FrameStore:
    def __init__(self):
        self._store: Dict[str, _Entry] = {}
        self._lock = threading.Lock()

    def put_bgr(self, name: str, img: np.ndarray):
        if img is None:
            return
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        with self._lock:
            self._store[name] = _Entry(rgb=rgb, w=w, h=h, ts=time())

    def latest(self, name: str) -> Optional[_Entry]:
        with self._lock:
            return self._store.get(name)

    def names(self):
        with self._lock:
            return list(self._store.keys())


class _NamedTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, name: str, store: _FrameStore, fps: float = 30.0):
        super().__init__()
        self.name = name
        self.store = store
        self.frame_interval = 1.0 / max(1.0, float(fps))

    async def recv(self) -> VideoFrame:
        await asyncio.sleep(self.frame_interval)
        pts, time_base = await self.next_timestamp()
        entry = self.store.latest(self.name)
        if entry is None:
            h, w = 480, 640
            img = np.zeros((h, w, 3), np.uint8)
            cv2.putText(img, f"Waiting for '{self.name}' ...",
                        (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
            rgb = img
        else:
            rgb = entry.rgb
        vf = VideoFrame.from_ndarray(rgb, format="rgb24")
        vf.pts = pts
        vf.time_base = time_base
        return vf


def build_app(fps: float = 30.0) -> FastAPI:
    store = _FrameStore()
    pcs: Set[RTCPeerConnection] = set()
    app = FastAPI()

    @app.get("/api/health")
    async def api_health():
        return JSONResponse({"ok": True})

    @app.get("/api/names")
    async def api_names(alive: float | None = Query(None, description="seconds to consider alive")):
        if alive is None:
            return JSONResponse(store.names())
        now = time()
        out = []
        for n in store.names():
            e = store.latest(n)
            if e and (now - e.ts) <= alive:
                out.append(n)
        return JSONResponse(out)

    @app.get("/api/meta")
    async def api_meta(name: str = Query(..., description="Stream name")):
        e = store.latest(name)
        if not e:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        now = time()
        return JSONResponse({
            "ok": True,
            "name": name,
            "w": e.w,
            "h": e.h,
            "ts": e.ts,
            "age": now - e.ts
        })

    @app.get("/api/sockets/names")
    async def api_sockets_names(
            alive: float | None = Query(None, description="seconds to consider alive"),
            poll: float = Query(0.5, description="server-side check interval (sec)"),
            heartbeat: float = Query(15.0, description="send keepalive comment every N sec"),
    ):
        async def event_stream():
            last_key = None
            last_sent = 0.0
            while True:
                now = time()
                names = store.names()
                if alive is not None:
                    names = [n for n in names if (store.latest(n) and (now - store.latest(n).ts) <= alive)]
                names = sorted(set(names))
                key = "|".join(names)

                if key != last_key:
                    last_key = key
                    payload = json.dumps(names, ensure_ascii=False)
                    yield f"event: names\ndata: {payload}\n\n"
                    last_sent = now
                elif now - last_sent >= heartbeat:
                    yield f": keepalive {int(now)}\n\n"
                    last_sent = now

                await asyncio.sleep(max(0.05, float(poll)))

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)

    @app.post("/push")
    async def push(req: Request, name: str = Query(..., description="Stream name")):
        body = await req.body()
        if not body:
            return JSONResponse({"ok": False, "error": "empty"}, status_code=400)
        arr = np.frombuffer(body, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse({"ok": False, "error": "decode fail"}, status_code=400)
        store.put_bgr(name, img)
        h, w = img.shape[:2]
        return JSONResponse({"ok": True, "w": w, "h": h})

    @app.post("/offer")
    async def offer(req: Request, name: str = Query(..., description="Stream name")):
        data = await req.json()
        offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        pc = RTCPeerConnection()
        pcs.add(pc)
        pc.addTrack(_NamedTrack(name=name, store=store, fps=fps))

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ("failed", "closed", "disconnected"):
                await pc.close()
                pcs.discard(pc)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        return JSONResponse({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

    @app.get("/viewer")
    async def viewer(name: str = Query(...)):
        safe = name.replace("<", "").replace(">", "")
        return HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Viewer — {safe}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body{{margin:0;background:#000;color:#fff;font-family:system-ui,Segoe UI,Arial}}
    header{{padding:10px 14px;background:#111;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
    .title{{font-weight:600}}
    .size{{opacity:.7}}
    .btn{{cursor:pointer;border:1px solid #444;border-radius:8px;padding:.3rem .6rem;background:#1b1b1b}}
    .btn:hover{{background:#2a2a2a}}
    main{{display:grid;place-items:center;height:calc(100dvh - 52px);}}
    video{{max-width:100vw;max-height:100%;background:#000}}
  </style>
</head>
<body>
  <header>
    <span class="title">{safe}</span>
    <span id="size" class="size">— …</span>
    <span style="flex:1"></span>
    <button class="btn" id="btnShot">Screenshot</button>
  </header>
  <main>
    <video id="v" autoplay playsinline muted></video>
  </main>
<script>
const name = {json.dumps(name)};
const v = document.getElementById('v');
const sizeEl = document.getElementById('size');

function setSizeLabel(w, h) {{
  if (w && h) sizeEl.textContent = ' — ' + w + '×' + h;
}}

async function start(name) {{
  const pc = new RTCPeerConnection({{iceServers:[{{urls:'stun:stun.l.google.com:19302'}}]}})
  pc.ontrack = (e) => {{ v.srcObject = e.streams[0]; }};
  const offer = await pc.createOffer({{ offerToReceiveVideo: true }});
  await pc.setLocalDescription(offer);
  const resp = await fetch('/offer?name=' + encodeURIComponent(name), {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ sdp: pc.localDescription.sdp, type: pc.localDescription.type }})
  }});
  const answer = await resp.json();
  await pc.setRemoteDescription(new RTCSessionDescription(answer));
}}

async function pullMeta() {{
  try {{
    const r = await fetch('/api/meta?name=' + encodeURIComponent(name));
    if (r.ok) {{
      const m = await r.json();
      if (m.ok) setSizeLabel(m.w, m.h);
    }}
  }} catch(_){{}}
}}

v.addEventListener('loadedmetadata', () => setSizeLabel(v.videoWidth, v.videoHeight));
setInterval(() => {{
  if (v.videoWidth) setSizeLabel(v.videoWidth, v.videoHeight);
}}, 1500);

document.getElementById('btnShot').onclick = () => {{
  if (!v.videoWidth) return;
  const c = document.createElement('canvas');
  c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext('2d').drawImage(v, 0, 0);
  const a = document.createElement('a');
  const ts = new Date().toISOString().replace(/[:.]/g,'-');
  a.download = name + '-' + ts + '.png';
  a.href = c.toDataURL('image/png');
  a.click();
}};

start(name);
pullMeta();
</script>
</body>
</html>
""")

    @app.get("/")
    async def index(names: str = Query("", description="Comma-separated names e.g. Image1,Image2")):
        initial = ",".join([n for n in [s.strip() for s in names.split(",")] if n]) if names else ""
        return HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>FramePublisher</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body{{font-family:system-ui,Segoe UI,Arial;margin:2rem}}
    #bar{{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1rem}}
    .tag{{padding:.25rem .5rem;border:1px solid #999;border-radius:.5rem;cursor:pointer;user-select:none}}
    .tag.active{{background:#222;color:#fff;border-color:#222}}
    #grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
    .tile{{background:#111;border-radius:12px;padding:8px;display:flex;flex-direction:column;gap:6px}}
    .head{{display:flex;align-items:center;gap:8px}}
    .title{{color:#ddd;margin:0 0 0 4px;font-size:14px;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .btn{{cursor:pointer;font-size:12px;border:1px solid #444;background:#1b1b1b;color:#eee;border-radius:8px;padding:.2rem .45rem}}
    .btn:hover{{background:#2a2a2a}}
    video{{width:100%;aspect-ratio:16/9;background:#000;border-radius:8px}}
  </style>
</head>
<body>
  <h2>FramePublisher</h2>
  <div id="bar"></div>
  <div id="grid"></div>

<script>
const grid = document.getElementById('grid');
const pcs = new Map();
const tiles = new Map(); // name -> {{tile, video, title}}

const url = new URL(location.href);
const initial = "{initial}";

function updateURL() {{
  const names = Array.from(pcs.keys()).join(',');
  if (names) url.searchParams.set('names', names); else url.searchParams.delete('names');
  history.replaceState(null, '', url.toString());
}}

function setTitleText(el, name, w, h) {{
  if (w && h) el.textContent = name + " — " + w + "×" + h;
  else el.textContent = name + " — …";
}}

function makeTile(name) {{
  const tile = document.createElement('div'); tile.className = 'tile';

  const head = document.createElement('div'); head.className = 'head';
  const t = document.createElement('div'); t.className='title'; t.textContent = name + " — …";
  head.appendChild(t);

  // buttons
  const bOpen = document.createElement('button'); bOpen.className='btn'; bOpen.textContent='Open';
  bOpen.title = 'ดูวิดีโอขนาดใหญ่';
  bOpen.onclick = () => window.open('/viewer?name=' + encodeURIComponent(name), '_blank');

  const bShot = document.createElement('button'); bShot.className='btn'; bShot.textContent='Screenshot';
  bShot.onclick = () => {{
    const rec = tiles.get(name);
    if (!rec || !rec.video || !rec.video.videoWidth) return;
    const v = rec.video;
    const c = document.createElement('canvas');
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    const a = document.createElement('a');
    const ts = new Date().toISOString().replace(/[:.]/g,'-');
    a.download = name + '-' + ts + '.png';
    a.href = c.toDataURL('image/png');
    a.click();
  }};

  const bHide = document.createElement('button'); bHide.className='btn'; bHide.textContent='Hide';
  bHide.onclick = () => stop(name);

  head.appendChild(bOpen);
  head.appendChild(bShot);
  head.appendChild(bHide);

  const v = document.createElement('video'); v.autoplay = true; v.playsInline = true; v.muted = true;

  tile.appendChild(head);
  tile.appendChild(v);
  grid.appendChild(tile);

  tiles.set(name, {{tile, video: v, title: t}});
  return v;
}}

async function start(name) {{
  if (pcs.has(name)) return;
  const videoEl = makeTile(name);
  const pc = new RTCPeerConnection({{iceServers:[{{urls:'stun:stun.l.google.com:19302'}}]}});

  pcs.set(name, pc);

  pc.ontrack = (e) => {{ videoEl.srcObject = e.streams[0]; }};
  pc.onconnectionstatechange = () => {{
    if (['failed','closed','disconnected'].includes(pc.connectionState)) stop(name);
  }};

  // update title when metadata known
  videoEl.addEventListener('loadedmetadata', () => {{
    const rec = tiles.get(name);
    if (rec) setTitleText(rec.title, name, videoEl.videoWidth, videoEl.videoHeight);
  }});
  // keep it fresh every ~1.5s
  const metaTimer = setInterval(() => {{
    if (!pcs.has(name)) {{ clearInterval(metaTimer); return; }}
    if (videoEl.videoWidth) {{
      const rec = tiles.get(name);
      if (rec) setTitleText(rec.title, name, videoEl.videoWidth, videoEl.videoHeight);
    }}
  }}, 1500);

  // also try server meta once (native size)
  try {{
    const r = await fetch('/api/meta?name=' + encodeURIComponent(name));
    if (r.ok) {{
      const m = await r.json();
      if (m.ok) {{
        const rec = tiles.get(name);
        if (rec) setTitleText(rec.title, name, m.w, m.h);
      }}
    }}
  }} catch(_){{}}

  const offer = await pc.createOffer({{ offerToReceiveVideo: true }});
  await pc.setLocalDescription(offer);
  const resp = await fetch('/offer?name=' + encodeURIComponent(name), {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ sdp: pc.localDescription.sdp, type: pc.localDescription.type }})
  }});
  const answer = await resp.json();
  await pc.setRemoteDescription(new RTCSessionDescription(answer));
  updateURL();
}}

function stop(name) {{
  const pc = pcs.get(name);
  if (pc) {{ try {{ pc.close(); }} catch{{}} pcs.delete(name); }}
  const rec = tiles.get(name);
  if (rec) {{ rec.tile.remove(); tiles.delete(name); }}
  const chip = document.querySelector(`[data-name="${{CSS.escape(name)}}"]`);
  if (chip) chip.classList.remove('active');
  updateURL();
}}

function renderBar(names) {{
  const bar = document.getElementById('bar');
  const active = new Set(pcs.keys());
  bar.innerHTML = '';
  names.forEach(n => {{
    const a = document.createElement('span');
    a.textContent = n;
    a.className = 'tag';
    a.dataset.name = n;
    a.onclick = () => {{
      if (pcs.has(n)) stop(n);
      else {{ a.classList.add('active'); start(n); }}
    }};
    if (active.has(n)) a.classList.add('active');
    bar.appendChild(a);
  }});
}}

// ---- SSE auto update ----
const es = new EventSource('/api/sockets/names');
es.addEventListener('names', (ev) => {{
  const names = JSON.parse(ev.data);
  renderBar(names);
}});
es.onerror = () => {{}};

(async () => {{
  // auto-start from ?names=...
  const qs = (initial || new URL(location.href).searchParams.get('names') || '')
    .split(',').map(s=>s.trim()).filter(Boolean);
  for (const n of qs) {{
    start(n);
    const chip = document.querySelector(`[data-name="${{CSS.escape(n)}}"]`);
    if (chip) chip.classList.add('active');
  }}
}})();
</script>
</body>
</html>
""")

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=2004)
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args()

    app = build_app(fps=args.fps)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
