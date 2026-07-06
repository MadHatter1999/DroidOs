"""LLM provider interface and implementations (spec §15).

DroidOS is not tied to one model or vendor. The provider interface supports local
models, a local network model server, remote hosted models, multiple fallbacks
and disabled-LLM operation. The model provider is *configuration, not core
architecture*.

Whatever the provider, two invariants hold:
* the proposed intent name must be a *registered* tool or the broker rejects it
  (spec §17), the LLM never gets an arbitrary shell;
* the chain always ends in the deterministic :class:`OfflineProvider`, so essential
  commands keep working when every model is unavailable (spec §16).

Secrets are never stored in the body manifest or exposed to the LLM context
(spec §15); API keys are read from a protected credential source by reference.
"""

from __future__ import annotations

import abc
import json
import os
import urllib.request
from typing import Any

from ..core.errors import ProviderError
from . import offline_parser
from .intent import StructuredIntent


class LLMProvider(abc.ABC):
    name: str = "abstract"
    type: str = "abstract"

    @abc.abstractmethod
    def available(self) -> bool:
        ...

    @abc.abstractmethod
    def generate_structured_intent(
        self, text: str, catalog: list[dict[str, Any]], context: dict[str, Any]
    ) -> StructuredIntent:
        ...

    def generate_response(self, facts: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Optional natural phrasing of already-verified facts. None => use template."""
        return None


class OfflineProvider(LLMProvider):
    """Deterministic provider backed by the rule-based parser (always available)."""

    name = "offline"
    type = "offline"

    def available(self) -> bool:
        return True

    def generate_structured_intent(self, text, catalog, context) -> StructuredIntent:
        intent = offline_parser.parse(text)
        intent.source = "offline"
        return intent


class DisabledProvider(LLMProvider):
    """Explicitly unavailable provider, used to simulate an LLM outage (spec §39)."""

    name = "disabled"
    type = "disabled"

    def available(self) -> bool:
        return False

    def generate_structured_intent(self, text, catalog, context) -> StructuredIntent:
        raise ProviderError("language model disabled")


class OpenAICompatibleProvider(LLMProvider):
    """Talks to an OpenAI-compatible chat endpoint (covers llama.cpp's server and a
    remote compatible HTTP model). Real HTTP via the stdlib; degrades to unavailable
    if the endpoint cannot be reached (spec §16)."""

    type = "compatible_http"

    _SYSTEM = (
        "You are the intent parser for a physical droid. Convert the user's request "
        "into a single JSON object with keys: intent (one of the allowed names), "
        "arguments (object), requires_motion (bool), requested_speed ('cautious' or "
        "'normal'). Only choose an intent from the allowed list. Output JSON only."
    )

    def __init__(self, name: str, spec: dict[str, Any]) -> None:
        self.name = name
        self.endpoint = str(spec.get("endpoint", ""))
        self.model = str(spec.get("model", "default"))
        self.api_key_ref = spec.get("api_key_ref")
        self.timeout = float(spec.get("timeout", 3.0))

    def _api_key(self) -> str | None:
        # Secrets come from a protected source, never the manifest / LLM context.
        if not self.api_key_ref:
            return None
        return os.environ.get(f"DROIDOS_LLM_KEY_{str(self.api_key_ref).upper()}")

    def _http_base(self) -> str | None:
        if self.endpoint.startswith(("http://", "https://")):
            return self.endpoint.rstrip("/")
        # unix-socket endpoints are not reachable via the stdlib in the reference build
        return None

    def available(self) -> bool:
        base = self._http_base()
        if base is None:
            return False
        try:
            req = urllib.request.Request(base + "/v1/models", method="GET")
            key = self._api_key()
            if key:
                req.add_header("Authorization", f"Bearer {key}")
            with urllib.request.urlopen(req, timeout=self.timeout):
                return True
        except Exception:  # noqa: BLE001 - any failure means "not available"
            return False

    def generate_structured_intent(self, text, catalog, context) -> StructuredIntent:
        base = self._http_base()
        if base is None:
            raise ProviderError(f"endpoint {self.endpoint!r} not reachable in reference build")
        allowed = [c["name"] for c in catalog]
        user = json.dumps({"request": text, "allowed_intents": allowed})
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(base + "/v1/chat/completions", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        key = self._api_key()
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"{self.name} request failed: {exc}") from exc
        return self._parse_intent(content, text, allowed)

    @staticmethod
    def _parse_intent(content: str, raw: str, allowed: list[str]) -> StructuredIntent:
        obj = _first_json_object(content)
        if not obj or obj.get("intent") not in allowed:
            # Fall back to the deterministic parser rather than trusting bad output.
            intent = offline_parser.parse(raw)
            intent.source = "llm-fallback"
            return intent
        return StructuredIntent(
            intent=obj["intent"],
            arguments=obj.get("arguments", {}) or {},
            requires_motion=bool(obj.get("requires_motion", False)),
            requested_speed=obj.get("requested_speed", "normal"),
            raw_text=raw,
            source="llm",
            confidence=float(obj.get("confidence", 0.9)),
        )


def build_provider(name: str, spec: dict[str, Any]) -> LLMProvider:
    ptype = (spec or {}).get("type", "offline")
    if ptype == "offline":
        return OfflineProvider()
    if ptype == "disabled":
        return DisabledProvider()
    if ptype in ("llama_cpp", "compatible_http"):
        return OpenAICompatibleProvider(name, spec)
    # unknown provider type -> safe default
    return OfflineProvider()


class ProviderChain:
    """Primary provider with fallbacks, always terminating in OfflineProvider."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        # guarantee an offline terminator
        if not any(isinstance(p, OfflineProvider) for p in providers):
            providers = [*providers, OfflineProvider()]
        self.providers = providers

    def active(self) -> LLMProvider:
        for p in self.providers:
            try:
                if p.available():
                    return p
            except Exception:  # noqa: BLE001
                continue
        return OfflineProvider()

    def generate_structured_intent(self, text, catalog, context) -> StructuredIntent:
        last_error = None
        for p in self.providers:
            try:
                if not p.available():
                    continue
                return p.generate_structured_intent(text, catalog, context)
            except ProviderError as exc:
                last_error = exc
                continue
        # final guaranteed fallback
        intent = offline_parser.parse(text)
        intent.source = "offline"
        return intent

    def degraded(self) -> bool:
        """True when only the offline provider is available (LLM unavailable)."""
        return isinstance(self.active(), OfflineProvider) and len(self.providers) > 1


def _first_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None
