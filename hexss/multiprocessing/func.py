from typing import Any, Dict, List, Union
import multiprocessing

ManagerType = Union[Dict[Any, Any], List[Any]]


def list_to_manager_list(manager: multiprocessing.Manager, l: List[Any]) -> List[Any]:
    """Recursively convert a list to a manager.list()."""
    return manager.list([
        dict_to_manager_dict(manager, item) if isinstance(item, (dict, list)) else item
        for item in l
    ])


def dict_to_manager_dict(manager: multiprocessing.Manager, d: ManagerType) -> ManagerType:
    """Recursively convert a nested dictionary or list to a manager.dict() or manager.list()."""
    if isinstance(d, dict):
        return manager.dict({
            k: dict_to_manager_dict(manager, v) if isinstance(v, (dict, list)) else v
            for k, v in d.items()
        })
    elif isinstance(d, list):
        return list_to_manager_list(manager, d)
    else:
        return d


if __name__ == "__main__":
    multiprocessing.freeze_support()
    manager = multiprocessing.Manager()

    config = {
        "ipv4_address": "auto",
        "camera": [
            {
                "width": 640,
                "height": 480,
            },
            {
                "width": 640,
                "height": 480,
            },
        ]
    }

    data = dict_to_manager_dict(manager, config)

    print(data)
    print(type(data))
    print()
    print(data["camera"])
    print(type(data["camera"]))
    print()
    print(data["camera"][0])
    print(type(data["camera"][0]))
