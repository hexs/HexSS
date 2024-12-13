import threading
from typing import Callable, Tuple, List, Optional


class Multithread:
    """
    A utility class for managing and handling multiple threads with convenience.
    """

    def __init__(self):
        """
        Initialize the Multithread manager with an empty list of threads
        and a lock for thread-safe operations.
        """
        self.threads = []  # Stores tuples of (join_required: bool, thread: threading.Thread)
        self.lock = threading.Lock()  # A lock for thread-safe access to threads' data

    def add_func(
            self,
            target: Callable,
            args: Tuple = (),
            join: bool = True,
            name: Optional[str] = None
    ) -> None:
        """
        Add a function as a thread to the thread manager.

        Args:
            target (Callable): The target function to run in a new thread.
            args (Tuple): The arguments to pass to the target function. Defaults to ().
            join (bool): Whether to join this thread during the `join()` call. Defaults to True.
            name (Optional[str]): An optional name for the thread. Defaults to None.
        """
        if not callable(target):
            raise ValueError("Target must be a callable function or method.")
        thread = threading.Thread(target=target, args=args, daemon=True, name=name)
        with self.lock:
            self.threads.append((join, thread))

    def start(self) -> None:
        """
        Start all threads added to the manager.
        """
        with self.lock:
            for _, thread in self.threads:
                thread.start()

    def join(self) -> None:
        """
        Join all threads that were marked for joining.
        """
        with self.lock:
            for join, thread in self.threads:
                if join:
                    thread.join()

    def get_status(self) -> List[dict]:
        """
        Retrieve the status of all managed threads.

        Returns:
            List[dict]: A list of dicts containing the status of each thread.
                        Each dict has 'name', 'status', and 'join' keys.
        """
        with self.lock:
            status = []
            for join, thread in self.threads:
                status.append({
                    "name": thread.name or f"Thread-{thread.ident}",
                    "status": "Running" if thread.is_alive() else "Stopped",
                    "join": "Will join" if join else "Won't join",
                })
            return status

if __name__ == '__main__':
    import time


    def task(duration, name):
        print(f"{name}: Starting")
        time.sleep(duration)
        print(f"{name}: Finished")


    if __name__ == "__main__":
        manager = Multithread()

        # Adding tasks as threads
        manager.add_func(target=task, args=(2, "Task 1"), name="Task-1")
        manager.add_func(target=task, args=(1, "Task 2"), join=False, name="Task-2")
        manager.add_func(target=task, args=(3, "Task 3"), name="Task-3")

        # Starting all threads
        print("Starting threads...")
        manager.start()

        # Checking thread status
        print("Thread statuses after start:")
        print(manager.get_status())

        # Joining threads marked for joining
        manager.join()

        # Checking thread status after join
        print("Thread statuses after join:")
        print(manager.get_status())
