import time
from hexss.constants import RED, BLUE, ENDC
from hexss.multiprocessing import Multicore


def func1(data):
    while True:
        data['func1'] = data.get('func1', 0) + 1
        data['list'].append(data['func1'])
        if len(data['list']) > 20:
            data['list'] = data['list'][:20]
        print(f'{RED}{data["func1"]} {data['list']}{ENDC}')
        time.sleep(1)


def func2(data):
    while True:
        data['func2'] = data.get('func2', 0) + 1
        print(f'{BLUE}{data["func2"]}{ENDC}')
        time.sleep(2)


if __name__ == '__main__':
    m = Multicore()
    m.set_data({
        'func1': -50,
        'func2': -50,
        'list': []
    })
    m.add_func(func1)
    m.add_func(func2)
    m.start()
    m.join()
