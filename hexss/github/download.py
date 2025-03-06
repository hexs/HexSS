import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import hexss
from hexss.constants.terminal_color import *
from tqdm import tqdm

headers = hexss.get_config('headers')


def collect_file_tasks(api_url, dest_folder):
    """
    Recursively collects file download tasks from the GitHub API.
    """
    tasks = []
    os.makedirs(dest_folder, exist_ok=True)
    try:
        response = requests.get(api_url, headers=headers, proxies=hexss.proxies or {})
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"\n{RED}Error: Unable to fetch data from {api_url} - {e}{END}")
        return tasks

    try:
        data = response.json()
    except ValueError:
        print(f"\n{RED}Error: Invalid JSON response from {api_url}{END}")
        return tasks

    if not isinstance(data, list):
        print(f"\n{RED}Error: Expected a list of items from {api_url}{END}")
        return tasks

    for item in data:
        item_type = item.get('type')
        if item_type == 'file':
            file_name = item.get('name')
            download_url = item.get('download_url')
            file_path = os.path.join(dest_folder, file_name)
            tasks.append((download_url, file_path))
        elif item_type == 'dir':
            new_api_url = item.get('url')
            new_dest_folder = os.path.join(dest_folder, item.get('name'))
            tasks.extend(collect_file_tasks(new_api_url, new_dest_folder))
    return tasks


def download_file(download_url, file_path):
    """
    Downloads a single file using streaming and displays a file-level progress bar.
    """
    # Skip if file already exists
    if os.path.exists(file_path):
        return
    try:
        with requests.get(download_url, headers=headers, proxies=hexss.proxies or {}, stream=True) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            total_length = r.headers.get('content-length')
            if total_length is None:
                # If no content-length header, simply write the content
                with open(file_path, 'wb') as f:
                    f.write(r.content)
            else:
                downloaded = 0
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

    except requests.RequestException as e:
        print(f"\n{RED}Failed to download {os.path.basename(file_path)}: {e}{END}")


def download(api_url, max_workers=20):
    """
    Recursively downloads content from a GitHub API URL using multi-threaded file downloads.
    Uses an overall progress bar to track total file downloads.
    The destination folder is derived from the last segment of the API URL.
    """
    dest_folder = api_url.rstrip('/').split('/')[-1]
    tasks = collect_file_tasks(api_url, dest_folder)
    print(f"\n{CYAN}Found {len(tasks)} files to download in '{dest_folder}'.{END}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        # Create a global progress bar for overall file download progress.
        with tqdm(total=len(tasks), desc="Overall Progress", unit="file") as pbar:
            for download_url, file_path in tasks:
                future = executor.submit(download_file, download_url, file_path)
                # Update the global progress bar as soon as a file download completes.
                future.add_done_callback(lambda p: pbar.update(1))
                futures.append(future)
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"\n{RED}Error in file download: {e}{END}")


if __name__ == "__main__":
    api_url = "https://api.github.com/repos/hexs/Image-Dataset/contents/flower_photos"
    download(api_url)
