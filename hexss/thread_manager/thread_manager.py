import threading
import inspect
from typing import Callable, Tuple, Dict, List, Any, Optional


class ThreadManager:
    def __init__(self):
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._results: Dict[str, Any] = {}
        self._errors: Dict[str, Exception] = {}
        self._statuses: Dict[str, str] = {}
        self._joinable: Dict[str, bool] = {}
        self._task_configs: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def add_task(self, target: Callable, args: Tuple = (), kwargs: Optional[Dict[str, Any]] = None, daemon: bool = True,
                 join: bool = True, task_id: Optional[str] = None) -> str:
        if not callable(target): raise ValueError("Target must be callable.")
        t_id = task_id or target.__name__
        with self._lock:
            if t_id in self._task_configs: raise KeyError(f"Task ID '{t_id}' exists.")
            self._task_configs[t_id] = {
                'target': target, 'args': args, 'kwargs': kwargs or {}, 'daemon': daemon, 'join': join
            }
        self._setup_thread(t_id)
        return t_id

    def _setup_thread(self, t_id: str):
        config = self._task_configs[t_id]
        stop_event = threading.Event()
        kw = config['kwargs'].copy()

        sig = inspect.signature(config['target'])
        has_stop_event = 'stop_event' in sig.parameters
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if has_stop_event or has_kwargs:
            kw['stop_event'] = stop_event

        def _task_wrapper(*a, **k):
            with self._lock:
                self._statuses[t_id] = "Running"
            try:
                result = config['target'](*a, **k)
                with self._lock:
                    self._results[t_id] = result
                    self._statuses[t_id] = "Stopped" if stop_event.is_set() else "Completed"
            except Exception as e:
                with self._lock:
                    self._errors[t_id] = e
                    self._statuses[t_id] = "Failed"

        thread = threading.Thread(
            target=_task_wrapper, args=config['args'], kwargs=kw, daemon=config['daemon'], name=t_id
        )
        with self._lock:
            self._threads[t_id] = thread
            self._stop_events[t_id] = stop_event
            self._statuses[t_id] = "Pending"
            self._joinable[t_id] = config['join']
            self._results.pop(t_id, None)
            self._errors.pop(t_id, None)

    def stop_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._stop_events and self._statuses.get(task_id) == "Running":
                self._stop_events[task_id].set()
                return True
        return False

    def restart_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id not in self._task_configs or self._statuses.get(task_id) in ("Running", "Pending"): return False
        self._setup_thread(task_id)
        with self._lock: self._threads[task_id].start()
        return True

    def start_all(self) -> None:
        with self._lock: pending = [t for t_id, t in self._threads.items() if self._statuses.get(t_id) == "Pending"]
        for thread in pending: thread.start()

    def join_all(self) -> None:
        while True:
            with self._lock:
                joining = [t for t_id, t in self._threads.items() if self._joinable.get(t_id, True) and t.is_alive()]

            if not joining:
                break

            for thread in joining:
                thread.join(timeout=0.5)

    def get_status(self) -> List[dict]:
        with self._lock:
            return [{
                "task_id": tid,
                "status": self._statuses.get(tid),
                "result": self._results.get(tid),
                "error": str(self._errors.get(tid)) if tid in self._errors else None,
                "joinable": self._joinable.get(tid)
            } for tid in self._task_configs.keys()]

    def start_monitor_server(self, ip: str = '0.0.0.0', port: int = 2000) -> None:
        from .app import run_server
        monitor_thread = threading.Thread(
            target=run_server,
            args=(self, ip, port),
            daemon=True,
            name="MonitorServer"
        )
        monitor_thread.start()
