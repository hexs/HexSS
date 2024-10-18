from hexss import json_load, json_update
from hexss.constants import cml

data = json_load("json_example.json", {'value': 1}, True)
print(cml.BLUE, data, cml.ENDC, sep='')
