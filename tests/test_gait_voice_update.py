"""Tests for the walking-policy runtime (§25), voice (§12.12) and update (§12.15)."""

import _harness
from _harness import fresh_system, ask_confirm


# --- gait policy (§25) ------------------------------------------------------ #
def test_biped_loads_valid_gait_policy():
    sys_ = fresh_system()
    m = sys_.rt.motion
    assert m.gait_policy is not None
    assert m.gait_policy.runtime in ("cpg", "onnx")
    assert m.gait_issues == []


def test_gait_policy_produces_joint_targets_when_walking():
    sys_ = fresh_system()
    ask_confirm(sys_, "go to the workshop")
    assert sys_.rt.motion.last_joint_targets  # non-empty
    # the sim tracked the commanded joint positions
    acts = sys_.rt.backend.read_all_actuators()
    assert any(abs(a.position) > 0.0 for a in acts.values())


def test_corrupt_gait_policy_is_rejected():
    sys_ = fresh_system()
    from droidos.gait import load_for_body
    body = sys_.rt.body
    body.manifest.gait_policy.checksum = "sha256:deadbeef"
    policy, issues = load_for_body(body)
    assert policy is None
    assert any("checksum" in i for i in issues)


def test_wheeled_body_has_no_gait_policy():
    sys_ = fresh_system(body="r2-mk1")
    assert sys_.rt.motion.gait_policy is None


# --- voice (§12.12) --------------------------------------------------------- #
def test_voice_emergency_stop_bypasses_llm():
    sys_ = fresh_system()
    result = sys_.rt.voice.handle_utterance("emergency stop", "operator")
    assert result.emergency == "emergency_stop"
    assert sys_.rt.safety.estop_engaged()


def test_voice_plain_stop():
    sys_ = fresh_system()
    result = sys_.rt.voice.handle_utterance("stop", "operator")
    assert result.emergency == "stop"
    assert not sys_.rt.safety.estop_engaged()  # plain stop != estop


def test_voice_routes_normal_command_to_language():
    sys_ = fresh_system()
    result = sys_.rt.voice.handle_utterance("what is your status", "operator")
    assert result.emergency is None
    assert "state" in result.response.lower() or "ig-12" in result.response.lower()


def test_voice_wake_word_gating():
    sys_ = fresh_system()
    v = sys_.rt.voice
    v.require_wake = True
    ignored = v.handle_utterance("what can you see", "operator")
    assert ignored.woke is False and ignored.response == ""
    heard = v.handle_utterance("IG-12 what can you see", "operator")
    assert heard.woke is True and heard.response


# --- update (§12.15, §33) --------------------------------------------------- #
def _write_bundle(tmp_path, version="1.1.0", signed=True, compatible=True):
    import json
    import os
    payload = {"rootfs": "abc"}
    checksum = "sha256:" + __import__("hashlib").sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()
    doc = {
        "compatible": "droidos" if compatible else "other",
        "version": version,
        "payload": payload,
        "payload_checksum": checksum,
        "signature": "SIGNED" if signed else "",
    }
    path = os.path.join(tmp_path, "bundle.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


def test_update_install_to_inactive_slot_and_health():
    import tempfile
    sys_ = fresh_system()
    up = sys_.rt.update
    assert up.status()["active_slot"] == "A"
    bundle = _write_bundle(tempfile.mkdtemp())
    result = up.install(bundle)
    assert result["ok"] and result["slot"] == "B"
    # confirm boot health of the new slot -> becomes active
    up.confirm_boot_health(True)
    assert up.status()["active_slot"] == "B"
    assert up.status()["running_version"] == "1.1.0"


def test_update_failed_boot_rolls_back():
    import tempfile
    sys_ = fresh_system()
    up = sys_.rt.update
    up.install(_write_bundle(tempfile.mkdtemp()))
    up.confirm_boot_health(False)      # simulated bad boot
    assert up.status()["active_slot"] == "A"  # rolled back


def test_update_rejects_unsigned_bundle():
    import tempfile
    sys_ = fresh_system()
    result = sys_.rt.update.install(_write_bundle(tempfile.mkdtemp(), signed=False))
    assert not result["ok"] and "signed" in result["reason"]


def test_update_rejects_incompatible_bundle():
    import tempfile
    sys_ = fresh_system()
    result = sys_.rt.update.install(_write_bundle(tempfile.mkdtemp(), compatible=False))
    assert not result["ok"]
