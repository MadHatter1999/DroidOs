"""Safety invariant tests (spec §16, §24, §40). These are the most important tests."""

import _harness
from _harness import fresh_system, ask_confirm
from droidos.core.states import DroidState
from droidos.core.models import BodyVelocity


def test_power_defaults_off_at_boot():
    sys_ = fresh_system()
    assert sys_.rt.backend.power_enabled() is False


def test_motion_has_no_effect_without_power():
    sys_ = fresh_system()
    before = sys_.rt.backend.pose().to_dict()
    sys_.rt.backend.command_velocity(BodyVelocity(0.3, 0, 0), 1.0)
    assert sys_.rt.backend.pose().to_dict() == before


def test_emergency_stop_removes_power_and_forbids_motion():
    sys_ = fresh_system()
    sys_.rt.safety.engage_estop("test")
    assert sys_.rt.safety.estop_engaged()
    assert sys_.rt.backend.power_enabled() is False
    assert sys_.rt.state.state == DroidState.EMERGENCY_STOPPED
    # a motion request is now refused by the broker
    resp = ask_confirm(sys_, "go to the workshop")
    assert resp.outcome in ("rejected", "failed")


def test_estop_latch_persists_across_reboot():
    sys_ = fresh_system()
    sys_.rt.safety.engage_estop("test")
    from droidos.system import DroidSystem
    sys2 = DroidSystem.boot()  # same DROIDOS_STATE
    assert sys2.rt.state.state == DroidState.EMERGENCY_STOPPED
    sys2.rt.safety.reset_estop()
    sys3 = DroidSystem.boot()
    assert sys3.rt.state.state != DroidState.EMERGENCY_STOPPED


def test_safety_link_loss_inhibits_motion():
    sys_ = fresh_system()
    sys_.rt.safety.set_safety_link(False)
    resp = ask_confirm(sys_, "go to the workshop")
    assert resp.outcome in ("rejected", "failed")


def test_low_battery_inhibits_motion():
    sys_ = fresh_system()
    sys_.rt.backend._battery = 5.0  # below the 20% motion minimum
    sup = sys_.supervisor
    readiness = sup.assess_readiness()
    assert readiness.state == DroidState.MOTION_INHIBITED
    assert any("battery" in r for r in readiness.inhibit_reasons)
