from pprint import pprint

from hexss.git import fetch_repositories

pprint(list(r['name'] for r in fetch_repositories('hexs')))
