# Rocky

A typed control layer between a local LLM and Debian.

```
The LLM proposes.
The policy decides.
The executor acts.
The audit log remembers.
```

The LLM never runs raw commands. It proposes typed actions. `policy.py` checks
each action against `capabilities.yaml` and `tool_registry.yaml`. `executor.py`
runs only approved actions as argv arrays, never through a shell. `audit.py`
writes every action, decision, command, and result to SQLite.

## Requirements

Python 3 with the standard library. `sqlite3` ships with Debian's `python3`.
`python3-yaml` is optional; a small fallback parser is built in. A local LLM is
needed only for `rockyctl ask`.

## Use

```sh
chmod +x rockyctl
./rockyctl init                                   # create the SQLite database
./rockyctl capabilities                           # show what is on or off
./rockyctl tools list                             # approved vs dangerous commands
./rockyctl memory add preference "Direct answers."
./rockyctl memory search "direct"
./rockyctl propose action.json                    # validate, decide, run or block
./rockyctl propose action.json --yes              # confirm an ask_user action
./rockyctl audit tail
./rockyctl ask "check disk space"                 # local LLM to typed action
```

## Connecting a local LLM

`ask` finds a local model in this order: environment variables, then
`rocky.conf.json`, then a probe of common ports (11434 for Ollama, 8080 for
llama.cpp, 1234 for LM Studio). Copy the example config and edit it:

```sh
cp rocky.conf.example.json rocky.conf.json
```

Or set environment variables, which take priority:

```sh
export ROCKY_LLM_URL=http://localhost:11434
export ROCKY_LLM_MODEL=llama3
# for an OpenAI-compatible server:
export ROCKY_LLM_API=openai ROCKY_LLM_URL=http://localhost:8080 ROCKY_LLM_KEY=...
```

The `ask` flow is: send the request to the model, read back a typed action, run
it through the policy and executor, then summarize the result. If the model is
not reachable, `ask` says so and the other commands still work without it.

The database path is `ROCKY_DB`, default `rocky.db` next to these files.

## Files

| File | Job |
|------|-----|
| `agent_profile.md` | Rocky behavior and the system prompt |
| `action_schema.json` | shape of a typed action |
| `policy_rules.md` | risk levels and decision rules in prose |
| `capabilities.yaml` | turn abilities on or off |
| `tool_registry.yaml` | allowlisted, dangerous, and forbidden commands |
| `memory_schema.sql` | SQLite tables for memory, actions, tool calls, audit |
| `policy.py` | action to allow, ask_user, or deny |
| `executor.py` | run approved actions with safe argv |
| `memory.py` | SQLite memory read and write |
| `audit.py` | log every action, decision, command, and result |
| `rockyctl` | command-line entry point |
| `packaging/` | build a .deb or a bootable ISO (see below) |

## Packaging

Build a Debian package with `packaging/deb/build-deb.sh`, or a bootable Debian
live ISO with `packaging/iso/build-iso.sh`. To write the ISO to a USB stick or SD
card, see `packaging/BURNING.md`.

## Safety defaults

Only allowlisted read-only commands run without confirmation. Writes, deletes,
network, and privileged actions start disabled in `capabilities.yaml`; enable
them on purpose. `forbidden_patterns` are denied even when a command is
mislabeled. Do not store raw passwords. Store credential references instead, for
example "SSH key exists at protected path".
