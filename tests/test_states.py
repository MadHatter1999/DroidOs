"""Tests for the DroidOS state machine (spec §9)."""

import _harness  # noqa: F401
from droidos.core.states import DroidState, StateMachine, InvalidTransition


def test_legal_boot_path():
    sm = StateMachine(DroidState.POWERED_OFF)
    sm.transition(DroidState.BOOTING)
    sm.transition(DroidState.HARDWARE_CHECK)
    sm.transition(DroidState.SAFE_IDLE)
    sm.transition(DroidState.READY)
    assert sm.state == DroidState.READY
    assert sm.motion_permitted()


def test_illegal_transition_raises():
    sm = StateMachine(DroidState.POWERED_OFF)
    raised = False
    try:
        sm.transition(DroidState.ACTIVE)
    except InvalidTransition:
        raised = True
    assert raised


def test_safe_idle_forbids_motion():
    sm = StateMachine(DroidState.SAFE_IDLE)
    assert not sm.motion_permitted()


def test_estop_force_from_any_state():
    sm = StateMachine(DroidState.READY)
    sm.force(DroidState.EMERGENCY_STOPPED, "estop")
    assert sm.state == DroidState.EMERGENCY_STOPPED
    assert not sm.motion_permitted()
