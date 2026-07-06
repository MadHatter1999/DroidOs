"""A tiny YAML-subset parser with no third-party dependency.

DroidOS body manifests and configuration are authored in a deliberately simple
YAML subset so that the core brain has **zero required dependencies** and can run
on a bare embedded image. If :mod:`yaml` (PyYAML) is installed it is used
instead, which also accepts the full YAML grammar.

Supported subset (sufficient for every file shipped in this repository):

* ``key: value`` mappings, arbitrarily nested by 2-space indentation
* ``key:`` followed by an indented block (mapping or list)
* ``- item`` sequences (scalars or ``- key: value`` inline maps)
* scalars: ``true``/``false``, ``null``/``~``, integers, floats, and strings
  (optionally single- or double-quoted)
* inline flow scalars only for empty collections: ``[]`` and ``{}``
* ``#`` line comments and blank lines

This is intentionally small; it is not a general YAML implementation.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised only when PyYAML is present
    import yaml as _pyyaml  # type: ignore
except Exception:  # noqa: BLE001
    _pyyaml = None


class MiniYamlError(ValueError):
    """Raised when the YAML subset cannot be parsed."""


def load(text: str) -> Any:
    """Parse *text* into Python objects."""
    if _pyyaml is not None:  # pragma: no cover
        return _pyyaml.safe_load(text)
    return _parse(text)


def load_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return load(fh.read())


def dump(obj: Any, indent: int = 0) -> str:
    """Serialize *obj* back to the YAML subset (used for round-trips/tests)."""
    if _pyyaml is not None:  # pragma: no cover
        return _pyyaml.safe_dump(obj, default_flow_style=False, sort_keys=False)
    return _dump(obj, indent)


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def _scalar(token: str) -> Any:
    token = token.strip()
    if token == "" or token in ("null", "~", "None"):
        return None
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    if token == "[]":
        return []
    if token == "{}":
        return {}
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    if len(token) >= 2 and token[0] == "[" and token[-1] == "]":
        # inline flow sequence: [a, b, c]
        inner = token[1:-1].strip()
        if inner == "":
            return []
        return [_scalar(part) for part in _split_flow(inner)]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _split_flow(inner: str) -> list[str]:
    """Split a flow-sequence body on commas, respecting quotes."""
    parts: list[str] = []
    buf = ""
    in_single = in_double = False
    for ch in inner:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "," and not in_single and not in_double:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _block_scalar_kind(rest: str) -> tuple[str, bool] | None:
    """Detect a block-scalar header (``|``, ``>`` with optional ``-``/``+``).

    Returns ``(style, chomp_strip)`` where style is 'literal' or 'folded', or
    ``None`` if *rest* is not a block-scalar indicator.
    """
    head = rest.strip()
    if not head or head[0] not in ("|", ">"):
        return None
    style = "literal" if head[0] == "|" else "folded"
    chomp_strip = "-" in head[1:]
    return style, chomp_strip


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _clean_lines(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in text.splitlines():
        # strip trailing comments only when the '#' is not inside quotes
        line = _strip_comment(raw)
        if line.strip() == "":
            continue
        if line.lstrip().startswith("---") or line.lstrip().startswith("..."):
            continue
        out.append((_indent_of(line), line.strip()))
    return out


def _strip_comment(line: str) -> str:
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            # only treat as comment if preceded by whitespace or start
            if i == 0 or line[i - 1] in (" ", "\t"):
                return line[:i]
    return line


def _parse(text: str) -> Any:
    lines = _clean_lines(text)
    if not lines:
        return None
    value, consumed = _parse_block(lines, 0, lines[0][0])
    if consumed != len(lines):
        raise MiniYamlError(f"unexpected indentation near: {lines[consumed][1]!r}")
    return value


def _parse_block(lines: list[tuple[int, str]], start: int, indent: int) -> tuple[Any, int]:
    if lines[start][1].startswith("- "):
        return _parse_list(lines, start, indent)
    return _parse_map(lines, start, indent)


def _parse_map(lines: list[tuple[int, str]], start: int, indent: int) -> tuple[dict, int]:
    result: dict[str, Any] = {}
    i = start
    while i < len(lines):
        cur_indent, content = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise MiniYamlError(f"bad indent at {content!r}")
        if content.startswith("- "):
            raise MiniYamlError(f"unexpected list item in mapping: {content!r}")
        if ":" not in content:
            raise MiniYamlError(f"expected 'key: value' but got {content!r}")
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        block = _block_scalar_kind(rest)
        if block is not None:
            value, i = _parse_block_scalar(lines, i + 1, indent, block)
            result[key] = value
        elif rest == "":
            # nested block belongs to this key if more-indented lines follow
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                child_indent = lines[i + 1][0]
                value, i = _parse_block(lines, i + 1, child_indent)
                result[key] = value
            else:
                result[key] = None
                i += 1
        else:
            result[key] = _scalar(rest)
            i += 1
    return result, i


def _parse_block_scalar(
    lines: list[tuple[int, str]], start: int, indent: int, block: tuple[str, bool]
) -> tuple[str, int]:
    """Consume the indented body of a ``|`` / ``>`` block scalar."""
    style, chomp_strip = block
    parts: list[str] = []
    i = start
    while i < len(lines) and lines[i][0] > indent:
        parts.append(lines[i][1])  # content is already left-stripped
        i += 1
    if style == "folded":
        text = " ".join(parts)
    else:
        text = "\n".join(parts)
    if not chomp_strip and parts:
        text += "" if style == "folded" else "\n"
    return text, i


def _parse_list(lines: list[tuple[int, str]], start: int, indent: int) -> tuple[list, int]:
    result: list[Any] = []
    i = start
    while i < len(lines):
        cur_indent, content = lines[i]
        if cur_indent < indent or not content.startswith("- "):
            if cur_indent < indent:
                break
            if not content.startswith("- ") and cur_indent == indent:
                break
        if cur_indent > indent:
            raise MiniYamlError(f"bad list indent at {content!r}")
        item = content[2:].strip()
        if ":" in item and not (item[0] in ("'", '"')):
            # inline "- key: value" starts a mapping; reparse this line as a map entry
            # Build a synthetic sub-block: treat the item plus any deeper lines.
            synth = [(indent + 2, item)]
            j = i + 1
            while j < len(lines) and lines[j][0] > indent:
                synth.append(lines[j])
                j += 1
            value, _ = _parse_map(synth, 0, indent + 2)
            result.append(value)
            i = j
        else:
            result.append(_scalar(item))
            i += 1
    return result, i


# --------------------------------------------------------------------------- #
# Dumper (subset)
# --------------------------------------------------------------------------- #
def _dump(obj: Any, indent: int) -> str:
    pad = " " * indent
    if isinstance(obj, dict):
        if not obj:
            return pad + "{}\n"
        out = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{k}:")
                out.append(_dump(v, indent + 2).rstrip("\n"))
            else:
                out.append(f"{pad}{k}: {_dump_scalar(v)}")
        return "\n".join(out) + "\n"
    if isinstance(obj, list):
        if not obj:
            return pad + "[]\n"
        out = []
        for item in obj:
            if isinstance(item, dict):
                block = _dump(item, indent + 2).rstrip("\n").splitlines()
                first = block[0].lstrip()
                out.append(f"{pad}- {first}")
                out.extend(block[1:])
            else:
                out.append(f"{pad}- {_dump_scalar(item)}")
        return "\n".join(out) + "\n"
    return pad + _dump_scalar(obj) + "\n"


def _dump_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or any(c in s for c in ":#") or s.strip() != s:
        return f'"{s}"'
    return s
