from pathlib import Path

from hexss import git

# repo_path = Path(r'C:\PythonProjects\auto_inspection_data__4A3-5526')
repo_path = Path(r'auto_inspection_data__4A3-5526')

git.clone_or_pull(repo_path, 'git@github.com:hexs/auto_inspection_data__4A3-5526.git')

pats = [
    Path('img_full/'),
    Path('img_frame_log/'),
    Path('model/'),
    Path('*.json'),
    Path('.gitignore'),
]

git.add(repo_path, pats)

msg = git.status(repo_path)
print(msg)

git.commit(repo_path, msg)

# git.push(repo_path)
