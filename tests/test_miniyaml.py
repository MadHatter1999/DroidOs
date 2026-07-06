"""Tests for the dependency-free YAML subset parser."""

import _harness  # noqa: F401  (sets up sys.path)
from droidos.util import miniyaml


def test_scalars_and_nesting():
    data = miniyaml.load("a: 1\nb: true\nc:\n  d: hello\n  e: 2.5\n")
    assert data == {"a": 1, "b": True, "c": {"d": "hello", "e": 2.5}}


def test_flow_list():
    data = miniyaml.load("resolution: [1280, 720]\nnames: [a, b, c]\n")
    assert data["resolution"] == [1280, 720]
    assert data["names"] == ["a", "b", "c"]


def test_block_scalar_folded():
    text = "description: >-\n  line one\n  line two\nother: 3\n"
    data = miniyaml.load(text)
    assert data["description"] == "line one line two"
    assert data["other"] == 3


def test_list_of_maps():
    text = "items:\n  - id: a\n    v: 1\n  - id: b\n    v: 2\n"
    data = miniyaml.load(text)
    assert data["items"] == [{"id": "a", "v": 1}, {"id": "b", "v": 2}]


def test_comments_ignored():
    data = miniyaml.load("# a comment\nx: 1  # inline\n")
    assert data == {"x": 1}
