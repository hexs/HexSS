from pathlib import Path

from hexss.git import clone_or_pull, push_if_dirty

path = Path(r'Project/func')
url = 'https://github.com/hexs/func.git'
# url = 'git@github.com/hexs/func.git' # SSH
clone_or_pull(path, url)
push_if_dirty(path, ['img/*', '*.txt'])