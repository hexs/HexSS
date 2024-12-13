from hexss import json_load, proxies, check_packages

# Ensure required packages are installed
check_packages('requests', 'GitPython')

import requests
from git import Repo


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
    except Exception as e:
        print(f"Error while pulling changes: {e}")


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
