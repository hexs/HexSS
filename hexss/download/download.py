import os
import sys
import math
import shutil
from pathlib import Path
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor, as_completed

import hexss
from hexss.constants.terminal_color import *

hexss.check_packages('requests', 'tqdm', auto_install=True)
import requests
from requests.adapters import HTTPAdapter, Retry
from tqdm.auto import tqdm

CHUNK_SIZE = 1024 * 1024  # 1 MiB
MAX_WORKERS = min(32, os.cpu_count() or 1)
RETRIES = 5  # per-chunk retry count
TIMEOUT = 30  # seconds


class RangeUnsupported(Exception):
    pass


def setup_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=RETRIES,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"Accept-Encoding": "identity", "User-Agent": "hexss-downloader/1.0"})
    return session


def get_filename_from_url(url: str) -> str:
    name = os.path.basename(urlsplit(url).path)
    if not name:
        raise ValueError(f"Cannot parse filename from URL: {url}")
    return name


def get_total_size(sess: requests.Session, url: str) -> int | None:
    resp = sess.head(url, timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    cl = resp.headers.get("Content-Length")
    if cl is None:
        return None
    try:
        size = int(cl)
        return size if size > 0 else None
    except ValueError:
        return None


def server_supports_range(sess: requests.Session, url: str) -> bool:
    try:
        h = sess.head(url, timeout=TIMEOUT, allow_redirects=True)
        if h.headers.get("Accept-Ranges", "").lower() == "bytes":
            return True
    except Exception:
        pass
    try:
        r = sess.get(url, headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"}, timeout=TIMEOUT, stream=False)
        return r.status_code == 206 and "Content-Range" in r.headers
    except Exception:
        return False


def download_streaming(sess: requests.Session, url: str, dest_path: Path) -> None:
    dest = dest_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    existing = tmp.stat().st_size if tmp.exists() else 0
    headers = {}
    mode = "wb"

    if existing:
        print(f"{YELLOW}Resuming streaming download from {existing} bytes…{END}")
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"

    r = sess.get(url, stream=True, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()

    if existing and r.status_code == 200:
        tqdm.write(f"{YELLOW}Server ignored Range header; restarting download…{END}")
        tmp.unlink(missing_ok=True)
        existing = 0
        mode = "wb"
        r.close()
        r = sess.get(url, stream=True, timeout=TIMEOUT)
        r.raise_for_status()

    if r.status_code == 206 and "Content-Range" in r.headers:
        total = int(r.headers["Content-Range"].split("/", 1)[1])
    else:
        cl = r.headers.get("Content-Length")
        total = int(cl) + existing if cl else None

    with tqdm(total=total, initial=existing, unit="B", unit_scale=True, desc=dest.name) as pbar, tmp.open(mode) as f:
        for chunk in r.iter_content(CHUNK_SIZE):
            if not chunk:
                continue
            f.write(chunk)
            pbar.update(len(chunk))

    tmp.replace(dest)
    print(f"{GREEN}✔ Download complete: {dest}{END}")


def download_chunk(
        sess: requests.Session,
        url: str,
        start: int,
        end: int,
        part_path: Path,
        pbar: tqdm
) -> None:
    headers = {"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}
    expected = end - start + 1

    for attempt in range(1, RETRIES + 1):
        try:
            r = sess.get(url, headers=headers, timeout=TIMEOUT, stream=False)
            if r.status_code != 206 or "Content-Range" not in r.headers:
                raise RangeUnsupported("Server did not return 206/Content-Range for a ranged request.")
            r.raise_for_status()
            data = r.content
            if len(data) != expected:
                raise IOError(f"Got {len(data)} bytes, expected {expected}")
            part_path.write_bytes(data)
            pbar.update(expected)
            return
        except RangeUnsupported:
            raise
        except Exception as e:
            tqdm.write(f"[{part_path.name}] attempt {attempt} failed: {e}")
            if attempt == RETRIES:
                print(f"{RED}ERROR: giving up on {part_path.name}{END}", file=sys.stderr)
                raise


def assemble_file(temp_dir: Path, filename: str, chunks: int) -> Path:
    out = temp_dir / filename
    with out.open("wb") as fout:
        for i in range(chunks):
            part = temp_dir / f"{filename}.part{i}"
            if not part.exists():
                raise FileNotFoundError(f"Missing chunk {i}")
            fout.write(part.read_bytes())
            part.unlink(missing_ok=True)
    return out


def download(
        url: str | tuple[str, str] | list[str],
        filename: str | None = None,
        dest_dir: str | Path = ".",
        temp_subdir: str = ".parts"
) -> Path:
    """
    Download `url` into directory `dest_dir`.
    - If `filename` is None, derive from URL.
    - Ranged chunking when server supports; otherwise streaming.
    - Temp parts are stored in `dest_dir / temp_subdir`.
    Returns final Path of the downloaded file.
    """
    sess = setup_session()

    if filename is None:
        if isinstance(url, str):
            filename = get_filename_from_url(url)
        else:
            filename = url[1]
            url = url[0]

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = dest_dir / temp_subdir
    temp_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    if dest.exists():
        print(f"{UNDERLINED}{dest.name}{END} {GREEN}already exists; {YELLOW}skipping.{END}")
        return dest

    total = get_total_size(sess, url)
    if total is None:
        download_streaming(sess, url, dest)
        return dest

    can_chunk = total > CHUNK_SIZE and server_supports_range(sess, url)
    if not can_chunk:
        download_streaming(sess, url, dest)
        return dest

    parts = math.ceil(total / CHUNK_SIZE)

    tasks = []
    for i in range(parts):
        start = i * CHUNK_SIZE
        end = min(total - 1, start + CHUNK_SIZE - 1)
        part = temp_dir / f"{dest.name}.part{i}"
        if part.exists() and part.stat().st_size == (end - start + 1):
            continue
        tasks.append((start, end, part))

    try:
        with tqdm(total=total, unit="B", unit_scale=True, desc=dest.name) as pbar:
            done = total - sum((e - s + 1) for s, e, _ in tasks)
            pbar.update(done)

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                futures = {exe.submit(download_chunk, sess, url, s, e, p, pbar): p for s, e, p in tasks}
                for f in as_completed(futures):
                    try:
                        f.result()
                    except RangeUnsupported:
                        tqdm.write(f"{YELLOW}Server doesn’t properly support Range; falling back to streaming…{END}")
                        for _s, _e, _p in tasks:
                            _p.unlink(missing_ok=True)
                        download_streaming(sess, url, dest)
                        return dest
    except Exception:
        tqdm.write(f"{YELLOW}Chunked download failed; trying streaming mode…{END}")
        for i in range(parts):
            (temp_dir / f"{dest.name}.part{i}").unlink(missing_ok=True)
        download_streaming(sess, url, dest)
        return dest

    print(f"{GREEN}All chunks done; {YELLOW}assembling file…{END}")
    assembled = assemble_file(temp_dir, dest.name, parts)
    shutil.move(str(assembled), dest)
    print(f"{GREEN}✔ Download complete:{END} {UNDERLINED}{dest}{END}")
    return dest


if __name__ == '__main__':
    # from hexss.env import set_proxy
    #
    # set_proxy() # if use hexss proxy

    download('https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css', )
    download(
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css',
        dest_dir='C://downloads'
    )
    download(
        'https://downloads.raspberrypi.com/raspios_full_armhf/images/raspios_full_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-full.img.xz',
        dest_dir='downloads'
    )
    download(
        'https://uk.download.nvidia.com/nvapp/client/11.0.2.337/NVIDIA_app_v11.0.2.337.exe',
        dest_dir='downloads'
    )
    download(
        'https://codeload.github.com/hexs/auto_inspection_data__QC7-7990-000-Example/zip/refs/heads/main',
        filename='QC7-7990.zip',
        dest_dir='downloads'
    )
    download(
        'https://developer.download.nvidia.com/compute/cudnn/secure/8.9.7/local_installers/11.x/cudnn-windows-x86_64-8.9.7.29_cuda11-archive.zip?'
        '__token__=exp=1761282766~hmac=cbecdd2da55fa7e1f014a326fcb192fa4d198859d3343ec74505c473f3e708da&'
        't=eyJscyI6InJlZiIsImxzZCI6IlJFRi1naXRodWIuY29tL2hleHMvVmFsb3JhbnQtQUkvYmxvYi9tYWluL3RyYWluX3lvbG92OF93aXRoX2dwdS9SRUFETUVfZm9yX3VzZV9HUFUubWQifQ==')

    download(
        'https://developer.download.nvidia.com/compute/cudnn/secure/8.9.7/local_installers/12.x/cudnn-windows-x86_64-8.9.7.29_cuda12-archive.zip?'
        '__token__=exp=1761282457~hmac=210a75b71bd87d51b15a807076ee12131e6891a8663a002faf4de5fb9d2b4e60&'
        't=eyJscyI6InJlZiIsImxzZCI6IlJFRi1naXRodWIuY29tL2hleHMvVmFsb3JhbnQtQUkvYmxvYi9tYWluL3RyYWluX3lvbG92OF93aXRoX2dwdS9SRUFETUVfZm9yX3VzZV9HUFUubWQifQ==')

    download('https://developer.download.nvidia.com/compute/cuda/13.0.1/local_installers/cuda_13.0.1_windows.exe')
