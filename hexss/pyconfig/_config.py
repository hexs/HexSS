import re
import ast
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple, Union

from hexss.constants import *


class Config:
    def __init__(self, config_file: Union[Path, str] = "config.py") -> None:
        self._file = Path(config_file)
        self._data: Dict[str, Any] = {}
        if self._file.exists():
            self._load()
        else:
            self._save()

    def _load(self) -> None:
        namespace: Dict[str, Any] = {}
        code = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
        try:
            exec(code, namespace)
            self._data = {
                k: v for k, v in namespace.items()
                if not k.startswith("__") and not callable(v) and not isinstance(v, type)
            }
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")

    def _split_inline_comment(self, line: str) -> Tuple[str, str]:
        in_sq = in_dq = escape = False
        for i, ch in enumerate(line):
            if ch == "\\":
                escape = not escape
                continue
            if ch == "'" and not escape and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not escape and not in_sq:
                in_dq = not in_dq
            elif ch == "#" and not in_sq and not in_dq:
                return line[:i].rstrip(), line[i:]
            else:
                escape = False
        return line.rstrip(), ""

    def _format_value(self, value: Any, indent: str, key: str) -> str:
        def pad(n: int) -> str:
            return " " * (n * 4)

        def fmt(val: Any, level: int) -> List[str]:
            if isinstance(val, (str, int, float, bool, type(None))):
                return [repr(val)]
            if isinstance(val, set):
                if not val:
                    return ["set()"]
                try:
                    items = sorted(val)
                except TypeError:
                    items = sorted(val, key=lambda x: repr(x))
                lines = ["{"]
                for i, item in enumerate(items):
                    item_lines = fmt(item, level + 1)
                    lines.append(f"{pad(level + 1)}{item_lines[0]}")
                    if i != len(items) - 1:
                        lines[-1] += ","
                lines.append(f"{pad(level)}}}")
                return lines
            if isinstance(val, (list, tuple)):
                ob, cb = ("[", "]") if isinstance(val, list) else ("(", ")")
                if not val:
                    return [ob + cb]
                lines = [ob]
                for i, item in enumerate(val):
                    item_lines = fmt(item, level + 1)
                    lines.append(f"{pad(level + 1)}{item_lines[0]}")
                    lines.extend(item_lines[1:])
                    if i != len(val) - 1:
                        lines[-1] += ","
                lines.append(f"{pad(level)}{cb}")
                return lines
            if isinstance(val, dict):
                if not val:
                    return ["{}"]
                lines = ["{"]
                items = list(val.items())
                for i, (k, v) in enumerate(items):
                    v_lines = fmt(v, level + 1)
                    key_text = repr(k)
                    lines.append(f"{pad(level + 1)}{key_text}: {v_lines[0]}")
                    lines.extend(v_lines[1:])
                    if i != len(items) - 1:
                        lines[-1] += ","
                lines.append(f"{pad(level)}}}")
                return lines
            return [repr(val)]

        val_lines = fmt(value, level=0)
        if len(val_lines) == 1:
            return f"{indent}{key} = {val_lines[0]}"
        out = [f"{indent}{key} = {val_lines[0]}"]
        out.extend(f"{indent}{ln}" for ln in val_lines[1:])
        return "\n".join(out)

    def _save(self) -> None:
        src = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
        lines = src.splitlines()
        try:
            tree = ast.parse(src or "\n")
        except SyntaxError:
            text = "\n".join(f"{k} = {repr(v)}" for k, v in self._data.items())
            self._file.write_text(text, encoding="utf-8")
            return
        spans: Dict[str, Tuple[int, int, str]] = {}
        for node in tree.body:
            key = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                key = node.targets[0].id
            elif isinstance(node, ast.AnnAssign) and node.simple and isinstance(node.target, ast.Name):
                key = node.target.id
            if key and key in self._data:
                start = getattr(node, "lineno", 1) - 1
                end = getattr(node, "end_lineno", node.lineno) - 1
                indent = ""
                if 0 <= start < len(lines):
                    m = re.match(r"^(\s*)", lines[start])
                    indent = m.group(1) if m else ""
                spans[key] = (start, end, indent)
        out: List[str] = []
        i = 0
        seen = set()
        start_to_key = {start: k for k, (start, end, _) in spans.items()}
        while i < len(lines):
            if i in start_to_key:
                key = start_to_key[i]
                start, end, indent = spans[key]
                comment = ""
                if start == end:
                    _, cmt = self._split_inline_comment(lines[start])
                    comment = (" " + cmt) if cmt else ""
                block = self._format_value(self._data[key], indent, key)
                if comment and "\n" not in block:
                    block = block + comment
                out.append(block)
                seen.add(key)
                i = end + 1
            else:
                out.append(lines[i])
                i += 1
        missing = [k for k in self._data.keys() if k not in seen and k not in spans]
        for k in missing:
            out.append(self._format_value(self._data[k], indent="", key=k))
        self._file.write_text("\n".join(out), encoding="utf-8")

    def __getattr__(self, key: str) -> Any:
        if key in self._data:
            return self._data[key]
        raise AttributeError(f"No config key '{key}'")

    def __setattr__(self, key: str, value: Any) -> None:
        if key in {"_file", "_data"}:
            super().__setattr__(key, value)
        else:
            self._data[key] = value
            self._save()

    def _update(self, path: List[str], value: Any) -> None:
        target = self._data
        for key in path[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]
        target[path[-1]] = value
        self._save()

    def _pprint(self, head=None) -> None:
        if head:
            print(f'{CYAN}{head}{END}')
        print(end=f'{YELLOW}')
        pprint(self._data)
        print(f'{END}')


if __name__ == "__main__":
    config = Config("config.py")  # Will create if not present
    config._pprint('Initial config:')

    # Add or update top-level values
    config.ipv4 = "0.0.0.0"
    config.port = 5000
    config._pprint('After setting ipv4 and port:')

    # Set a list
    config.model_names = ['m1', 'm2']
    config._pprint('After setting model_names:')

    # Overwrite the list
    config.model_names = []
    config._pprint('After clearing model_names:')

    # Add to the list
    config.model_names = ['m1', 'm2']
    config.model_names.append("m3")  # modifies in place and auto-saves
    config._pprint('After appending to model_names:')

    # Work with nested dicts
    config.rects = {}
    config.rects["r1"] = {"x": 10, "y": 2}
    config.rects["r1"]["x"] = 15
    config._pprint('After creating rects and modifying r1:')

    # Auto-create nested dict keys
    config._update(["rects", "r2", "x"], 20)
    config._update(["rects", "r2", "y"], 60)
    config._pprint('After updating r2 in rects:')

    # Access attributes
    print("ipv4:", config.ipv4)
    print("port:", config.port)
    print("model_names:", config.model_names)
    print("rects:", config.rects)
