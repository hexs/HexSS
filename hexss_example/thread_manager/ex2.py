import time
from hexss.thread_manager import ThreadManager
import random


def task1(data):
    while data.get('play'):
        print('Task 1, random number\n', end='')
        data['number'] = random.randint(0, 99)
        time.sleep(1)


def task2(data):
    while data.get('play'):
        print(f"Task 2, show number; number = {data.get('number')}\n", end='')
        time.sleep(1)


def main():
    m = ThreadManager()
    data = {
        'play': True,
        'number': 0,
    }

    m.add_task(task1, args=(data,), task_id="Random Number")
    m.add_task(task2, args=(data,), task_id="Show Number")

    m.start_all()
    try:
        while data['play']:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        data['play'] = False
        m.join_all()


if __name__ == '__main__':
    main()
