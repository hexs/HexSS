from hexss import json_load, json_update
from hexss.constants import cml

data = json_load("example.json", {'value': 1})
json_update("example.json", data)
print(cml.BLUE, data, cml.ENDC, sep='')
