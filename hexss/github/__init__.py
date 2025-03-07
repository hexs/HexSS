import hexss

hexss.check_packages('requests', 'tqdm', auto_install=True)

from .download import download
