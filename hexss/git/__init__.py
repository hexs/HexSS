from pathlib import Path
from typing import Optional, Union, List
import os
import time
import fnmatch

import hexss
from hexss.constants import *

hexss.check_packages('requests', 'GitPython', auto_install=True)

import requests
from git import Repo, GitCommandError, InvalidGitRepositoryError, RemoteProgress


def _ensure_repo(path: Union[Path, str]) -> Repo:
    try:
        return Repo(path)
    except InvalidGitRepositoryError:
        raise RuntimeError(f"'{path}' is not a valid Git repository.")


def _git_safe(*segments: str) -> str:
    # Normalize path for Git/Windows
    return os.path.join(*segments).replace("\\", "/")


# ---------- Core ops ----------
def clone(path: Union[Path, str], url: str, branch: str = "main", timeout: Optional[int] = None) -> Repo:
    try:
        print(end=f"Cloning '{url}' into '{path}'...\n")
        repo = Repo.clone_from(url, path, branch=branch, single_branch=True, depth=1, timeout=timeout)
        print(end=f"✅ {GREEN}Successfully cloned{END} '{url}' to '{repo.working_dir}'.\n")
        return repo
    except GitCommandError as e:
        raise RuntimeError(f"{RED}Git clone failed{END}: {e.stderr.strip()}") from e
    except Exception as e:
        raise RuntimeError(f"{RED}Unexpected error during clone{END}: {e}") from e


def pull(path: Union[Path, str], branch: str = "main") -> str:
    repo = _ensure_repo(path)
    try:
        print(end=f"Pulling latest changes in '{repo.working_tree_dir}' (branch '{branch}')...\n")
        output = repo.git.pull("origin", branch)
        print(end=f"✅ {GREEN}Pull result{END}: {output}\n")
        return output
    except GitCommandError as e:
        raise RuntimeError(f"{RED}Git pull failed{END}: {e.stderr.strip()}") from e
    except Exception as e:
        raise RuntimeError(f"{RED}Unexpected error during pull{END}: {e}") from e


def clone_or_pull(path: Union[Path, str], url: Optional[str] = None, branch: str = "main") -> Union[Repo, str]:
    git_dir = os.path.join(path, ".git")
    if not os.path.isdir(git_dir):
        if not url:
            raise ValueError("URL is required to clone into an empty directory.")
        return clone(path, url, branch)
    return pull(path, branch)


def auto_pull(path: Union[Path, str], interval: int = 600, branch: str = "main") -> None:
    while True:
        try:
            pull(path, branch)
        except Exception as e:
            print(end=f"{RED}Auto-pull error{END}: {e}\n")
        time.sleep(interval)


def status(path: Union[Path, str], file_patterns: Optional[List[str]] = None, filter_codes: str = 'MADRCU') -> str:
    repo = _ensure_repo(path)
    status_lines = repo.git.status('--porcelain').splitlines()

    status_map = {
        "M": "modify",
        "A": "add",
        "D": "delete",
        "R": "rename",
        "C": "copy",
        "U": "update",
        "?": "untrack"
    }

    details = []
    for line in status_lines:
        if not line.strip():
            continue

        code = line[:2].strip()  # e.g. "M", "A", "??"
        file_path = line[3:].strip()  # after two status chars + space

        if not code:
            continue
        if code[0] not in filter_codes:
            continue

        if file_patterns:
            # Accept either wildcard match or directory prefix match
            if not any(
                    fnmatch.fnmatch(file_path, pat) or file_path.startswith(pat.rstrip("/") + "/")
                    for pat in file_patterns
            ):
                continue

        details.append(f"{status_map.get(code[0], code)} {file_path}")

    return ", ".join(details)


def add(path: Union[Path, str], file_patterns: Optional[List[str]] = None) -> None:
    """
    Prefer Git's pathspec handling (robust wildcards/dirs).
    """
    repo = _ensure_repo(path)
    root = repo.working_tree_dir

    if not file_patterns:
        repo.git.add(A=True)
        print(end="✅ Staged all changes.\n")
        return

    # Normalize: if it's a dir, make sure it ends with '/'
    normalized: List[str] = []
    for pat in file_patterns:
        full = _git_safe(root, pat)
        if os.path.isdir(full):
            d = pat.replace("\\", "/")
            if not d.endswith("/"):
                d += "/"
            normalized.append(d)
        else:
            normalized.append(pat)

    try:
        repo.git.add('--', *normalized)
    except GitCommandError as e:
        raise RuntimeError(f"{RED}git add failed{END}: {e.stderr.strip()}") from e

    staged = repo.git.diff('--cached', '--name-only').splitlines()
    if staged:
        print(end=f"✅ Staged files ({len(staged)}):\n")
        for f in staged:
            print("   ", f)
    else:
        print(end="⚠️ No matching files found to stage.\n")


def commit(path: Union[Path, str], message: Optional[str] = None) -> Optional[str]:
    """
    Commit staged changes if any. Returns commit hexsha or None if nothing staged.
    """
    repo = _ensure_repo(path)

    staged = repo.git.diff('--cached', '--name-only').splitlines()
    if not staged:
        print(end=f"{YELLOW}No staged changes to commit.{END}\n")
        return None

    msg = message or "Auto-commit"
    try:
        commit_obj = repo.index.commit(msg)
        print(end=f"📝 {PINK}Committed{END}: {msg}\n")
        print(end=f"🔗 {commit_obj.hexsha}\n")
        return commit_obj.hexsha
    except GitCommandError as e:
        raise RuntimeError(f"{RED}Git commit failed{END}: {e.stderr.strip()}") from e


def push(path: Union[Path, str], branch: str = "main", commit_message: Optional[str] = None) -> None:
    """
    Push current HEAD to origin/<branch>.
    - If commit_message is provided and there are staged changes, a commit is made before push.
    - If no upstream is set, set upstream to origin/<branch>.
    """
    repo = _ensure_repo(path)

    if commit_message is not None:
        _ = commit(path, commit_message)

    try:
        origin = repo.remote(name="origin")
    except ValueError:
        raise RuntimeError(f"{RED}No remote named 'origin'{END} is configured.")

    # Ensure/checkout the target branch
    try:
        if repo.head.is_detached:
            raise RuntimeError("HEAD is detached. Please attach HEAD to a branch before pushing.")

        if repo.active_branch.name != branch:
            if branch in repo.heads:
                repo.git.checkout(branch)
            else:
                repo.git.checkout('-b', branch)
    except Exception as e:
        raise RuntimeError(f"{RED}Unable to checkout branch '{branch}'{END}: {e}")

    # Push with upstream if needed
    try:
        if repo.active_branch.tracking_branch() is None:
            print(end=f"🔧 Setting upstream to origin/{branch}...\n")
            repo.git.push('--set-upstream', 'origin', branch)
        else:
            push_info = origin.push(branch)
            for info in push_info:
                if info.flags & info.ERROR:
                    raise RuntimeError(f"Push failed: {info.summary}")
    except GitCommandError as e:
        raise RuntimeError(f"{RED}Git push failed{END}: {e.stderr.strip()}") from e

    print(end=f"✅ {GREEN}Pushed to origin/{branch} successfully.{END}\n")


def push_if_dirty(path: Union[Path, str], file_patterns: Optional[List[str]] = None, branch: str = "main") -> None:
    add(path, file_patterns)
    s = status(path, file_patterns)
    push(path, branch=branch, commit_message=s if s else None)


def fetch_repositories(username: str) -> List[dict]:
    if not username:
        raise ValueError("GitHub username must be provided.")
    url = f"https://api.github.com/users/{username}/repos"
    try:
        response = requests.get(url, proxies=hexss.proxies)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(end=f"{RED}Failed to fetch repos for '{username}'{END}: {e}\n")
        return []


if __name__ == '__main__':
    from pprint import pprint

    pprint(list(r['name'] for r in fetch_repositories('hexs')))

    path = Path(r'Project/func')
    url = 'https://github.com/hexs/func.git'
    # url = 'git@github.com/hexs/func.git' # SSH
    clone_or_pull(path, url)
    push_if_dirty(path, ['img/*', '*.txt'])

    repo_path = r'C:\PythonProjects\auto_inspection_data__QC7-2413'
    pats = [
        'img_full/',
        'img_frame_log/',
        'model/',
        '*.json',
        '.gitignore',
    ]

    add(repo_path, pats)
    s = status(repo_path, pats)
    print(s)
    push(repo_path, branch='main', commit_message=s if s else None)
