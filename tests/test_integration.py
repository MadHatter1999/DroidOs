"""End-to-end integration tests across the whole brain (spec §38, §39, §40)."""

import _harness
from _harness import fresh_system, ask_confirm


def test_boots_to_ready():
    sys_ = fresh_system()
    assert sys_.readiness.state.value == "READY"
    assert all(s.state.value == "ACTIVE" for s in sys_.rt.all_services())


def test_status_reports_safe_to_move():
    sys_ = fresh_system()
    resp = sys_.rt.language.process("what is your status", "operator")
    assert "safe to move" in resp.text.lower()


def test_describe_scene_is_honest_without_camera_fault():
    sys_ = fresh_system()
    resp = sys_.rt.language.process("what can you see", "operator")
    assert "server rack" in resp.text


def test_camera_fault_reported_honestly():
    sys_ = fresh_system()
    sys_.rt.backend.inject_fault("sensor_dropout", sensor="camera/front")
    resp = sys_.rt.language.process("what can you see", "operator")
    assert "not responding" in resp.text.lower() or "not available" in resp.text.lower()


def test_navigate_arrives():
    sys_ = fresh_system()
    resp = ask_confirm(sys_, "go to the workshop")
    assert resp.outcome == "approved"
    assert "arrived" in resp.text.lower()


def test_blocked_route_reports_distance():
    sys_ = fresh_system()
    sys_.rt.backend.inject_fault("path_blocked", distance=2.4)
    resp = ask_confirm(sys_, "go to the workshop")
    assert resp.outcome == "failed"
    assert "blocked" in resp.text.lower()
    assert "2.4" in resp.text


def test_inspection_separates_observation_from_interpretation():
    sys_ = fresh_system()
    resp = ask_confirm(sys_, "go to the workshop and inspect the server rack")
    assert resp.outcome == "approved"
    assert "amber" in resp.text.lower()
    assert "observation only" in resp.text.lower()


def test_wheeled_body_refuses_stairs():
    sys_ = fresh_system(body="r2-mk1")
    resp = sys_.rt.language.process("walk upstairs", "operator")
    assert resp.outcome == "rejected"
    assert "stairs" in resp.text.lower()


def test_memory_remember_and_forget():
    sys_ = fresh_system()
    sys_.rt.language.process("remember that the shelf holds networking gear", "operator")
    assert sys_.rt.memory.recall("networking")
    # deleting a memory requires explicit confirmation (spec §18)
    r = sys_.rt.language.process("forget networking gear", "operator")
    assert r.needs_confirmation
    r = ask_confirm(sys_, "forget networking gear")
    assert "removed" in r.text.lower()
    assert not sys_.rt.memory.recall("networking")


def test_offline_degraded_message_for_unknown():
    sys_ = fresh_system()
    resp = sys_.rt.language.process("qwerty nonsense", "operator")
    assert resp.degraded is True
    assert "unavailable" in resp.text.lower()


def test_audit_records_written():
    sys_ = fresh_system()
    ask_confirm(sys_, "go to the workshop")
    kinds = {r.kind for r in sys_.rt.audit.records}
    assert "command" in kinds and "approval" in kinds and "task" in kinds
