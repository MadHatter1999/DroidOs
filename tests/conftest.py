"""pytest bootstrap: make ``droidos`` importable from ``src`` without installing,
and put the tests directory on the path so ``import _harness`` works."""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for path in (os.path.join(_ROOT, "src"), _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)
