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
TEMP_DIR = Path("temp")


def setup_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=RETRIES,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_filename_from_url(url: str) -> str:
    name = os.path.basename(urlsplit(url).path)
    if not name:
        raise ValueError(f"Cannot parse filename from URL: {url}")
    return name


def get_total_size(sess: requests.Session, url: str) -> int | None:
    resp = sess.head(url, timeout=TIMEOUT)
    resp.raise_for_status()
    size_header = resp.headers.get("Content-Length")
    if size_header is None or int(size_header) <= 0:
        return None
    return int(size_header)


def download_streaming(sess: requests.Session, url: str, filename: str) -> None:
    dest = Path(filename)
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
        tmp.unlink()
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

    with tqdm(
            total=total,
            initial=existing,
            unit="B",
            unit_scale=True,
            desc=filename
    ) as pbar, tmp.open(mode) as f:
        for chunk in r.iter_content(CHUNK_SIZE):
            if not chunk:
                continue
            f.write(chunk)
            pbar.update(len(chunk))

    tmp.replace(dest)
    print(f"{GREEN}✔ Download complete: {filename}{END}")


def download_chunk(
        sess: requests.Session,
        url: str,
        start: int,
        end: int,
        part_path: Path,
        pbar: tqdm
) -> None:
    headers = {"Range": f"bytes={start}-{end}"}
    expected = end - start + 1

    for attempt in range(1, RETRIES + 1):
        try:
            r = sess.get(url, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.content
            if len(data) != expected:
                raise IOError(f"Got {len(data)} bytes, expected {expected}")
            part_path.write_bytes(data)
            pbar.update(expected)
            return
        except Exception as e:
            tqdm.write(f"[{part_path.name}] attempt {attempt} failed: {e}")
            if attempt == RETRIES:
                print(f"{RED}ERROR: giving up on {part_path.name}{END}", file=sys.stderr)
                sys.exit(1)


def assemble_file(tmp: Path, filename: str, chunks: int) -> Path:
    out = tmp / filename
    with out.open("wb") as fout:
        for i in range(chunks):
            part = tmp / f"{filename}.part{i}"
            if not part.exists():
                raise FileNotFoundError(f"Missing chunk {i}")
            fout.write(part.read_bytes())
            part.unlink()
    return out


def download(url: str, filename: str = None) -> None:
    sess = setup_session()

    if filename is None:
        filename = get_filename_from_url(url)
    dest = Path(filename)
    if dest.exists():
        print(f"{GREEN}{filename} already exists; {YELLOW}skipping.{END}")
        return

    total = get_total_size(sess, url)
    if total is None:
        return download_streaming(sess, url, filename)

    parts = math.ceil(total / CHUNK_SIZE)
    TEMP_DIR.mkdir(exist_ok=True)

    tasks = []
    for i in range(parts):
        start = i * CHUNK_SIZE
        end = min(total - 1, start + CHUNK_SIZE - 1)
        part = TEMP_DIR / f"{filename}.part{i}"
        if part.exists() and part.stat().st_size == (end - start + 1):
            continue
        tasks.append((start, end, part))

    print(f"{YELLOW}Downloading {filename}: {total:,} bytes in {parts} chunks{END}")
    with tqdm(total=total, unit="B", unit_scale=True, desc=filename) as pbar:
        done = total - sum((e - s + 1) for s, e, _ in tasks)
        pbar.update(done)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
            futures = {
                exe.submit(download_chunk, sess, url, s, e, p, pbar): p
                for s, e, p in tasks
            }
            for f in as_completed(futures):
                f.result()

    print(f"{GREEN}All chunks done; {YELLOW}assembling file…{END}")
    assembled = assemble_file(TEMP_DIR, filename, parts)
    shutil.move(str(assembled), filename)
    print(f"{GREEN}✔ Download complete: {filename}{END}")


if __name__ == '__main__':
    # Example usage:
    urls = [
        'https://downloads.raspberrypi.com/raspios_full_armhf/images/raspios_full_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-full.img.xz',
        'https://uk.download.nvidia.com/nvapp/client/11.0.2.337/NVIDIA_app_v11.0.2.337.exe',
        ('https://codeload.github.com/hexs/auto_inspection_data__FE4-1624-000/zip/refs/heads/main',
         'auto_inspection_data__FE4-1624-000.zip'),
    ]

    for entry in urls:
        if isinstance(entry, str):
            download(entry)
        else:
            download(entry[0], entry[1])
