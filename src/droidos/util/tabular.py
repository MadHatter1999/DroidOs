"""Small helpers for human-readable table and key/value output in the CLIs."""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence


def kv(pairs: Iterable[tuple[str, Any]], width: int | None = None) -> str:
    """Render aligned ``key: value`` lines."""
    pairs = list(pairs)
    if not pairs:
        return ""
    w = width or max(len(str(k)) for k, _ in pairs)
    return "\n".join(f"{str(k):<{w}}  {fmt(v)}" for k, v in pairs)


def table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    rows = [[fmt(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(f"{h:<{widths[i]}}" for i, h in enumerate(headers))
    sep = "  ".join("-" * widths[i] for i in range(len(headers)))
    body = "\n".join("  ".join(f"{c:<{widths[i]}}" for i, c in enumerate(row)) for row in rows)
    return f"{line}\n{sep}\n{body}" if body else f"{line}\n{sep}"


def fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def as_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=_json_default, sort_keys=False)


def _json_default(o: Any) -> Any:
    if hasattr(o, "to_dict"):
        return o.to_dict()
    if hasattr(o, "value"):  # Enum
        return o.value
    return str(o)
