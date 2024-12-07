from hexss import json_load, proxies, check_packages

check_packages('requests', 'GitPython')

import requests
from git import Repo


def pull(path):
    repo = Repo(path)
    res = repo.git.pull('origin', 'main')
    print(res)


def push_if_status_change(path):
    repo = Repo(path)
    status = repo.git.status()
    print('status', status, '- -' * 30, sep='\n')
    if status.split('\n')[-1] != 'nothing to commit, working tree clean':
        res = repo.git.add('.')
        print('add', res, '- -' * 30, sep='\n')
        for v in status.split('\n'):
            if '	modified:   ' in v:
                print(v.split('	modified:   ')[-1])
                break
        else:
            v = ''
        res = repo.git.commit('-am', f'auto update {v.strip()}')
        print('commit', res, '- -' * 30, sep='\n')

        res = repo.git.push('origin', 'main')
        print('push', res, '- -' * 30, sep='\n')


def get_repositories(username):
    url = f"https://api.github.com/users/{username}/repos"

    if proxies is not None:
        response = requests.get(url, proxies=proxies)
    else:
        response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get repositories: {response.status_code} - {response.reason}")
