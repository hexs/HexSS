from typing import Optional, Union, List
import os
import time

import hexss
from hexss.constants import *

hexss.check_packages('requests', 'GitPython', auto_install=True)

import requests
from git import Repo, GitCommandError, InvalidGitRepositoryError


def clone(path: str, url: str, branch: str = "main", timeout: Optional[int] = None) -> Repo:
    """
    Clone a Git repository to the given path.

    Args:
        path (str): Destination directory path.
        url (str): Repository URL.
        branch (str): Branch to check out after cloning.
        timeout (Optional[int]): Timeout for the clone operation in seconds.

    Returns:
        Repo: GitPython Repo object for the cloned repository.

    Raises:
        ValueError: If url is empty or invalid.
        RuntimeError: If Git command fails.
    """
    if url is None:
        raise ValueError("A repository URL must be provided for cloning.")

    try:
        print(f"Cloning '{url}' into '{path}'...")
        repo = Repo.clone_from(url, path, branch=branch, single_branch=True, depth=1, timeout=timeout)
        print(f"✅ {GREEN}Successfully cloned{END} '{url}' to '{repo.working_dir}'.")
        return repo
    except GitCommandError as e:
        raise RuntimeError(f"{RED}Git clone failed{END}: {e.stderr.strip()}") from e
    except Exception as e:
        raise RuntimeError(f"{RED}Unexpected error during clone{END}: {e}") from e


def pull(path: str, branch: str = "main") -> str:
    """
    Pull latest changes from origin for the given repository path and branch.

    Args:
        path (str): Path to existing Git repository.
        branch (str): Branch to pull from origin.

    Returns:
        str: Output from the Git pull command.

    Raises:
        RuntimeError: If directory is not a Git repo or Git command fails.
    """
    try:
        repo = Repo(path)
    except InvalidGitRepositoryError:
        raise RuntimeError(f"'{path}' is not a valid Git repository.")

    try:
        print(f"Pulling latest changes in '{path}' (branch '{branch}')...")
        output = repo.git.pull("origin", branch)
        print(f"✅ {GREEN}Pull result{END}: {output}")
        return output
    except GitCommandError as e:
        raise RuntimeError(f"Git pull failed: {e.stderr.strip()}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error during pull: {e}") from e


def clone_or_pull(path: str, url: Optional[str] = None, branch: str = "main") -> Union[Repo, str]:
    """
    Clone the repository if not already present, otherwise pull latest changes.

    Args:
        path (str): Local path for repository.
        url (Optional[str]): Repository URL. Required if cloning.
        branch (str): Branch name for both clone and pull.

    Returns:
        Union[Repo, str]: Repo object if cloned, or pull output if pulled.
    """
    git_dir = os.path.join(path, ".git")
    if not os.path.isdir(git_dir):
        if not url:
            raise ValueError("URL is required to clone into an empty directory.")
        return clone(path, url, branch)
    return pull(path, branch)


def auto_pull(path: str, interval: int = 600, branch: str = "main") -> None:
    """
    Continuously pull latest changes at given time intervals.

    Args:
        path (str): Path to Git repository.
        interval (int): Polling interval in seconds.
        branch (str): Branch to pull.
    """
    while True:
        try:
            pull(path, branch)
        except Exception as e:
            print(f"{RED}Auto-pull error{END}: {e}")
        time.sleep(interval)


def push_if_dirty(path: str, branch: str = "main", commit_message: Optional[str] = None) -> None:
    """
    Commit and push changes if the working tree is dirty.

    Args:
        path (str): Path to Git repository.
        branch (str): Target branch for push.
        commit_message (Optional[str]): Custom commit message. Defaults to auto-generated.
    """
    try:
        repo = Repo(path)
    except InvalidGitRepositoryError:
        raise RuntimeError(f"'{path}' is not a valid Git repository.")

    if not repo.is_dirty(untracked_files=True):
        print(f"{GREEN}Working tree clean; no changes to push.{END}")
        return

    repo.git.add(A=True)
    modified = [item.a_path for item in repo.index.diff(None)]
    msg = commit_message or f"Auto-update: {', '.join(modified)}"
    repo.index.commit(msg)
    print(f"{PINK}Committed changes{END}: {msg}")
    origin = repo.remote(name="origin")
    push_info = origin.push(branch)
    for info in push_info:
        if info.flags & info.ERROR:
            raise RuntimeError(f"Push failed: {info.summary}")
    print(f"✅ {GREEN}Pushed to origin/{branch} successfully.{END}")


def fetch_repositories(username: str) -> Optional[List[dict]]:
    """
    Fetch public repositories of a GitHub user.

    Args:
        username (str): GitHub username.
        use_proxy (bool): Whether to route through configured proxies.

    Returns:
        Optional[List[dict]]: List of repo data or None on failure.
    """
    if not username:
        raise ValueError("GitHub username must be provided.")

    url = f"https://api.github.com/users/{username}/repos"
    try:
        response = requests.get(url, proxies=hexss.proxies)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"{RED}Failed to fetch repos for '{username}'{END}: {e}")
        return None


if __name__ == '__main__':
    from pprint import pprint

    # clone_or_pull(r'C:\Users\c026730\Desktop\New folder (3)', 'https://github.com/hexs/play-manim.git')
