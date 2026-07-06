"""``droid-update`` (spec §12.15, §33).

Validates signed update bundles, installs to the inactive A/B slot, requests a
reboot, verifies boot health, and rolls back a failed update automatically. The
running slot is never modified, so a bad update cannot break the live system.

In the reference build the slot model and bundle verification are simulated
(persisted to state), so the whole update/rollback flow runs and is testable. A
production build delegates to RAUC (``meta-droidos/recipes-update/rauc``); the
:class:`RaucAdapter` hook shows where.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from .. import __version__
from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


def _default_state() -> dict[str, Any]:
    return {
        "running_version": __version__,
        "active_slot": "A",
        "slots": {
            "A": {"version": __version__, "healthy": True},
            "B": {"version": None, "healthy": False},
        },
        "next_boot": "A",
        "last_result": "none",
    }


class Update(ManagedService):
    requires = ("safety_gateway",)

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("update", rt)
        self.uinfo: dict[str, Any] = _default_state()

    def _on_configure(self) -> bool:
        self._load()
        return True

    # queries -------------------------------------------------------------- #
    def status(self) -> dict[str, Any]:
        s = self.uinfo
        return {
            "running_version": s["running_version"],
            "active_slot": s["active_slot"],
            "inactive_slot": self._inactive(),
            "next_boot": s["next_boot"],
            "slots": s["slots"],
            "update_available": False,
            "last_result": s["last_result"],
        }

    def _inactive(self) -> str:
        return "B" if self.uinfo["active_slot"] == "A" else "A"

    # verify --------------------------------------------------------------- #
    def verify_bundle(self, path: str) -> tuple[bool, dict[str, Any], str]:
        """Verify a signed update bundle (spec §33 step 1)."""
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            return False, {}, f"cannot read bundle: {exc}"
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return False, {}, f"bundle is not a valid DroidOS bundle: {exc}"
        if doc.get("compatible") != "droidos":
            return False, {}, "bundle is not compatible with DroidOS"
        # checksum over the payload description
        payload = json.dumps(doc.get("payload", {}), sort_keys=True).encode("utf-8")
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        if doc.get("payload_checksum") not in (None, digest):
            return False, doc, "bundle checksum mismatch"
        # signature: production verifies against the keyring; reference checks presence
        if not doc.get("signature"):
            return False, doc, "bundle is not signed"
        return True, doc, "verified"

    # install -------------------------------------------------------------- #
    def install(self, path: str) -> dict[str, Any]:
        ok, doc, reason = self.verify_bundle(path)
        if not ok:
            self.uinfo["last_result"] = f"verify_failed: {reason}"
            self._save()
            return {"ok": False, "reason": reason}
        target = self._inactive()
        version = doc.get("version", "unknown")
        # install into the inactive slot only (spec §33 step 2)
        self.uinfo["slots"][target] = {"version": version, "healthy": False}
        self.uinfo["next_boot"] = target  # mark inactive as next boot target (step 2)
        self.uinfo["last_result"] = f"installed:{version}->{target}"
        self._save()
        self.rt.audit.emit("update", outcome="installed",
                           detail={"version": version, "slot": target})
        return {"ok": True, "slot": target, "version": version, "reboot_required": True}

    # boot health + rollback ----------------------------------------------- #
    def confirm_boot_health(self, healthy: bool) -> dict[str, Any]:
        """Run after booting the new slot (spec §33 steps 4-6)."""
        booted = self.uinfo["next_boot"]
        if healthy:
            self.uinfo["active_slot"] = booted
            self.uinfo["slots"][booted]["healthy"] = True
            self.uinfo["running_version"] = self.uinfo["slots"][booted]["version"] or __version__
            self.uinfo["last_result"] = f"boot_ok:{booted}"
            result = {"ok": True, "active_slot": booted}
        else:
            # automatic rollback to the previous slot (spec §33 step 6)
            previous = "A" if booted == "B" else "B"
            self.uinfo["next_boot"] = previous
            self.uinfo["active_slot"] = previous
            self.uinfo["last_result"] = f"rolled_back_from:{booted}"
            result = {"ok": False, "rolled_back_to": previous}
        self._save()
        self.rt.audit.emit("update", outcome=self.uinfo["last_result"])
        return result

    def rollback(self) -> dict[str, Any]:
        """Manually roll back to the other slot (spec §34)."""
        other = self._inactive()
        if not self.uinfo["slots"][other]["version"]:
            return {"ok": False, "reason": "no alternative slot to roll back to"}
        self.uinfo["active_slot"] = other
        self.uinfo["next_boot"] = other
        self.uinfo["running_version"] = self.uinfo["slots"][other]["version"]
        self.uinfo["last_result"] = f"manual_rollback:{other}"
        self._save()
        return {"ok": True, "active_slot": other}

    # diagnostics ---------------------------------------------------------- #
    def diagnostics(self) -> list[DiagnosticStatus]:
        return [
            DiagnosticStatus(
                name="update/slots",
                level=DiagnosticLevel.OK,
                message=f"running {self.uinfo['running_version']} on slot {self.uinfo['active_slot']}",
                values=self.status(),
            )
        ]

    # persistence ---------------------------------------------------------- #
    def _path(self):
        return self.rt.paths.state_dir / "update.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                self.uinfo = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.uinfo = _default_state()

    def _save(self) -> None:
        try:
            self._path().write_text(json.dumps(self.uinfo, indent=2), encoding="utf-8")
        except OSError:
            pass


class RaucAdapter:  # pragma: no cover - requires rauc + hardware
    """Production hook: drive RAUC instead of the simulated slot model (spec §33)."""

    def install(self, bundle_path: str) -> None:
        import subprocess

        subprocess.run(["rauc", "install", bundle_path], check=True)

    def status(self) -> str:
        import subprocess

        return subprocess.run(["rauc", "status"], capture_output=True, text=True).stdout
