"""Tests for body-package loading and the capability registry (spec §20, §21)."""

import _harness  # noqa: F401
from droidos.core.config import Config
from droidos.body.loader import BodyManager


def _mgr():
    return BodyManager(Config.load())


def test_both_bodies_load():
    bm = _mgr()
    assert set(["ig-mk1", "r2-mk1"]).issubset(set(bm.available_bodies()))
    ig = bm.load("ig-mk1")
    r2 = bm.load("r2-mk1")
    assert ig.manifest.locomotion_type == "biped"
    assert r2.manifest.locomotion_type == "differential"


def test_biped_can_walk_not_roll():
    ig = _mgr().load("ig-mk1")
    assert ig.capabilities.can("walk") is True
    assert ig.capabilities.can("roll") is False
    assert ig.capabilities.supports_motion()


def test_wheeled_can_roll_not_walk():
    r2 = _mgr().load("r2-mk1")
    assert r2.capabilities.can("roll") is True
    assert r2.capabilities.can("walk") is False


def test_experimental_is_not_supported():
    ig = _mgr().load("ig-mk1")
    # stairs is experimental -> can() is False, is_experimental() True
    assert ig.capabilities.can("stairs") is False
    assert ig.capabilities.is_experimental("stairs") is True


def test_required_sensors_declared():
    ig = _mgr().load("ig-mk1")
    for sid in ig.required_sensor_ids():
        assert sid in ig.sensor_ids()


def test_placeholder_signature_flagged_not_fatal():
    ig = _mgr().load("ig-mk1")
    assert any("placeholder" in i for i in ig.issues)
    fatal = [i for i in ig.issues if "placeholder" not in i]
    assert fatal == []
