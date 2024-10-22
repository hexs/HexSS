from multiprocessing import Process, Manager
from hexss.multiprocessing.func import dict_to_manager_dict
import os
import signal


class Multicore:
    def __init__(self):
        self.processes = []
        self.manager = Manager()
        self.data = self.manager.dict()
        self.func_join = []

    def set_data(self, data: dict):
        self.data = dict_to_manager_dict(self.manager, data)

    def add_func(self, func, *args, join=True):
        self.processes.append(Process(target=func, args=(self.data, *args)))
        self.func_join.append(join)

    def start(self):
        for process in self.processes:
            process.start()

    def join(self):
        for i, process in enumerate(self.processes):
            if self.func_join[i]:
                process.join()

    def kill(self):
        os.kill(os.getpid(), signal.SIGINT)
