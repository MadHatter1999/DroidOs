"""Diagnostics tests: faults surface as evidence, not speculation (spec §28)."""

import _harness
from _harness import fresh_system
from droidos.core.models import DiagnosticLevel


def test_clean_system_has_no_faults():
    sys_ = fresh_system()
    assert sys_.rt.diagnostics.summary()["fault_count"] == 0


def test_overtemp_surfaces_as_error():
    sys_ = fresh_system()
    joint = sys_.rt.backend.actuator_names()[0]
    sys_.rt.backend.inject_fault("motor_overheat", joint=joint, temp=90.0)
    problems = sys_.rt.diagnostics.problems()
    assert any(p.level == DiagnosticLevel.ERROR for p in problems)
    hottest = sys_.rt.diagnostics.hottest_actuator()
    assert hottest.values["temperature_c"] >= 85.0


def test_missing_required_sensor_is_error():
    sys_ = fresh_system()
    sys_.rt.backend.inject_fault("sensor_dropout", sensor="imu/torso")
    summary = sys_.rt.diagnostics.summary()
    assert summary["fault_count"] >= 1
