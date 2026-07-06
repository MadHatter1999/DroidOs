"""``droid``, the natural-language interface (spec §13.1).

Accepts ordinary English and returns an English response. Runs a single command
when given arguments, or an interactive conversation when run with none. The same
command broker validates voice and typed input, so this CLI is a thin shell over
:meth:`LanguageService.process`.

    droid "What can you see?"
    droid do "Walk to the workshop."
    droid explain "Why did the previous task fail?"
    droid remember "This shelf contains networking equipment."
    droid                       # interactive session
"""

from __future__ import annotations

import sys

from ..core.errors import DroidError
from ..system import DroidSystem

MODES = {"ask", "do", "explain", "remember", "forget"}


def _apply_mode(mode: str, text: str) -> str:
    if mode in ("remember", "forget") and not text.lower().startswith(mode):
        return f"{mode} {text}"
    return text


def _banner(sys_: DroidSystem) -> str:
    rt = sys_.rt
    perm = "available" if rt.state.motion_permitted() else "unavailable"
    return (
        "DroidOS interactive interface\n"
        f"Body: {rt.body.body_id if rt.body else 'none'}\n"
        f"State: {rt.state.state.value}\n"
        f"Language service: {rt.language.active_provider_name()}"
        f"{' (advanced model unavailable)' if rt.language.is_degraded() else ''}\n"
        f"Motion permission: {perm}\n"
    )


def run_once(text: str, user: str, confirm: bool) -> int:
    try:
        sys_ = DroidSystem.boot()
    except DroidError as exc:
        print(f"droid: failed to start: {exc}", file=sys.stderr)
        return 2
    resp = sys_.rt.language.process(text, user, confirmed=confirm)
    if resp.text:
        print(resp.text)
    if resp.needs_confirmation:
        print("(re-run with --yes to confirm, or use interactive mode)", file=sys.stderr)
        return 3
    return 0 if resp.outcome in ("approved", "cancelled") else 1


def interactive(user: str) -> int:
    try:
        sys_ = DroidSystem.boot()
    except DroidError as exc:
        print(f"droid: failed to start: {exc}", file=sys.stderr)
        return 2
    print(_banner(sys_))
    pending = None
    while True:
        try:
            line = input("DROID> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", ":q"):
            break
        resp = sys_.rt.language.process(line, user, pending=pending)
        pending = resp.pending if resp.needs_confirmation else None
        if resp.text:
            print(resp.text)
    return 0


def voice_interactive(user: str) -> int:
    """Simulated voice session (spec §12.12): typed lines are treated as speech and
    routed through wake-word + emergency detection before the language service."""
    try:
        sys_ = DroidSystem.boot()
    except DroidError as exc:
        print(f"droid: failed to start: {exc}", file=sys.stderr)
        return 2
    v = sys_.rt.voice
    names = "/".join(v.wake_names)
    print(f"DroidOS voice interface (say '{names}'). Ctrl-D to exit.")
    print(f"Wake word required: {v.require_wake}. Emergency words work anytime.\n")
    while True:
        try:
            heard = input("voice> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not heard:
            continue
        result = v.handle_utterance(heard, None)
        if not result.woke and not result.emergency:
            print("(no wake word, ignored)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    user = "operator"
    confirm = False
    voice = False
    # extract flags
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--user" and i + 1 < len(argv):
            user = argv[i + 1]
            i += 2
            continue
        if a in ("--yes", "-y"):
            confirm = True
            i += 1
            continue
        if a == "--voice":
            voice = True
            i += 1
            continue
        if a in ("-h", "--help"):
            print(__doc__)
            return 0
        rest.append(a)
        i += 1

    if voice:
        return voice_interactive(user)
    if not rest:
        return interactive(user)

    mode = ""
    if rest[0] in MODES and len(rest) > 1:
        mode = rest.pop(0)
    text = " ".join(rest)
    if mode:
        text = _apply_mode(mode, text)
    return run_once(text, user, confirm)


if __name__ == "__main__":
    raise SystemExit(main())
