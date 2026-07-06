"""``droid-voice`` (spec §12.12).

Wake-word detection, speech recognition, speaker identification (where enabled),
text-to-speech, audio output, interruptible speech and emergency command
detection.

The engine is pluggable behind :class:`VoiceEngine`. The default
:class:`TextModeEngine` needs no audio hardware, spoken input is supplied as text
and speech is printed, so the whole voice pipeline (wake word, emergency
detection, speaker id, interruptible TTS) runs and is testable without a
microphone. Optional adapters (Vosk/Whisper ASR, Piper TTS) plug in unchanged.

Crucially, emergency command detection runs **before** ASR/LLM and calls the
safety gateway directly, so "stop"/"emergency stop" work even if the language
model is unavailable (spec §16, §39).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


# Emergency phrases matched locally, before any model, in any state (spec §16).
_EMERGENCY = [
    (re.compile(r"\b(emergency stop|e-?stop|kill power|kill it)\b"), "emergency_stop"),
    (re.compile(r"\b(stop|halt|freeze|whoa|abort)\b"), "stop"),
]


@dataclass
class VoiceResult:
    heard: str
    woke: bool
    emergency: str | None
    speaker: str
    response: str


class VoiceEngine:
    """Pluggable audio engine. The default is text-mode (no hardware)."""

    def capture(self, prompt_text: str | None = None) -> str | None:  # pragma: no cover
        raise NotImplementedError

    def speak(self, text: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def identify_speaker(self, sample: str) -> str | None:
        return None


class TextModeEngine(VoiceEngine):
    """Treats typed lines as speech and prints spoken output. Fully runnable."""

    def __init__(self, sink: Callable[[str], None] | None = None) -> None:
        self._sink = sink or (lambda s: print(s))

    def capture(self, prompt_text: str | None = None) -> str | None:
        try:
            return input(prompt_text or "voice> ")
        except (EOFError, KeyboardInterrupt):
            return None

    def speak(self, text: str) -> None:
        if text:
            self._sink(f"[{'droid'}] {text}")

    def identify_speaker(self, sample: str) -> str | None:
        return None


class Voice(ManagedService):
    requires = ("safety_gateway",)

    def __init__(self, rt: "Runtime", engine: VoiceEngine | None = None) -> None:
        super().__init__("voice", rt)
        self.engine = engine or TextModeEngine()
        ident = rt.config.identity
        self.wake_names = [w.lower() for w in ident.get("wake_names", [ident.get("name", "droid")])]
        self.require_wake = bool(rt.config.get("voice", "require_wake_word", default=False))
        self._speaking = False
        self.speaker_map = rt.config.get("voice", "speakers", default={}) or {}

    # wake word ------------------------------------------------------------ #
    def has_wake_word(self, text: str) -> bool:
        t = text.lower()
        return any(w in t for w in self.wake_names)

    def strip_wake_word(self, text: str) -> str:
        out = text
        for w in self.wake_names:
            out = re.sub(rf"\b{re.escape(w)}\b", "", out, flags=re.IGNORECASE)
        return out.strip(",.")

    # emergency detection (before ASR/LLM) --------------------------------- #
    def detect_emergency(self, text: str) -> str | None:
        t = " ".join(text.lower().split())
        for pattern, kind in _EMERGENCY:
            if pattern.search(t):
                return kind
        return None

    # speaker identification (spec §12.12, §32) ---------------------------- #
    def identify_speaker(self, sample: str) -> str:
        who = self.engine.identify_speaker(sample)
        if who:
            return who
        # a configured voiceprint map may hint the user; high-risk actions still
        # require authenticated authorization, not merely a familiar voice (§32).
        return self.rt.config.get("default_user", default="operator")

    # output --------------------------------------------------------------- #
    def speak(self, text: str) -> None:
        self._speaking = True
        try:
            self.engine.speak(text)
        finally:
            self._speaking = False

    def silence(self) -> None:
        self._speaking = False

    def speaking(self) -> bool:
        return self._speaking

    # full pipeline -------------------------------------------------------- #
    def handle_utterance(self, text: str, user: str | None = None) -> VoiceResult:
        """Route one heard utterance through wake word, emergency detection and,
        if appropriate, the language service."""
        speaker = user or self.identify_speaker(text)

        emergency = self.detect_emergency(text)
        if emergency == "emergency_stop":
            self.rt.safety.engage_estop("voice_emergency")
            msg = "Emergency stop engaged. Motor power removed."
            self.speak(msg)
            return VoiceResult(text, True, emergency, speaker, msg)
        if emergency == "stop":
            if self.rt.motion:
                self.rt.motion.stop()
            msg = "Stopped."
            self.speak(msg)
            return VoiceResult(text, True, emergency, speaker, msg)

        woke = not self.require_wake or self.has_wake_word(text)
        if not woke:
            return VoiceResult(text, False, None, speaker, "")

        command = self.strip_wake_word(text) if self.require_wake else text
        resp = self.rt.language.process(command, speaker)
        self.speak(resp.text)
        return VoiceResult(text, woke, None, speaker, resp.text)

    def diagnostics(self) -> list[DiagnosticStatus]:
        return [
            DiagnosticStatus(
                name="voice/engine",
                level=DiagnosticLevel.OK,
                message=f"{type(self.engine).__name__}; wake={'/'.join(self.wake_names)}",
                values={
                    "engine": type(self.engine).__name__,
                    "require_wake_word": self.require_wake,
                    "speaking": self._speaking,
                },
            )
        ]
