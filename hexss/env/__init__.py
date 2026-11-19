r"""
Cross-platform (Windows / Linux) environment variable manager.

Quick tour:
    from env import env, Scope

    env.set("MY_VAR", "hello")                                    # this process only (temporary)
    env.set("MY_VAR", "hello", persist=True)                      # permanent, USER scope
    env.set("MY_VAR", "hello", persist=True, scope=Scope.SYSTEM)  # permanent, SYSTEM scope (admin/root)
    env.get("MY_VAR")                                             # read from this process
    env.get("MY_VAR", persist=True, scope=Scope.USER)             # read the stored (permanent) value
    env.unset("MY_VAR", persist=True)
    env.reload()                                                  # pull stored values into this process

    # PATH is a list, so it has its own add / remove API
    env.path.add(r"C:\tools")                                     # this process only, appended
    env.path.add(r"C:\tools", first=True)                         # put at the front (highest priority)
    env.path.add(r"C:\tools", persist=True)                       # permanent, USER scope
    env.path.remove(r"C:\tools", persist=True, scope=Scope.SYSTEM)
    env.path.list(persist=True, scope=Scope.USER)                 # stored PATH of one scope only
    print(env.path)                                               # this process's PATH, one entry per line

Things to know:
- persist=False: only os.environ of the current process (and its children) changes.
                 `scope` has no effect.
- persist=True:  the value is written to permanent storage AND os.environ of the current
                 process is updated. Processes that are already running (terminals, IDEs
                 such as PyCharm) will NOT see the change; they keep the environment they
                 were started with. Use env.reload() inside your own process to catch up.
- Windows: permanent values live in the registry (HKCU / HKLM) and a WM_SETTINGCHANGE
           broadcast tells Explorer and other apps to refresh.
- Linux:   there is no registry, so a shell script managed by this module is used.
              USER   -> ~/.config/env-py/env.sh   (sourced from ~/.profile, ~/.bashrc, ...)
              SYSTEM -> /etc/profile.d/env-py.sh  (root required)
           GUI apps that are not started from a login shell may not see these values.
- Scope.SYSTEM needs administrator (Windows) or root (Linux); otherwise PermissionError.
"""
from __future__ import annotations

import enum
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Iterator, Optional

__all__ = ["Env", "Scope", "env"]

_IS_WIN = sys.platform == "win32"
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

if _IS_WIN:
    import ctypes
    import winreg
    from ctypes import wintypes


class Scope(enum.Enum):
    USER = "user"
    SYSTEM = "system"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _validate(key: str, value: Optional[str] = None) -> None:
    if not isinstance(key, str) or not _KEY_RE.match(key):
        raise ValueError(f"invalid environment variable name: {key!r}")
    if value is not None and ("\n" in value or "\r" in value or "\0" in value):
        raise ValueError("value must not contain newline or NUL characters")


def _is_path_key(key: str) -> bool:
    return key == "PATH" or (_IS_WIN and key.upper() == "PATH")


def _norm(p: str) -> str:
    """Normalize a path so two spellings of the same directory compare equal
    (expands %VAR% on Windows, ignores case on Windows, strips trailing separators)."""
    if _IS_WIN:
        p = os.path.expandvars(p)
    return os.path.normcase(os.path.normpath(p)) if p else p


def _same(a: str, b: str) -> bool:
    return _norm(a) == _norm(b)


def _split_path(value: str) -> list:
    return [p for p in value.split(os.pathsep) if p]


def _clean_path(p) -> str:
    p = os.fspath(p)
    if not isinstance(p, str):
        raise TypeError("path must be str or PathLike[str]")
    p = p.strip()
    if not p:
        raise ValueError("empty path")
    if os.pathsep in p or "\n" in p or "\0" in p:
        raise ValueError(f"invalid path entry: {p!r}")
    return p


# --------------------------------------------------------------------------
# Windows backend (registry)
# --------------------------------------------------------------------------
class _WindowsBackend:
    _SYSTEM_SUBKEY = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    _PATH_NAME = "Path"

    def _root(self, scope: Scope):
        if scope is Scope.USER:
            return winreg.HKEY_CURRENT_USER, "Environment"
        return winreg.HKEY_LOCAL_MACHINE, self._SYSTEM_SUBKEY

    def get(self, key: str, scope: Scope) -> Optional[str]:
        root, sub = self._root(scope)
        try:
            with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as k:
                value, _ = winreg.QueryValueEx(k, key)
                return str(value)  # REG_EXPAND_SZ is returned unexpanded (%VAR% kept)
        except FileNotFoundError:
            return None

    def all(self, scope: Scope) -> dict:
        root, sub = self._root(scope)
        out: dict = {}
        try:
            with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as k:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(k, i)
                    except OSError:  # no more values
                        break
                    out[name] = str(value)
                    i += 1
        except FileNotFoundError:
            pass
        return out

    def set(self, key: str, value: str, scope: Scope) -> None:
        root, sub = self._root(scope)
        with winreg.OpenKey(root, sub, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            try:
                _, old_type = winreg.QueryValueEx(k, key)
            except FileNotFoundError:
                old_type = winreg.REG_SZ
            # Keep an expandable type if the value contains %VAR% or the old one was
            # REG_EXPAND_SZ (e.g. PATH).
            kind = (
                winreg.REG_EXPAND_SZ
                if old_type == winreg.REG_EXPAND_SZ or "%" in value
                else winreg.REG_SZ
            )
            winreg.SetValueEx(k, key, 0, kind, value)
        self._broadcast()

    def unset(self, key: str, scope: Scope) -> None:
        root, sub = self._root(scope)
        try:
            with winreg.OpenKey(root, sub, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, key)
        except FileNotFoundError:
            return
        self._broadcast()

    # ---- PATH (edits only the PATH of the given scope; never mixes USER and SYSTEM) ----
    def get_path(self, scope: Scope) -> list:
        raw = self.get(self._PATH_NAME, scope) or ""
        return [p for p in raw.split(";") if p]  # entries keep %SystemRoot% etc. unexpanded

    def _write_path(self, scope: Scope, entries: list) -> None:
        root, sub = self._root(scope)
        with winreg.OpenKey(root, sub, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, self._PATH_NAME, 0, winreg.REG_EXPAND_SZ, ";".join(entries))
        self._broadcast()

    def add_path(self, entry: str, scope: Scope, first: bool) -> None:
        entries = self.get_path(scope)
        if any(_same(e, entry) for e in entries):
            return
        if first:
            entries.insert(0, entry)
        else:
            entries.append(entry)
        self._write_path(scope, entries)

    def remove_path(self, entry: str, scope: Scope) -> None:
        entries = self.get_path(scope)
        kept = [e for e in entries if not _same(e, entry)]
        if len(kept) != len(entries):
            self._write_path(scope, kept)

    @staticmethod
    def _broadcast() -> None:
        """Tell Explorer and other apps that the environment changed
        (newly started processes will see the new values)."""
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        send = ctypes.windll.user32.SendMessageTimeoutW
        send.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, ctypes.c_wchar_p,
            wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
        ]
        send.restype = wintypes.LPARAM
        result = ctypes.c_size_t()
        send(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
             SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))


# --------------------------------------------------------------------------
# POSIX backend (Linux) - a shell script managed by this module
#
# File format:
#   export KEY='value'                 <- regular variables
#   __envpy_path first '/opt/bin'      <- PATH entries (first = prepend, last = append)
#
# The __envpy_path helper never adds an entry twice, so sourcing the file repeatedly
# (nested shells, ~/.bashrc re-reads) does not make PATH grow.
# --------------------------------------------------------------------------
class _PosixBackend:
    _MARK = "# added by env.py"
    _HEADER = [
        "# Managed by env.py - do not edit by hand",
        '__envpy_path() { case ":$PATH:" in *":$2:"*) ;; *) if [ "$1" = first ]; '
        'then PATH="$2:$PATH"; else PATH="$PATH:$2"; fi; export PATH ;; esac; }',
    ]
    _FOOTER = ["unset -f __envpy_path 2>/dev/null"]

    def _file(self, scope: Scope) -> Path:
        if scope is Scope.USER:
            base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
            return base / "env-py" / "env.sh"
        return Path("/etc/profile.d/env-py.sh")

    @staticmethod
    def _read(path: Path):
        data: dict = {}
        paths: list = []  # [(position, directory)]
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return data, paths
        for line in text.splitlines():
            line = line.strip()
            if not (line.startswith("export ") or line.startswith("__envpy_path ")):
                continue
            try:
                parts = shlex.split(line)
            except ValueError:
                continue
            if parts[0] == "export" and len(parts) == 2 and "=" in parts[1]:
                k, v = parts[1].split("=", 1)
                data[k] = v
            elif parts[0] == "__envpy_path" and len(parts) == 3 and parts[1] in ("first", "last"):
                paths.append((parts[1], parts[2]))
        return data, paths

    def _write(self, path: Path, data: dict, paths: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = list(self._HEADER)
        lines += [f"export {k}={shlex.quote(v)}" for k, v in sorted(data.items())]
        lines += [f"__envpy_path {pos} {shlex.quote(d)}" for pos, d in paths]
        lines += self._FOOTER
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".env-py-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)  # atomic replace
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _ensure_sourced(self, script: Path) -> None:
        """Make the user's shells load our script (adds one line per rc file, only once)."""
        line = f'[ -f "{script}" ] && . "{script}"  {self._MARK}'
        home = Path.home()
        candidates = [home / n for n in (".profile", ".bash_profile", ".bashrc", ".zshenv")]
        targets = [p for p in candidates if p.exists()] or [home / ".profile"]
        for rc in targets:
            text = rc.read_text(encoding="utf-8") if rc.exists() else ""
            if self._MARK in text:
                continue
            with rc.open("a", encoding="utf-8") as f:
                if text and not text.endswith("\n"):
                    f.write("\n")
                f.write(line + "\n")

    def get(self, key: str, scope: Scope) -> Optional[str]:
        return self._read(self._file(scope))[0].get(key)

    def all(self, scope: Scope) -> dict:
        return self._read(self._file(scope))[0]

    def set(self, key: str, value: str, scope: Scope) -> None:
        path = self._file(scope)
        data, paths = self._read(path)
        data[key] = value
        self._write(path, data, paths)
        if scope is Scope.USER:
            self._ensure_sourced(path)

    def unset(self, key: str, scope: Scope) -> None:
        path = self._file(scope)
        data, paths = self._read(path)
        if key in data:
            del data[key]
            self._write(path, data, paths)

    # ---- PATH ----
    def get_path(self, scope: Scope) -> list:
        return [d for _, d in self._read(self._file(scope))[1]]

    def add_path(self, entry: str, scope: Scope, first: bool) -> None:
        path = self._file(scope)
        data, paths = self._read(path)
        if any(_same(d, entry) for _, d in paths):
            return
        paths.append(("first" if first else "last", entry))
        self._write(path, data, paths)
        if scope is Scope.USER:
            self._ensure_sourced(path)

    def remove_path(self, entry: str, scope: Scope) -> None:
        path = self._file(scope)
        data, paths = self._read(path)
        kept = [(pos, d) for pos, d in paths if not _same(d, entry)]
        if len(kept) != len(paths):
            self._write(path, data, kept)


# --------------------------------------------------------------------------
# env.path
# --------------------------------------------------------------------------
class _PathAPI:
    """Manage PATH as a list of directories: add / remove / list."""

    def __init__(self, backend) -> None:
        self._backend = backend

    # ---- current process (os.environ["PATH"]) ----
    @staticmethod
    def _add_process(p: str, first: bool) -> None:
        if _IS_WIN:
            p = os.path.expandvars(p)
        current = _split_path(os.environ.get("PATH", ""))
        if any(_same(p, c) for c in current):
            return
        if first:
            current.insert(0, p)
        else:
            current.append(p)
        os.environ["PATH"] = os.pathsep.join(current)

    @staticmethod
    def _remove_process(p: str) -> None:
        current = _split_path(os.environ.get("PATH", ""))
        os.environ["PATH"] = os.pathsep.join(c for c in current if not _same(c, p))

    # ---- public API ----
    def add(self, *paths, first: bool = False, persist: bool = False,
            scope: Scope = Scope.USER) -> None:
        """
        Add one or more directories to PATH. Entries that already exist are left alone.

        :param first: put the entries at the front of PATH (highest priority);
                      by default they are appended. Given order is preserved.
        :param persist: also store permanently (edits only the PATH of `scope`).
        :param scope: Scope.USER or Scope.SYSTEM (only used when persist=True).
        """
        entries = [_clean_path(p) for p in paths]
        for p in (reversed(entries) if first else entries):
            if persist:
                self._backend.add_path(p, scope, first)
            self._add_process(p, first)

    def remove(self, *paths, persist: bool = False, scope: Scope = Scope.USER) -> None:
        """Remove one or more directories from PATH (missing entries are ignored)."""
        for p in [_clean_path(p) for p in paths]:
            if persist:
                self._backend.remove_path(p, scope)
            self._remove_process(p)

    def list(self, *, persist: bool = False, scope: Scope = Scope.USER) -> list:
        """persist=False: PATH of this process. persist=True: stored PATH of `scope` only."""
        if persist:
            return self._backend.get_path(scope)
        return _split_path(os.environ.get("PATH", ""))

    def __iter__(self) -> Iterator[str]:
        return iter(self.list())

    def __len__(self) -> int:
        return len(self.list())

    def __contains__(self, p) -> bool:
        return any(_same(_clean_path(p), c) for c in self.list())

    def __str__(self) -> str:
        return "\n".join(self.list())

    def __repr__(self) -> str:
        return f"EnvPath({self.list()!r})"


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
class Env:
    def __init__(self) -> None:
        self._backend = _WindowsBackend() if _IS_WIN else _PosixBackend()
        self.path = _PathAPI(self._backend)

    def get(
            self,
            key: str,
            default: Optional[str] = None,
            *,
            persist: bool = False,
            scope: Scope = Scope.USER,
    ) -> Optional[str]:
        """
        persist=False: read from os.environ (what this process really sees).
        persist=True:  read the permanently stored value of `scope`.
        """
        _validate(key)
        if persist:
            value = self._backend.get(key, scope)
            return default if value is None else value
        return os.environ.get(key, default)

    def set(
            self,
            key: str,
            value,
            *,
            persist: bool = False,
            scope: Scope = Scope.USER,
    ) -> None:
        """
        :param persist: also store the value permanently (otherwise this process only).
        :param scope: Scope.USER or Scope.SYSTEM (only used when persist=True).
        """
        value = str(value)
        _validate(key, value)
        if persist and _is_path_key(key):
            raise ValueError("don't overwrite the whole PATH; use env.path.add()/remove()")
        if persist:
            self._backend.set(key, value, scope)
        os.environ[key] = os.path.expandvars(value) if (persist and _IS_WIN) else value

    def unset(
            self,
            key: str,
            *,
            persist: bool = False,
            scope: Scope = Scope.USER,
    ) -> None:
        """Delete a variable. Missing variables are ignored."""
        _validate(key)
        if persist and _is_path_key(key):
            raise ValueError("don't delete the whole PATH; use env.path.remove()")
        if persist:
            self._backend.unset(key, scope)
        os.environ.pop(key, None)

    def reload(self, *, override: bool = False) -> None:
        """
        Load the permanently stored values (SYSTEM first, then USER on top) into the
        os.environ of this process. Useful when a long-running parent (e.g. PyCharm)
        still holds an old environment.

        - override=False: only add variables missing from os.environ, so values set by
                          an IDE or a virtualenv are not overwritten.
        - override=True:  overwrite existing values with the stored ones.
        - PATH is never overwritten; only entries that are not present yet get appended.
        """
        values: dict = {}
        for scope in (Scope.SYSTEM, Scope.USER):  # USER wins over SYSTEM
            for k, v in self._backend.all(scope).items():
                name = k.upper() if _IS_WIN else k
                if name != "PATH":
                    values[name] = v

        for name, v in values.items():
            if override or name not in os.environ:
                os.environ[name] = os.path.expandvars(v) if _IS_WIN else v

        for scope in (Scope.SYSTEM, Scope.USER):
            for p in self._backend.get_path(scope):
                self.path._add_process(p, first=False)


env = Env()