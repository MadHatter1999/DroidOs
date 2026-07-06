"""Command-broker validation tests (spec §14, §17, §18, §21, §32)."""

import _harness
from _harness import fresh_system
from droidos.language.broker import Outcome
from droidos.language.intent import StructuredIntent


def _validate(sys_, intent_name, user="operator", confirmed=False, **args):
    lang = sys_.rt.language
    user_obj = lang.authorizer.resolve(user)
    intent = StructuredIntent(intent=intent_name, arguments=args,
                              requires_motion=lang.registry.get(intent_name).requires_motion
                              if lang.registry.get(intent_name) else False)
    return lang.broker.validate(intent, user_obj, confirmed=confirmed)


def test_unknown_intent_rejected():
    sys_ = fresh_system()
    d = _validate(sys_, "totally.made.up")
    assert d.outcome == Outcome.REJECTED


def test_always_available_bypasses_gates():
    sys_ = fresh_system()
    d = _validate(sys_, "motion.emergency_stop", user="guest")
    assert d.outcome == Outcome.APPROVED  # even a guest can e-stop (spec §18)


def test_guest_cannot_move():
    sys_ = fresh_system()
    d = _validate(sys_, "navigation.navigate_to", user="guest", destination="workshop")
    assert d.outcome == Outcome.REJECTED
    assert "authoriz" in d.reason.lower() or "operator" in d.reason.lower()


def test_admin_requires_owner_and_confirmation():
    sys_ = fresh_system()
    # operator is not owner
    d = _validate(sys_, "system.install_update", user="operator")
    assert d.outcome == Outcome.REJECTED
    # owner gets a confirmation requirement, not immediate approval
    d2 = _validate(sys_, "system.install_update", user="owner")
    assert d2.outcome == Outcome.CONFIRM


def test_capability_refusal_for_unknown_place():
    sys_ = fresh_system()
    d = _validate(sys_, "navigation.navigate_to", destination="mars")
    assert d.outcome == Outcome.REJECTED
    assert "not a known destination" in d.reason


def test_stairs_capability_refusal():
    sys_ = fresh_system()  # biped: stairs experimental -> cannot traverse
    d = _validate(sys_, "navigation.navigate_to", destination="stairs")
    assert d.outcome == Outcome.REJECTED
    assert "stairs" in d.reason.lower()


def test_known_place_needs_confirmation_then_approves():
    sys_ = fresh_system()
    d = _validate(sys_, "navigation.navigate_to", destination="workshop")
    assert d.outcome == Outcome.CONFIRM
    d2 = _validate(sys_, "navigation.navigate_to", destination="workshop", confirmed=True)
    assert d2.outcome == Outcome.APPROVED
