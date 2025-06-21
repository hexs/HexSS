import os
import time
import threading
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import hexss
from hexss.constants import GREEN, YELLOW, RED, END

try:
    DEFAULT_HEADERS = hexss.get_config('headers')
    DEFAULT_PROXIES = hexss.get_config('proxies')
except ImportError:
    DEFAULT_HEADERS = None
    DEFAULT_PROXIES = None


def _download_file(
        file_url: str,
        filename: str,
        counter: List[int],
        total: int,
        lock: threading.Lock,
        skip_existing: bool,
        failed_files: List[Tuple[str, str, str]],
        headers: Optional[Dict[str, str]] = DEFAULT_HEADERS,
        proxies: Optional[Dict[str, str]] = DEFAULT_PROXIES,
):
    """
    Downloads a single file and updates progress. Appends failed downloads to failed_files list.
    """
    try:
        if skip_existing and os.path.exists(filename):
            with lock:
                counter[0] += 1
                percent = (counter[0] / total) * 100
                print(f"\r{YELLOW}[{counter[0]}/{total}] ({percent:.1f}%) "
                      f"Skipped: {YELLOW.UNDERLINED}{filename}{END}", end='')
            return

        file_r = requests.get(file_url, headers=headers, proxies=proxies)
        file_r.raise_for_status()
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'wb') as f:
            f.write(file_r.content)
        with lock:
            counter[0] += 1
            percent = (counter[0] / total) * 100
            print(f"\r{GREEN}[{counter[0]}/{total}] ({percent:.1f}%) "
                  f"Downloaded: {GREEN.UNDERLINED}{filename}{END}", end='')
        return


    except Exception as e:
        with lock:
            failed_files.append((file_url, filename, str(e)))
        print(f"\r{RED}Failed: {RED.UNDERLINED}{filename}{END} ({file_url}) - {e}\n", end='')


def _list_files_recursive(
        owner: str,
        repo: str,
        path: str,
        branch: str,
        headers: Optional[Dict[str, str]] = DEFAULT_HEADERS,
        proxies: Optional[Dict[str, str]] = DEFAULT_PROXIES,
) -> List[Dict[str, str]]:
    """
    Recursively fetch files and their paths from a GitHub folder.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    try:
        r = requests.get(api_url, headers=headers, proxies=proxies)
        r.raise_for_status()
        items = r.json()

    except requests.RequestException as e:
        print(f"\r{RED}Failed to list directory {api_url}:{END} {e}")
        return []

    files = []
    for item in items:
        if item['type'] == 'file':
            files.append({
                "download_url": item['download_url'],
                "path": item['path']
            })
        elif item['type'] == 'dir':
            files.extend(_list_files_recursive(
                owner, repo, item['path'], branch, headers, proxies
            ))
    return files


def download(
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        path: str = '',
        branch: str = 'main',
        url: Optional[str] = None,
        dest_dir: str | Path = '.',
        max_workers: int = 16,
        skip_existing: bool = True,
        files_to_download: Optional[List[Dict[str, str]]] = None,
        headers: Optional[Dict[str, str]] = DEFAULT_HEADERS,
        proxies: Optional[Dict[str, str]] = DEFAULT_PROXIES
) -> List[Tuple[str, str, str]]:
    """
    Download a file or all files from a GitHub folder (recursively).
    Returns a list of (file_url, filename, error_message) tuples for files that failed to download.
    """

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
        r = requests.get(api_url, headers=headers, proxies=proxies)
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
        os.makedirs(dest_dir, exist_ok=True)
        filepath = os.path.join(dest_dir, filename)
        if skip_existing and os.path.exists(filepath):
            print(f"\r{YELLOW}Skipped: {YELLOW.UNDERLINED}{filepath}{END}")
        else:
            try:
                r = requests.get(raw_url, headers=headers, proxies=proxies)
                r.raise_for_status()
                with open(filepath, 'wb') as f:
                    f.write(r.content)
                print(f"\r{GREEN}Downloaded: {GREEN.UNDERLINED}{filepath}{END}")
            except Exception as e:
                print(f"\r{RED}Failed: {RED.UNDERLINED}{filepath}{END} ({raw_url}) - {e}\n", end='')
                failed_files.append((raw_url, filepath, str(e)))

    elif mode == 'folder':
        print(f"\r{YELLOW}Listing all files recursively. This may take a while for large folders...{END}", end='')
        if files_to_download is not None:
            files = files_to_download
        else:
            files = _list_files_recursive(owner, repo, path, branch, headers, proxies)
        total = len(files)
        if total == 0:
            print("\rNo files to download.")
            return []
        counter = [0]
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _download_file,
                    file['download_url'],
                    os.path.join(
                        dest_dir,
                        unquote(file['path'][len(path):].lstrip('/\\')) if path else unquote(file['path'])
                    ),
                    counter, total, lock, skip_existing, failed_files, headers, proxies
                )
                for file in files
            ]
            for future in as_completed(futures):
                future.result()
        print(f"\r{GREEN}All files downloaded to: {GREEN.UNDERLINED}{dest_dir}{END}")

    return failed_files


def download_until_complete(
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        path: str = '',
        branch: str = 'main',
        url: Optional[str] = None,
        dest_dir: str | Path = '.',
        max_workers: int = 16,
        retries: int = 10,
        wait: int = 5,
        headers: Optional[Dict[str, str]] = DEFAULT_HEADERS,
        proxies: Optional[Dict[str, str]] = DEFAULT_PROXIES,
):
    """
    Download files, retrying failed ones until all are complete or retries reached.
    """
    attempt = 0
    files_to_download: Optional[List[Dict[str, str]]] = None  # None means get all files from repo
    while True:
        failed_files = download(
            owner=owner,
            repo=repo,
            path=path,
            branch=branch,
            url=url,
            dest_dir=dest_dir,
            max_workers=max_workers,
            skip_existing=True,
            files_to_download=(
                [{"download_url": f[0], "path": f[1]} for f in files_to_download]
                if files_to_download else None
            ),
            headers=headers,
            proxies=proxies
        )
        if not failed_files:
            break
        attempt += 1
        if attempt >= retries:
            print(f"Giving up after {attempt} attempt. {len(failed_files)} files failed to download.")
            for f_url, f_path, f_err in failed_files:
                print(f"FAILED: {f_path} ({f_url}) - {f_err}")
            break
        print(f"{len(failed_files)} files failed to download. "
              f"Retrying {attempt}/{retries} after {wait}s...")
        files_to_download = [(f_url, f_path) for f_url, f_path, _ in failed_files]
        time.sleep(wait)


if __name__ == '__main__':
    # Example usage:
    # Optional: Setup a token for private repos
    # headers = {"Authorization": "token YOUR_GITHUB_TOKEN"}
    headers = None
    # Optional: Setup proxies if needed
    proxies = None  # e.g., {"http": "http://proxy:port", "https": "http://proxy:port"}
    download_until_complete(
        url='https://github.com/hexs/Image-Dataset/tree/main/flower_photos',
        max_workers=200,
        dest_dir='photos',
        headers=headers,
        proxies=proxies
    )
    # or
    download_until_complete(
        'hexs', 'Image-Dataset', 'Other/people.jpg',
        max_workers=200,
        dest_dir='photos2',
    )
