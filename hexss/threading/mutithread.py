import threading


class Multithread:
    def __init__(self):
        self.threads = []
        self.lock = threading.Lock()

    def add_func(self, target, args=(), join=True, name=None):
        thread = threading.Thread(target=target, args=args, daemon=True, name=name)
        self.threads.append((join, thread))

    def start(self):
        for _, thread in self.threads:
            thread.start()

    def join(self):
        for join, thread in self.threads:
            if join:
                thread.join()

    def get_status(self):
        with self.lock:
            status = []
            for join, thread in self.threads:
                status.append({
                    'name': thread.name or str(thread.ident),
                    'status': "Running" if thread.is_alive() else "Stopped",
                    'join': "Will join" if join else "Won't join"
                })
            return status
