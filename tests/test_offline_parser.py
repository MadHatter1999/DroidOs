"""Tests that essential commands parse deterministically without an LLM (spec §16)."""

import _harness  # noqa: F401
from droidos.language import offline_parser as op


def _intent(text):
    return op.parse(text).intent


def test_essential_commands():
    assert _intent("stop") == "motion.stop"
    assert _intent("emergency stop") == "motion.emergency_stop"
    assert _intent("cancel the task") == "task.cancel"
    assert _intent("what is your status") == "robot.get_status"
    assert _intent("battery level") == "robot.get_battery"
    assert _intent("how hot are your motors") == "robot.get_temperature"
    assert _intent("help") == "help"
    assert _intent("return to safe idle") == "robot.return_safe_idle"
    assert _intent("be quiet") == "voice.silence"
    assert _intent("shut down") == "system.shutdown"
    assert _intent("what is wrong") == "diagnostics.summary"
    assert _intent("report active faults") == "diagnostics.summary"


def test_navigation_and_slots():
    i = op.parse("go to the workshop")
    assert i.intent == "navigation.navigate_to"
    assert i.arguments["destination"] == "workshop"
    assert i.requires_motion is True


def test_inspection_slots():
    i = op.parse("go to the workshop and inspect the server rack")
    assert i.intent == "inspect.named_target"
    assert i.arguments["destination"] == "workshop"
    assert i.arguments["target"] == "server rack"


def test_stairs_destination():
    i = op.parse("walk upstairs")
    assert i.arguments["destination"] == "stairs"


def test_unknown_is_unknown():
    assert op.parse("qwertyuiop").intent == "unknown"


def test_affirmative_negative():
    assert op.is_affirmative("yes")
    assert op.is_affirmative("confirm")
    assert op.is_negative("no")
