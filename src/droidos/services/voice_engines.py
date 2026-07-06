"""Optional real audio engines for droid-voice (spec §12.12).

These are the production integration points. They import their dependencies lazily
so the reference build (and the tests) run without audio hardware or model files;
selecting an audio engine that is not installed raises a clear error rather than
failing silently.

On a target (especially the Jetson build, spec §7.2), wire these to on-device
models: Vosk or whisper.cpp for speech recognition, Piper for text-to-speech.
"""

from __future__ import annotations

from typing import Any

from .voice import VoiceEngine


class AudioEngine(VoiceEngine):
    """Microphone/speaker engine backed by pluggable ASR and TTS models."""

    def __init__(self, asr_model: str, tts_model: str, sample_rate: int = 16000) -> None:
        self.asr_model = asr_model
        self.tts_model = tts_model
        self.sample_rate = sample_rate
        self._asr = self._load_asr()
        self._tts = self._load_tts()

    def _load_asr(self) -> Any:
        try:
            from vosk import Model, KaldiRecognizer  # type: ignore  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "AudioEngine needs the 'vosk' package and a model. "
                "Install vosk and set voice.asr_model, or use the default text engine."
            ) from exc
        from vosk import Model  # type: ignore

        return Model(self.asr_model)

    def _load_tts(self) -> Any:
        try:
            import piper  # type: ignore  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "AudioEngine needs a TTS backend (e.g. 'piper'). "
                "Install it and set voice.tts_model, or use the default text engine."
            ) from exc
        import piper  # type: ignore

        return piper.PiperVoice.load(self.tts_model)

    def capture(self, prompt_text: str | None = None) -> str | None:  # pragma: no cover
        # Real implementation records from the mic and streams to the recognizer.
        # Left as an integration point; requires sounddevice/pyaudio + the model.
        raise NotImplementedError("wire AudioEngine.capture to your audio input")

    def speak(self, text: str) -> None:  # pragma: no cover
        raise NotImplementedError("wire AudioEngine.speak to your audio output")


def build_engine(spec: dict[str, Any]):
    """Factory used by droid-voice from config (spec §15-style provider neutrality)."""
    from .voice import TextModeEngine

    kind = (spec or {}).get("engine", "text")
    if kind == "text":
        return TextModeEngine()
    if kind == "audio":
        return AudioEngine(
            asr_model=spec.get("asr_model", ""),
            tts_model=spec.get("tts_model", ""),
            sample_rate=int(spec.get("sample_rate", 16000)),
        )
    return TextModeEngine()
