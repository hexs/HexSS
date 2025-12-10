import json
import re
import ast
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple, Union, Iterable

from hexss.constants import *


class _SaveMixin:
    def __init__(self, _cb):
        super().__init__()
        object.__setattr__(self, "_cb", _cb)

    def _touch(self):
        cb = object.__getattribute__(self, "_cb")
        if cb:
            cb()


class SaveList(list, _SaveMixin):
    def __init__(self, it: Iterable = (), _cb=None):
        list.__init__(self, it)
        _SaveMixin.__init__(self, _cb)

    def append(self, *a): r = super().append(*a); self._touch(); return r

    def extend(self, *a): r = super().extend(*a); self._touch(); return r

    def insert(self, *a): r = super().insert(*a); self._touch(); return r

    def remove(self, *a): r = super().remove(*a); self._touch(); return r

    def pop(self, *a):    r = super().pop(*a);    self._touch(); return r

    def clear(self):      r = super().clear();    self._touch(); return r

    def sort(self, *a, **k): r = super().sort(*a, **k); self._touch(); return r

    def reverse(self):    r = super().reverse();  self._touch(); return r

    def __setitem__(self, *a): r = super().__setitem__(*a); self._touch(); return r

    def __delitem__(self, *a): r = super().__delitem__(*a); self._touch(); return r

    def __iadd__(self, other): r = super().__iadd__(other); self._touch(); return r

    def __imul__(self, other): r = super().__imul__(other); self._touch(); return r


class SaveDict(dict, _SaveMixin):
    def __init__(self, m: Dict = None, _cb=None):
        dict.__init__(self, {} if m is None else m)
        _SaveMixin.__init__(self, _cb)

    def __setitem__(self, *a): r = super().__setitem__(*a); self._touch(); return r

    def __delitem__(self, *a): r = super().__delitem__(*a); self._touch(); return r

    def clear(self):      r = super().clear();    self._touch(); return r

    def pop(self, *a):    r = super().pop(*a);    self._touch(); return r

    def popitem(self):    r = super().popitem();  self._touch(); return r

    def setdefault(self, *a): r = super().setdefault(*a); self._touch(); return r

    def update(self, *a, **k): r = super().update(*a, **k); self._touch(); return r


class SaveSet(set, _SaveMixin):
    def __init__(self, it: Iterable = (), _cb=None):
        set.__init__(self, it)
        _SaveMixin.__init__(self, _cb)

    def add(self, *a):    r = super().add(*a);    self._touch(); return r

    def remove(self, *a): r = super().remove(*a); self._touch(); return r

    def discard(self, *a): r = super().discard(*a);self._touch(); return r

    def pop(self):        r = super().pop();      self._touch(); return r

    def clear(self):      r = super().clear();    self._touch(); return r

    def update(self, *a): r = super().update(*a); self._touch(); return r

    def difference_update(self, *a): r = super().difference_update(*a); self._touch(); return r

    def intersection_update(self, *a): r = super().intersection_update(*a); self._touch(); return r

    def symmetric_difference_update(self, *a): r = super().symmetric_difference_update(*a); self._touch(); return r


def _wrap_mutables(obj: Any, touch_cb) -> Any:
    if isinstance(obj, list):
        return SaveList([_wrap_mutables(v, touch_cb) for v in obj], _cb=touch_cb)
    if isinstance(obj, dict):
        return SaveDict({k: _wrap_mutables(v, touch_cb) for k, v in obj.items()}, _cb=touch_cb)
    if isinstance(obj, set):
        return SaveSet({_wrap_mutables(v, touch_cb) for v in obj}, _cb=touch_cb)
    return obj


class Config:
    def __init__(self, config_file: Union[Path, str] = "cfg.py", default_text: str = "") -> None:
        self._file = Path(config_file)
        self._data: Dict[str, Any] = {}
        if self._file.exists():
            self._load()
        else:
            self._file.parent.mkdir(exist_ok=True)
            self._file.write_text(default_text)
            self._save()

    def __repr__(self) -> str:
        return json.dumps(self._data, indent=4)

    def _load(self) -> None:
        code = self._file.read_text(encoding="utf-8") if self._file.exists() else ""

        def _exec_with_ns() -> Dict[str, Any]:
            ns: Dict[str, Any] = {"__file__": str(self._file), "__name__": "__config__"}
            exec(code, ns)
            return ns

        try:
            namespace = _exec_with_ns()
        except FileNotFoundError as e:
            missing = Path(e.filename) if getattr(e, "filename", None) else None
            if missing and (self._file.parent in missing.parents or missing.parent == self._file.parent):
                try:
                    missing.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                namespace = _exec_with_ns()
            else:
                raise RuntimeError(f"Failed to load config: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}") from e

        import types as _types
        def is_literal(x: Any) -> bool:
            if isinstance(x, _types.ModuleType): return False
            if isinstance(x, (_types.FunctionType, _types.BuiltinFunctionType, _types.MethodType)): return False
            if isinstance(x, type): return False
            if isinstance(x, (str, int, float, bool, type(None))): return True
            if isinstance(x, (list, tuple, set)): return all(is_literal(i) for i in x)
            if isinstance(x, dict): return all(
                isinstance(k, (str, int, float, bool)) and is_literal(v) for k, v in x.items())
            return False

        raw = {k: v for k, v in namespace.items() if not k.startswith("__") and is_literal(v)}
        self._data = _wrap_mutables(raw, self._save)

    def _split_inline_comment(self, line: str) -> Tuple[str, str]:
        in_sq = in_dq = escape = False
        for i, ch in enumerate(line):
            if ch == "\\": escape = not escape; continue
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

        def unwrap(val: Any) -> Any:
            if isinstance(val, SaveList): return [unwrap(x) for x in list(val)]
            if isinstance(val, SaveDict): return {k: unwrap(v) for k, v in dict(val).items()}
            if isinstance(val, SaveSet):  return set(unwrap(x) for x in set(val))
            return val

        def fmt(val: Any, level: int) -> List[str]:
            val = unwrap(val)
            if isinstance(val, (str, int, float, bool, type(None))):
                return [repr(val)]
            if isinstance(val, set):
                if not val: return ["set()"]
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

        new_src = "\n".join(out)
        if not new_src.endswith("\n"):
            new_src += "\n"
        self._file.write_text(new_src, encoding="utf-8")

    def _get_assigned_object(self, name: str) -> Any:
        src = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
        try:
            tree = ast.parse(src or "\n")
        except SyntaxError as e:
            raise KeyError(name) from e

        assigned = False
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if (
                        len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id == name
                ):
                    assigned = True
                    break
            elif (
                    isinstance(node, ast.AnnAssign)
                    and node.simple
                    and isinstance(node.target, ast.Name)
                    and node.target.id == name
            ):
                assigned = True
                break
        if not assigned:
            raise KeyError(name)

        def _exec_with_ns() -> Dict[str, Any]:
            ns: Dict[str, Any] = {"__file__": str(self._file), "__name__": "__config__"}
            exec(src, ns)
            return ns

        try:
            ns = _exec_with_ns()
        except FileNotFoundError as e:
            missing = Path(e.filename) if getattr(e, "filename", None) else None
            if missing and (self._file.parent in missing.parents or missing.parent == self._file.parent):
                try:
                    missing.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                ns = _exec_with_ns()
            else:
                raise KeyError(name) from e

        if name not in ns:
            raise KeyError(name)
        return ns[name]

    def __getattr__(self, key: str) -> Any:
        if key in self._data:
            return self._data[key]
        try:
            return self._get_assigned_object(key)
        except KeyError:
            return None

    def __setattr__(self, key: str, value: Any) -> None:
        if key in {"_file", "_data"}:
            super().__setattr__(key, value)
        else:
            if key[0] == '_':
                print(f"{YELLOW}Warning: {key}, You shouldn't start with '_'{END}")
            self._data[key] = _wrap_mutables(value, self._save)
            self._save()

    def _update(self, path: List[str], value: Any) -> None:
        target = self._data
        for key in path[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = SaveDict({}, _cb=self._save)
            target = target[key]
        target[path[-1]] = _wrap_mutables(value, self._save)
        self._save()

    def _pprint(self, head=None) -> None:
        if head: print(f"{BLUE}{head}{END}")
        print(end=f"{CYAN}")
        pprint(self._data)
        print(f"{END}")

    def _ensure_import(self, *imports_or_modules: str) -> None:
        src = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
        lines = src.splitlines()

        normalized_inputs: List[str] = []
        for raw in imports_or_modules:
            raw = (raw or "").strip()
            if not raw: continue
            low = raw.lstrip().lower()
            if low.startswith("import ") or low.startswith("from "):
                normalized_inputs.append(raw)
            else:
                parts = [p.strip() for p in raw.split(",") if p.strip()]
                for p in parts: normalized_inputs.append(f"import {p}")

        try:
            tree = ast.parse(src or "\n")
        except SyntaxError:
            head = "\n".join(s for s in normalized_inputs if s)
            new_src = (head + ("\n" if head else "") + src).lstrip("\n")
            self._file.write_text(new_src, encoding="utf-8")
            try:
                self._load()
            except Exception:
                pass
            return

        import_nodes: List[ast.AST] = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]

        def canon(node: ast.AST):
            if isinstance(node, ast.Import):
                return ("import", tuple((n.name, n.asname) for n in node.names))
            if isinstance(node, ast.ImportFrom):
                return ("from", node.module, node.level, tuple((n.name, n.asname) for n in node.names))
            return None

        from_index: Dict[Tuple[str, int], List[ast.ImportFrom]] = {}
        import_index: Dict[str, ast.alias] = {}
        for node in import_nodes:
            if isinstance(node, ast.ImportFrom):
                key = (node.module or "", node.level or 0)
                from_index.setdefault(key, []).append(node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    import_index[alias.name] = alias

        def find_insert_at() -> int:
            i = 0
            if i < len(lines) and lines[i].startswith("#!"): i += 1
            if i < len(lines) and re.match(r"^\s*#.*coding[:=]\s*[-\w.]+", lines[i]): i += 1
            if i < len(lines) and lines[i].lstrip().startswith(('"""', "'''")):
                q = lines[i].lstrip()[:3]
                i += 1
                while i < len(lines):
                    if lines[i].rstrip().endswith(q): i += 1; break
                    i += 1
            while i < len(lines) and lines[i].strip() == "": i += 1
            last = i - 1
            j = i
            while j < len(lines):
                s = lines[j].strip()
                if s.startswith("import ") or s.startswith("from "): last = j; j += 1; continue
                if s == "" or s.startswith("#"): j += 1; continue
                break
            return last + 1

        insert_at = find_insert_at()

        missing_lines: List[str] = []
        merged_edits: List[Tuple[ast.ImportFrom, List[ast.alias]]] = []

        for text in normalized_inputs:
            try:
                mod = ast.parse(text + ("\n" if not text.endswith("\n") else ""))
            except SyntaxError:
                if text not in src: missing_lines.append(text)
                continue
            if len(mod.body) != 1 or not isinstance(mod.body[0], (ast.Import, ast.ImportFrom)):
                if text not in src: missing_lines.append(text)
                continue

            req = mod.body[0]
            if isinstance(req, ast.Import):
                exists = any(isinstance(n, ast.Import) and canon(n) == canon(req) for n in import_nodes)
                if not exists:
                    for a in req.names:
                        if a.name in import_index:
                            exists = True
                            break
                if not exists:
                    missing_lines.append(text.strip())
                continue

            if isinstance(req, ast.ImportFrom):
                key = (req.module or "", req.level or 0)
                if key in from_index and from_index[key]:
                    tgt = from_index[key][0]
                    existing_map = {(a.name, a.asname): a for a in tgt.names}
                    new_aliases: List[ast.alias] = []
                    for a in req.names:
                        if (a.name, a.asname) not in existing_map:
                            clash = any(a.name == b.name for b in tgt.names)
                            if not clash: new_aliases.append(a)
                    if new_aliases:
                        merged_edits.append((tgt, new_aliases))
                else:
                    missing_lines.append(text.strip())

        if merged_edits:
            line_edits: List[Tuple[int, int, str]] = []
            for tgt, adds in merged_edits:
                s = tgt.lineno - 1
                e = getattr(tgt, "end_lineno", tgt.lineno) - 1
                original = lines[s:e + 1]
                tail = "".join(original).split("import", 1)[1].strip()
                add_txt = ", ".join(f"{a.name} as {a.asname}" if a.asname else a.name for a in adds)
                if tail.endswith(")"):
                    joined = "\n".join(original)
                    idx = joined.rfind(")")
                    before, after = joined[:idx], joined[idx:]
                    comma = "" if before.rstrip().endswith(("(", ",")) else ","
                    replacement = before + f"{comma} {add_txt}" + after
                    line_edits.append((s, e, replacement))
                else:
                    comma = "" if tail.strip() == "" else ","
                    replacement = f"from {tgt.module or ''} import {tail}{comma} {add_txt}".rstrip()
                    line_edits.append((s, e, replacement))

            for s, e, rep in sorted(line_edits, key=lambda x: x[0], reverse=True):
                new_chunk = rep.splitlines()
                lines[s:e + 1] = new_chunk

        if missing_lines:
            pre_blank = insert_at > 0 and lines[insert_at - 1].strip() != ""
            post_blank = insert_at < len(lines) and lines[insert_at].strip() != ""
            to_insert = []
            if pre_blank: to_insert.append("")
            to_insert.extend(missing_lines)
            if post_blank: to_insert.append("")
            lines[insert_at:insert_at] = to_insert

        new_src = "\n".join(lines)
        if not new_src.endswith("\n"): new_src += "\n"
        self._file.write_text(new_src, encoding="utf-8")
        try:
            self._load()
        except Exception:
            pass

    def _update_block(self, name: str, code: str) -> None:
        import textwrap
        src = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
        lines = src.splitlines()
        code = textwrap.dedent(code).strip()

        def needs_wrap(name: str, snippet: str) -> bool:
            try:
                mod = ast.parse(snippet or "\n")
            except SyntaxError:
                return True
            if len(mod.body) != 1: return True
            node = mod.body[0]
            if isinstance(node, ast.Assign):
                return not (
                        len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id == name
                )
            if (
                    isinstance(node, ast.AnnAssign)
                    and node.simple
                    and isinstance(node.target, ast.Name)
            ):
                return node.target.id != name
            return True

        block = f"{name} = {code}" if needs_wrap(name, code) else code
        if not block.endswith("\n"): block += "\n"

        try:
            tree = ast.parse(src or "\n")
        except SyntaxError:
            new_src = src.rstrip() + ("\n\n" if src.strip() else "") + block
            self._file.write_text(new_src, encoding="utf-8")
            try:
                self._load()
            except Exception:
                pass
            return

        target_span = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
                    target_span = (node.lineno - 1, getattr(node, "end_lineno", node.lineno) - 1)
                    break
            elif (
                    isinstance(node, ast.AnnAssign)
                    and node.simple
                    and isinstance(node.target, ast.Name)
                    and node.target.id == name
            ):
                target_span = (node.lineno - 1, getattr(node, "end_lineno", node.lineno) - 1)
                break

        if target_span:
            s, e = target_span
            lines[s:e + 1] = block.splitlines()
        else:
            if lines and lines[-1].strip() != "": lines.append("")
            lines.extend(block.splitlines())

        new_src = "\n".join(lines)
        if not new_src.endswith("\n"): new_src += "\n"
        self._file.write_text(new_src, encoding="utf-8")
        try:
            self._load()
        except Exception:
            pass


if __name__ == '__main__':
    from pathlib import Path
    from hexss.pyconfig import Config

    # Point Config to your target file
    cfg = Config("my_project/config.py")

    # (int, float, complex, str, bytes, bool)
    cfg.x = 1
    cfg.y = 2.06
    cfg.z = 3 + 2j
    cfg.a = 'abc'
    cfg.b = b'abc'
    cfg.c = True

    # (Lists, Dicts, Sets)
    # Initialize a list and a dict
    cfg.users = ["alice", "bob"]
    cfg.settings = {"theme": "dark", "retries": 3}

    # Modify in-place (Triggers auto-save)
    cfg.users.append("charlie")
    cfg.settings["theme"] = "light"

    # Even nested modifications work
    cfg.nested = {"a": [1, 2]}
    cfg.nested["a"].append(3)

    # Make sure imports you’ll need exist (idempotent; merges nicely)
    cfg._ensure_import(
        "from keras import Sequential, layers",
        "from pathlib import Path",
        "os, sys, json",
        "from typing import Dict, List",
        "from typing import Optional as Opt",  # merges into any existing typing line
    )

    # Set simple values (auto-saves on assignment)
    cfg.ipv4 = "0.0.0.0"
    cfg.port = 5000
    cfg.img_size = [100, 100]
    cfg.epochs = 100
    cfg.batch_size = 64
    cfg.validation_split = 0.2
    cfg.seed = 456

    # Set derived paths and a computed list via _update_block (RHS or full assignment)
    cfg._update_block("datasets_path", "Path(__file__).parent / 'datasets'")
    cfg._update_block("model_path", "Path(__file__).parent / 'model'")
    cfg._update_block("class_names", "[p.name for p in datasets_path.iterdir() if p.is_dir()]")
    # If datasets/ doesn’t exist yet, it’ll be created on first execution (during load) and retried.

    # Add/update your Keras model using just the RHS (will wrap as `model = ...`)
    cfg._update_block("model", """
            Sequential([
                layers.Rescaling(1./255, input_shape=(*img_size, 3)),
                layers.Conv2D(16, 3, padding='same', activation='relu'),
                layers.MaxPooling2D(),
                layers.Conv2D(32, 3, padding='same', activation='relu'),
                layers.MaxPooling2D(),
                layers.Conv2D(64, 3, padding='same', activation='relu'),
                layers.MaxPooling2D(),
                layers.Flatten(),
                layers.Dense(128, activation='relu'),
                layers.Dense(len(class_names))
            ])
        """)

    # Read back values
    print("ipv4:", cfg.ipv4)  # from literals cache
    print("port:", cfg.port)
    print("img_size:", cfg.img_size)
    print("class_names (lazy):", cfg.class_names)  # computed in file, read via execution
    print("model object:", type(cfg.model))  # built object (Sequential)

    # Optional: If Keras is available, you can do a summary:
    cfg.model.build(input_shape=(None, cfg.img_size[0], cfg.img_size[1], 3))
    cfg.model.summary()

    # In-place mutations auto-save (thanks to SaveList/SaveDict/SaveSet wrappers)
    cfg.model_names = ["m1", "m2"]
    cfg.model_names.append("m3")  # triggers auto-save without reassigning
    print("model_names:", cfg.model_names)

    # Nested updates that auto-create parents and save
    cfg._update(["rects", "r1", "x"], 15)
    cfg._update(["rects", "r1", "y"], 2)
    cfg._update(["rects", "r2", "x"], 20)
    cfg._update(["rects", "r2", "y"], 60)
    print("rects:", cfg.rects)

    # Pretty print the literal store (_data)
    cfg._pprint("Current literal config (_data):")
