"""``droidctl``, the deterministic administrative interface (spec §13.2).

Does not require an LLM. Scripts and automated tests use ``droidctl``; humans
normally use ``droid``. The natural-language interface is never the only way to
operate or diagnose the machine.

    droidctl status [--json]
    droidctl body show|list|validate|set <id> [--backend sim|physical]
    droidctl safety status|estop|reset
    droidctl diagnostics list [--json]
    droidctl services list
    droidctl boot-report
    droidctl task cancel
    droidctl update status
"""

from __future__ import annotations

import argparse
import sys

from .. import __version__
from ..core.errors import DroidError
from ..system import DroidSystem
from ..util import tabular


def _boot() -> DroidSystem:
    return DroidSystem.boot()


def _status_dict(sys_: DroidSystem) -> dict:
    rt = sys_.rt
    battery = rt.backend.battery() if rt.backend else None
    diag = rt.diagnostics.summary() if rt.diagnostics else {}
    return {
        "name": rt.config.identity.get("name"),
        "version": __version__,
        "state": rt.state.state.value,
        "body": rt.body.body_id if rt.body else None,
        "backend": rt.body.backend_kind if rt.body else None,
        "locomotion_type": rt.body.manifest.locomotion_type if rt.body else None,
        "battery_percent": round(battery.percent, 1) if battery else None,
        "motion_permitted": rt.state.motion_permitted(),
        "readiness": sys_.readiness.state.value,
        "inhibit_reasons": sys_.readiness.inhibit_reasons,
        "safety": rt.safety.status() if rt.safety else {},
        "language_provider": rt.language.active_provider_name(),
        "language_degraded": rt.language.is_degraded(),
        "diagnostics_overall": diag.get("overall"),
        "fault_count": diag.get("fault_count", 0),
    }


def cmd_status(sys_: DroidSystem, args) -> int:
    d = _status_dict(sys_)
    if args.json:
        print(tabular.as_json(d))
        return 0
    print(tabular.kv([
        ("name", d["name"]), ("version", d["version"]), ("state", d["state"]),
        ("body", f'{d["body"]} ({d["backend"]}, {d["locomotion_type"]})'),
        ("battery", f'{d["battery_percent"]}%'),
        ("motion permitted", d["motion_permitted"]),
        ("readiness", d["readiness"]),
        ("language", f'{d["language_provider"]}{" (degraded)" if d["language_degraded"] else ""}'),
        ("diagnostics", f'{d["diagnostics_overall"]} ({d["fault_count"]} fault(s))'),
    ]))
    if d["inhibit_reasons"]:
        print("\nmotion inhibited:")
        for r in d["inhibit_reasons"]:
            print(f"  - {r}")
    return 0


def cmd_body(sys_: DroidSystem, args) -> int:
    rt = sys_.rt
    bm = rt.body_manager
    if args.action == "list":
        for b in bm.available_bodies():
            print(b)
        return 0
    if args.action == "show":
        if args.json:
            print(tabular.as_json(rt.body.to_dict()))
        else:
            b = rt.body
            print(tabular.kv([
                ("body_id", b.body_id), ("name", b.name),
                ("model_family", b.manifest.model_family),
                ("locomotion", b.manifest.locomotion_type),
                ("backend", b.backend_kind),
                ("interface_rev", b.manifest.interface_revision),
                ("locomotion_summary", b.capabilities.locomotion_summary()),
                ("required_sensors", ", ".join(b.required_sensor_ids())),
            ]))
        return 0
    if args.action == "validate":
        issues = rt.body.issues
        if not issues:
            print("body OK: no issues")
            return 0
        print("body issues:")
        for i in issues:
            fatal = "placeholder" not in i
            print(f"  [{'FATAL' if fatal else 'warn '}] {i}")
        return 1 if any("placeholder" not in i for i in issues) else 0
    if args.action == "set":
        if not args.id:
            print("droidctl body set <id> [--backend sim|physical]", file=sys.stderr)
            return 2
        try:
            sel = bm.set_active(args.id, args.backend)
        except DroidError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"active body set to {sel['body_id']} ({sel['backend']}); applies on next boot")
        return 0
    return 2


def cmd_safety(sys_: DroidSystem, args) -> int:
    sg = sys_.rt.safety
    if sg is None:
        print("safety gateway unavailable", file=sys.stderr)
        return 2
    if args.action == "status":
        print(tabular.as_json(sg.status()) if args.json else tabular.kv(sg.status().items()))
        return 0
    if args.action == "estop":
        sg.engage_estop("droidctl")
        print("EMERGENCY STOP engaged; motor power removed")
        return 0
    if args.action == "reset":
        sg.reset_estop()
        print("emergency-stop latch cleared; reboot to re-arm")
        return 0
    return 2


def cmd_diagnostics(sys_: DroidSystem, args) -> int:
    diag = sys_.rt.diagnostics
    items = diag.collect()
    if args.json:
        print(tabular.as_json([d.to_dict() for d in items]))
        return 0
    print(tabular.table(["component", "level", "message"],
                        [[d.name, d.level.label, d.message] for d in items]))
    return 0


def cmd_services(sys_: DroidSystem, args) -> int:
    rows = [[s.name, s.state.value, s.restart_count] for s in sys_.rt.all_services()]
    print(tabular.table(["service", "state", "restarts"], rows))
    return 0


def cmd_boot_report(sys_: DroidSystem, args) -> int:
    sup = sys_.supervisor
    print(tabular.table(["step", "ok", "detail"],
                        [[s.name, "yes" if s.ok else "NO", s.detail] for s in sup.boot_report]))
    return 0


def cmd_task(sys_: DroidSystem, args) -> int:
    if args.action == "cancel":
        ex = sys_.rt.executive
        if ex:
            ex.cancel()
        sys_.rt.motion.stop()
        print("cancel signalled; motion stopped")
        return 0
    return 2


def cmd_update(sys_: DroidSystem, args) -> int:
    updater = sys_.rt.update
    if updater is None:
        print("update service unavailable", file=sys.stderr)
        return 2
    action = getattr(args, "action", "status")
    if action == "install":
        if not args.bundle:
            print("droidctl update install <bundle.json>", file=sys.stderr)
            return 2
        result = updater.install(args.bundle)
        print(tabular.as_json(result) if args.json else tabular.kv(result.items()))
        return 0 if result.get("ok") else 1
    if action == "rollback":
        result = updater.rollback()
        print(tabular.kv(result.items()))
        return 0 if result.get("ok") else 1
    st = updater.status()
    print(tabular.as_json(st) if args.json else tabular.kv([
        ("running_version", st["running_version"]),
        ("active_slot", st["active_slot"]),
        ("next_boot", st["next_boot"]),
        ("update_available", st["update_available"]),
        ("last_result", st["last_result"]),
    ]))
    return 0


def cmd_voice(sys_: DroidSystem, args) -> int:
    v = sys_.rt.voice
    if v is None:
        print("voice service unavailable", file=sys.stderr)
        return 2
    for d in v.diagnostics():
        print(tabular.as_json(d.to_dict()) if args.json else tabular.kv(d.values.items()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="droidctl", description="DroidOS deterministic control")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status"); s.add_argument("--json", action="store_true")
    b = sub.add_parser("body")
    b.add_argument("action", choices=["show", "list", "validate", "set"])
    b.add_argument("id", nargs="?")
    b.add_argument("--backend", choices=["simulation", "physical"])
    b.add_argument("--json", action="store_true")
    sf = sub.add_parser("safety")
    sf.add_argument("action", choices=["status", "estop", "reset"])
    sf.add_argument("--json", action="store_true")
    d = sub.add_parser("diagnostics"); d.add_argument("action", nargs="?", default="list")
    d.add_argument("--json", action="store_true")
    sub.add_parser("services")
    sub.add_parser("boot-report")
    t = sub.add_parser("task"); t.add_argument("action", choices=["cancel"])
    u = sub.add_parser("update")
    u.add_argument("action", nargs="?", default="status", choices=["status", "install", "rollback"])
    u.add_argument("bundle", nargs="?")
    u.add_argument("--json", action="store_true")
    vc = sub.add_parser("voice"); vc.add_argument("action", nargs="?", default="status")
    vc.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        sys_ = _boot()
    except DroidError as exc:
        print(f"droidctl: failed to start: {exc}", file=sys.stderr)
        return 2
    dispatch = {
        "status": cmd_status, "body": cmd_body, "safety": cmd_safety,
        "diagnostics": cmd_diagnostics, "services": cmd_services,
        "boot-report": cmd_boot_report, "task": cmd_task, "update": cmd_update,
        "voice": cmd_voice,
    }
    return dispatch[args.command](sys_, args)


if __name__ == "__main__":
    raise SystemExit(main())
