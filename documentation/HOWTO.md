# DroidOS how-to guide

A practical guide to running and using the DroidOS reference brain. For how the
code maps to the spec see [ARCHITECTURE.md](ARCHITECTURE.md); for the path to
hardware see [ROADMAP.md](ROADMAP.md).

---

## 1. Get a Python interpreter

The reference brain needs **Python 3.10+** and has **no third-party dependencies**.

- Recommended: install Python from <https://www.python.org/downloads/> and tick
  "Add python.exe to PATH".
- On this machine there is no `python` on PATH, but a working Python 3.12 ships
  with GIMP at `C:\Program Files\GIMP 3\bin\python.exe`. The launcher scripts below
  find it automatically, so you don't have to install anything to try it.

## 2. Run it (Windows, no install needed)

From the repo root (`c:\Users\TonyHealy\Documents\GitHub\DroidOs`):

```powershell
.\tools\droidctl.ps1 status                 # deterministic status
.\tools\droid.ps1 "What can you see?"        # natural language
.\tools\droid.ps1                            # interactive session
```

These wrappers set `PYTHONPATH` and a writable `run-state\` folder for you and
locate a Python interpreter.

### Or install it as real commands

```powershell
python -m pip install -e .      # from the repo root
droidctl status
droid "What is your status?"
```

After `pip install -e .` the `droid` and `droidctl` commands exist on PATH.

### Or run the modules directly

```powershell
$env:PYTHONPATH = "src"
& "C:\Program Files\GIMP 3\bin\python.exe" -m droidos.cli.droidctl status
& "C:\Program Files\GIMP 3\bin\python.exe" -m droidos.cli.droid "What can you see?"
```

## 3. The two commands

**`droid`**, talk to the droid in English. Humans use this.

```powershell
.\tools\droid.ps1 "What is your current status?"
.\tools\droid.ps1 "How hot are your motors?"
.\tools\droid.ps1 "What is wrong?"
.\tools\droid.ps1 ask "Why is your movement disabled?"
.\tools\droid.ps1 do "Walk to the workshop."
.\tools\droid.ps1 remember "This shelf holds networking equipment."
```

Modes (`ask`, `do`, `explain`, `remember`, `forget`) are optional hints. Motion
commands ask for confirmation first; add `--yes` to auto-confirm, or answer in
interactive mode. Pick who is asking with `--user owner|operator|guest|technician`.

**`droidctl`**, deterministic administration, **no LLM required**. Scripts use this.

```powershell
.\tools\droidctl.ps1 status [--json]
.\tools\droidctl.ps1 body list
.\tools\droidctl.ps1 body show
.\tools\droidctl.ps1 body validate
.\tools\droidctl.ps1 body set r2-mk1 --backend simulation
.\tools\droidctl.ps1 safety status
.\tools\droidctl.ps1 safety estop
.\tools\droidctl.ps1 safety reset
.\tools\droidctl.ps1 diagnostics list [--json]
.\tools\droidctl.ps1 services list
.\tools\droidctl.ps1 boot-report
```

## 4. Interactive session

```
.\tools\droid.ps1

DroidOS interactive interface
Body: ig-mk1
State: READY
Language service: offline (advanced model unavailable)
Motion permission: available

DROID> what can you see?
I can see workbench, two monitors, closed door, server rack; 1 person...
DROID> go to the workshop
This will navigate to a named place (destination=workshop). Confirm? [yes/no]
DROID> yes
I have arrived at workshop.
DROID> quit
```

## 4b. Voice mode (§12.12)

The voice service runs in **text mode** by default (no microphone): typed lines are
treated as speech and routed through wake-word and emergency detection before the
language service. Emergency words work at any time and bypass the LLM.

```powershell
.\tools\droid.ps1 --voice
voice> what can you see
voice> emergency stop        # engages e-stop immediately, no LLM needed
```

Enable a real audio engine (Vosk/whisper ASR + Piper TTS) in `config/droidos.yaml`
under `voice:` and install the optional packages. Speaker identification is a
*hint* only, high-risk actions still require an authenticated role (§32).

## 4c. Updates (A/B slots, §33)

```powershell
.\tools\droidctl.ps1 update status
.\tools\droidctl.ps1 update install path\to\bundle.json   # installs to the inactive slot
.\tools\droidctl.ps1 update rollback                      # switch back to the other slot
```

A bundle is a signed JSON descriptor (`compatible: droidos`, `version`, `payload`,
`payload_checksum`, `signature`). Install goes to the *inactive* slot; boot-health
confirmation promotes it, and a bad boot rolls back automatically.

## 5. Switch bodies (biped ↔ wheeled)

```powershell
.\tools\droidctl.ps1 body set r2-mk1 --backend simulation   # wheeled astromech
.\tools\droid.ps1 "walk upstairs"        # -> honest refusal: cannot traverse stairs
.\tools\droid.ps1 "go to the workshop"   # -> rolls there instead
.\tools\droidctl.ps1 body set ig-mk1     # back to the biped
```

The core brain does not change, only the body package and backend do.

## 6. Try the safety and failure behaviours

```powershell
# Emergency stop latches across "reboot" until reset
.\tools\droidctl.ps1 safety estop
.\tools\droidctl.ps1 status              # state = EMERGENCY_STOPPED
.\tools\droidctl.ps1 safety reset
.\tools\droidctl.ps1 status              # back to READY
```

Fault-injection demos (motor overheat, blocked route, camera dropout, lost
localization, safety-link loss) are driven from Python, see the scenarios in
[`simulation/droidos_sim.yaml`](../simulation/droidos_sim.yaml) and examples in
[`tests/test_integration.py`](../tests/test_integration.py).

## 7. Run the tests

```powershell
$env:PYTHONPATH = "src"
& "C:\Program Files\GIMP 3\bin\python.exe" tests\run_all.py     # zero-dependency runner
# or, if pytest is installed:
python -m pytest -q
```

## 8. Where things live

| You want to… | Look at |
|--------------|---------|
| Change identity / personality / language provider | `config/droidos.yaml` |
| Add/edit users and roles | `config/users.yaml` |
| Add a robot body | `bodies/<id>/` + [BODY_DEVELOPMENT.md](BODY_DEVELOPMENT.md) |
| Understand the state machine | `src/droidos/core/states.py` |
| See how a command is validated | `src/droidos/language/broker.py` |
| See how a task runs | `src/droidos/executive/executive.py` |
| Build a bootable OS image | `tools/build-image.sh` + `meta-droidos*` (needs Yocto host) |

## 9. Reset state

Everything mutable lives under `run-state\` (git-ignored). Delete that folder for a
clean slate (memory, world model, e-stop latch, logs).
