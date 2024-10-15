from multiprocessing import Process, Manager
from hexss.multiprocessing.func import dict_to_manager_dict


class Multicore:
    def __init__(self):
        self.processes = []
        self.manager = Manager()
        self.data = self.manager.dict()

    def set_data(self, data: dict):
        self.data = dict_to_manager_dict(self.manager, data)

    def add_func(self, func):
        self.processes.append(Process(target=func, args=(self.data,)))

    def start(self):
        for process in self.processes:
            process.start()

    def join(self):
        for process in self.processes:
            process.join()
