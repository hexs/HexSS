"""
Everything this script creates is removed again at the end, so it is safe to run.
"""
import tempfile
from hexss.env import env, Scope

VAR = "ENVPY_DEMO"


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Temporary variables (this process and its children only)
    # ------------------------------------------------------------------
    section("Temporary variable")
    print("before set :", env.get(VAR))                 # None
    env.set(VAR, "temp-value")                          # non-str values are converted with str()
    print("after set  :", env.get(VAR))                 # temp-value
    print("default    :", env.get("ENVPY_MISSING", "fallback"))
    env.unset(VAR)
    print("after unset:", env.get(VAR))                 # None

    # ------------------------------------------------------------------
    # 2. Permanent variables (USER scope, no admin/root needed)
    # ------------------------------------------------------------------
    section("Permanent variable (USER scope)")
    env.set(VAR, 123, persist=True, scope=Scope.USER)
    print("process view :", env.get(VAR))                                   # 123
    print("stored value :", env.get(VAR, persist=True, scope=Scope.USER))   # 123

    # A process that was started BEFORE the change (a terminal, PyCharm, ...) keeps its
    # old environment. reload() pulls the stored values into this process:
    env.unset(VAR)                                      # simulate a stale process
    print("stale process:", env.get(VAR))               # None
    env.reload()
    print("after reload :", env.get(VAR))               # 123

    # ------------------------------------------------------------------
    # 3. SYSTEM scope (needs administrator on Windows / root on Linux)
    # ------------------------------------------------------------------
    section("Permanent variable (SYSTEM scope)")
    try:
        env.set(VAR, "system-value", persist=True, scope=Scope.SYSTEM)
        print("stored (SYSTEM):", env.get(VAR, persist=True, scope=Scope.SYSTEM))
        env.unset(VAR, persist=True, scope=Scope.SYSTEM)
    except PermissionError:
        print("skipped: run as administrator/root to use Scope.SYSTEM")

    # ------------------------------------------------------------------
    # 4. PATH helpers: env.path.add / remove / list
    # ------------------------------------------------------------------
    section("PATH")
    demo_dir = tempfile.gettempdir() + "/envpy_demo_bin"

    env.path.add(demo_dir)                              # this process only, appended
    print("in PATH      :", demo_dir in env.path)       # True
    env.path.add(demo_dir)                              # adding twice is a no-op
    env.path.remove(demo_dir)
    print("after remove :", demo_dir in env.path)       # False

    env.path.add(demo_dir, first=True)                  # front of PATH = highest priority
    print("first entry  :", env.path.list()[0])
    env.path.remove(demo_dir)

    # Permanent PATH entry; only the PATH of the chosen scope is edited
    env.path.add(demo_dir, persist=True, scope=Scope.USER)
    print("stored USER PATH contains it:",
          demo_dir in env.path.list(persist=True, scope=Scope.USER))
    env.path.remove(demo_dir, persist=True, scope=Scope.USER)

    # print(env.path) shows this process's PATH, one entry per line
    print("\nCurrent PATH (first 3 entries):")
    for entry in list(env.path)[:3]:
        print("  ", entry)

    # Overwriting the whole PATH is blocked on purpose; use env.path.add/remove instead
    try:
        env.set("PATH", "/nowhere", persist=True)
    except ValueError as exc:
        print("\nblocked:", exc)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    section("Cleanup")
    env.unset(VAR, persist=True, scope=Scope.USER)
    print("stored value after cleanup:", env.get(VAR, persist=True, scope=Scope.USER))  # None


if __name__ == "__main__":
    main()