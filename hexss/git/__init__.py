import time
import hexss

hexss.check_packages('requests', 'GitPython', auto_install=True)

from hexss import json_load, proxies
import requests
from git import Repo


def clone(path=".", url=None):
    """
    Clone a Git repository from the specified URL to the given path.

    Args:
        url (str): The URL of the Git repository to clone.
        path (str): The local directory where the repository should be cloned. Defaults to the current directory.

    Returns:
        str: The path to the cloned repository if successful.

    Raises:
        Exception: If the cloning operation fails for any reason.
    """

    try:
        print(f"Cloning repository from {url} into {path}...")
        # Clone the repository
        repo = Repo.clone_from(url, path)
        print(f"Repository successfully cloned to: {repo.working_dir}")
        return repo.working_dir
    except Exception as e:
        raise Exception(f"Error occurred while cloning the repository: {e}")


def pull(path):
    """
    Pull the latest changes from the origin/main branch of the Git repository at the given path.

    Args:
        path (str): The path to the Git repository.

    Raises:
        Exception: If the repository cannot be accessed or pull operation fails.
    """
    try:
        repo = Repo(path)
        res = repo.git.pull('origin', 'main')
        print(res)
        return res
    except Exception as e:
        print(f"Error while pulling changes: {e}")


def pull_loop(path):
    while pull(path) is None:
        time.sleep(10)


def push_if_status_change(path):
    """
    Push changes to the origin/main branch if there are modifications in the repository at the given path.

    Args:
        path (str): The path to the Git repository.

    Raises:
        Exception: If the repository operation fails.
    """
    try:
        repo = Repo(path)
        status = repo.git.status()
        print('status', status, '- -' * 30, sep='\n')

        if status.split('\n')[-1] != 'nothing to commit, working tree clean':
            # Stage all changes
            res = repo.git.add('.')
            print('add', res, '- -' * 30, sep='\n')

            # Get the file name of the first modified file
            modified_file = ''
            for line in status.split('\n'):
                if '	modified:   ' in line:
                    modified_file = line.split('	modified:   ')[-1]
                    break

            # Commit the changes
            res = repo.git.commit('-am', f'auto update {modified_file.strip()}')
            print('commit', res, '- -' * 30, sep='\n')

            # Push the changes to origin/main
            res = repo.git.push('origin', 'main')
            print('push', res, '- -' * 30, sep='\n')
        else:
            print("No changes to push. Working tree is clean.")
    except Exception as e:
        print(f"Error while pushing changes: {e}")


def get_repositories(username):
    """
    Fetch public repositories of a GitHub user.

    Args:
        username (str): The GitHub username.

    Returns:
        list: A list of repositories (in JSON format) if successful, None otherwise.

    Raises:
        Exception: If the API request or JSON parsing fails.
    """
    url = f"https://api.github.com/users/{username}/repos"

    try:
        # Use proxies if available
        if proxies:
            response = requests.get(url, proxies=proxies)
        else:
            response = requests.get(url)

        # Handle the response
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get repositories: {response.status_code} - {response.reason}")
    except Exception as e:
        print(f"Error while fetching repositories: {e}")
        return None
