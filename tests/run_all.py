"""Zero-dependency test runner.

Runs every ``test_*`` function in every ``test_*.py`` module in this directory,
without requiring pytest. Use this on a target image or anywhere pytest is not
installed:

    python tests/run_all.py

Exit code is non-zero if any test fails.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_module(path: str):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    files = sorted(
        f for f in os.listdir(HERE)
        if f.startswith("test_") and f.endswith(".py")
    )
    passed = failed = 0
    failures: list[str] = []
    for fname in files:
        mod = _load_module(os.path.join(HERE, fname))
        for attr in sorted(dir(mod)):
            if not attr.startswith("test_"):
                continue
            fn = getattr(mod, attr)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
                print(f"  PASS  {fname}::{attr}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                failures.append(f"{fname}::{attr}: {type(exc).__name__}: {exc}")
                print(f"  FAIL  {fname}::{attr}  -> {type(exc).__name__}: {exc}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
