import os
import time
import threading
from typing import List, Tuple, Optional, Dict

import requests
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import hexss

try:
    DEFAULT_PROXIES = hexss.get_config('proxies') or None
    DEFAULT_HEADERS = hexss.get_config('headers') or None
except ImportError:
    DEFAULT_PROXIES = None
    DEFAULT_HEADERS = None


def _download_file(
        file_url: str,
        filename: str,
        counter: List[int],
        total: int,
        lock: threading.Lock,
        skip_existing: bool,
        failed_files: List[Tuple[str, str, str]],
        timeout: int = 20,
        headers: Optional[Dict[str, str]] = None,
        proxies: Optional[Dict[str, str]] = None,
        max_retries: int = 3
):
    """
    Downloads a single file and updates progress. Appends failed downloads to failed_files list.
    """
    try:
        if skip_existing and os.path.exists(filename):
            with lock:
                counter[0] += 1
                percent = (counter[0] / total) * 100
                print(f"Skipped: {filename} [{counter[0]}/{total}] ({percent:.1f}%)")
            return

        tries = 0
        while tries < max_retries:
            try:
                file_r = requests.get(file_url, timeout=timeout, headers=headers, proxies=proxies)
                file_r.raise_for_status()
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'wb') as f:
                    f.write(file_r.content)
                with lock:
                    counter[0] += 1
                    percent = (counter[0] / total) * 100
                    print(f"Downloaded: {filename} [{counter[0]}/{total}] ({percent:.1f}%)")
                return
            except requests.RequestException as e:
                tries += 1
                if tries >= max_retries:
                    raise
                time.sleep(1)
    except Exception as e:
        with lock:
            failed_files.append((file_url, filename, str(e)))
        print(f"Failed: {filename} ({file_url}) - {e}")


def _list_files_recursive(
        owner: str,
        repo: str,
        path: str,
        branch: str,
        timeout: int = 20,
        headers: Optional[Dict[str, str]] = None,
        proxies: Optional[Dict[str, str]] = None,
        max_retries: int = 3
) -> List[Dict[str, str]]:
    """
    Recursively fetch files and their paths from a GitHub folder.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    tries = 0
    while True:
        try:
            r = requests.get(api_url, timeout=timeout, headers=headers, proxies=proxies)
            if r.status_code == 403 and r.headers.get('X-RateLimit-Remaining') == '0':
                sleep_time = int(r.headers.get('Retry-After', 30))
                print(f"Rate limited by GitHub API. Sleeping for {sleep_time} seconds...")
                time.sleep(sleep_time)
                continue
            r.raise_for_status()
            items = r.json()
            break
        except requests.RequestException as e:
            tries += 1
            if tries >= max_retries:
                print(f"Failed to list directory {api_url}: {e}")
                return []
            time.sleep(2)
    files = []
    for item in items:
        if item['type'] == 'file':
            files.append({
                "download_url": item['download_url'],
                "path": item['path']
            })
        elif item['type'] == 'dir':
            files.extend(_list_files_recursive(
                owner, repo, item['path'], branch, timeout, headers, proxies, max_retries
            ))
    return files


def download(
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        path: str = '',
        branch: str = 'main',
        url: Optional[str] = None,
        save_dir: Optional[str] = None,
        max_workers: int = 16,
        skip_existing: bool = True,
        files_to_download: Optional[List[Dict[str, str]]] = None,
        timeout: int = 20,
        headers: Optional[Dict[str, str]] = None,
        proxies: Optional[Dict[str, str]] = None,
        max_retries: int = 3
) -> List[Tuple[str, str, str]]:
    """
    Download a file or all files from a GitHub folder (recursively).
    Returns a list of (file_url, filename, error_message) tuples for files that failed to download.
    """
    if headers is None:
        headers = DEFAULT_HEADERS
    if proxies is None:
        proxies = DEFAULT_PROXIES
    if not save_dir:
        save_dir = '.'

    # Parse URL (if provided)
    if url is not None:
        parts = url.split('/')
        owner, repo, _, branch = parts[3:7]
        path = '/'.join(parts[7:])
        if 'blob' in url:
            mode = 'file'
        elif 'tree' in url:
            mode = 'folder'
        else:
            raise ValueError("URL must contain 'blob' (for file) or 'tree' (for folder)")
    else:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        r = requests.get(api_url, timeout=timeout, headers=headers, proxies=proxies)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get('type') == 'file':
            mode = 'file'
        elif isinstance(data, list) or (isinstance(data, dict) and data.get('type') == 'dir'):
            mode = 'folder'
        else:
            raise ValueError("Could not determine if path is file or folder")

    failed_files: List[Tuple[str, str, str]] = []

    if mode == 'file':
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        filename = os.path.basename(unquote(path))
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, filename)
        if skip_existing and os.path.exists(filepath):
            print(f"Skipped: {filepath}")
        else:
            print(f"Downloading {raw_url} to {filepath}")
            try:
                r = requests.get(raw_url, timeout=timeout, headers=headers, proxies=proxies)
                r.raise_for_status()
                with open(filepath, 'wb') as f:
                    f.write(r.content)
                print(f"Downloaded: {filepath}")
            except Exception as e:
                print(f"Failed: {filepath} ({raw_url}) - {e}")
                failed_files.append((raw_url, filepath, str(e)))

    elif mode == 'folder':
        print("Listing all files recursively. This may take a while for large folders...")
        if files_to_download is not None:
            files = files_to_download
        else:
            files = _list_files_recursive(owner, repo, path, branch, timeout, headers, proxies, max_retries)
        total = len(files)
        if total == 0:
            print("No files to download.")
            return []
        counter = [0]
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _download_file,
                    file['download_url'],
                    os.path.join(
                        save_dir,
                        unquote(file['path'][len(path):].lstrip('/\\')) if path else unquote(file['path'])
                    ),
                    counter, total, lock, skip_existing, failed_files, timeout, headers, proxies, max_retries
                )
                for file in files
            ]
            for future in as_completed(futures):
                future.result()
        print(f"All files downloaded to: {save_dir}")

    return failed_files


def download_until_complete(
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        path: str = '',
        branch: str = 'main',
        url: Optional[str] = None,
        save_dir: Optional[str] = None,
        max_workers: int = 16,
        sleep_seconds: int = 10,
        max_retries: int = 10,
        timeout: int = 20,
        headers: Optional[Dict[str, str]] = None,
        proxies: Optional[Dict[str, str]] = None,
):
    """
    Download files, retrying failed ones until all are complete or max_retries reached.
    """
    if headers is None:
        headers = DEFAULT_HEADERS
    if proxies is None:
        proxies = DEFAULT_PROXIES

    retries = 0
    files_to_download: Optional[List[Dict[str, str]]] = None  # None means get all files from repo
    while True:
        failed_files = download(
            owner=owner,
            repo=repo,
            path=path,
            branch=branch,
            url=url,
            save_dir=save_dir,
            max_workers=max_workers,
            skip_existing=True,
            files_to_download=(
                [{"download_url": f[0], "path": f[1]} for f in files_to_download]
                if files_to_download else None
            ),
            timeout=timeout,
            headers=headers,
            proxies=proxies,
            max_retries=3
        )
        if not failed_files:
            print("All files downloaded (no failures).")
            break
        retries += 1
        if retries >= max_retries:
            print(f"Giving up after {retries} retries. {len(failed_files)} files failed to download.")
            for f_url, f_path, f_err in failed_files:
                print(f"FAILED: {f_path} ({f_url}) - {f_err}")
            break
        print(
            f"{len(failed_files)} files failed to download. Retrying {retries}/{max_retries} after {sleep_seconds}s...")
        files_to_download = [(f_url, f_path) for f_url, f_path, _ in failed_files]
        time.sleep(sleep_seconds)


if __name__ == '__main__':
    # Optional: Setup a token for private repos
    # headers = {"Authorization": "token YOUR_GITHUB_TOKEN"}
    headers = None
    # Optional: Setup proxies if needed
    proxies = None  # e.g., {"http": "http://proxy:port", "https": "http://proxy:port"}
    download_until_complete(
        url='https://github.com/hexs/Image-Dataset/tree/main/flower_photos',
        max_workers=200,
        save_dir='photos',
        max_retries=10,
        headers=headers,
        proxies=proxies
    )
