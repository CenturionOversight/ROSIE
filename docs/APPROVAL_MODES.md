# Approval Modes

ROSIE is the layer where authorized engineering work becomes real local-machine action. Its approval policy therefore belongs at the local execution boundary rather than only in a higher-level conversation.

The current standalone/local runtime uses `ApprovalPolicy` in `wrapper/policy.py` to control mutating actions.

## Modes

| Mode | File writes / patches | Shell commands |
|---|---|---|
| `ask` | prompt | prompt |
| `auto-write` | auto-approve | prompt |
| `yolo` | auto-approve | auto-approve |

## `ask`

This is the default mode.

Before a mutating local action executes, ROSIE displays an approval prompt:

```text
[y]es  [N]o  [a]lways
```

- `y` / `yes` approves only the current action.
- `n` / `no` or an empty response denies the action.
- `a` / `always` approves the current action and upgrades the session to `yolo`.

Interrupted approval input is treated as denial.

## `auto-write`

Start standalone ROSIE with:

```bash
python -m wrapper.cli . --auto-write
```

File writes and patches are automatically approved.

Shell commands still require explicit approval.

## `yolo`

Start with:

```bash
python -m wrapper.cli . --yolo
```

or:

```bash
python -m wrapper.cli . -y
```

File mutations and shell commands execute without an interactive confirmation prompt.

Because `run_shell` can execute arbitrary shell commands, `yolo` grants the active reasoning system broad execution authority within the permissions of the operating-system user running ROSIE.

## Enforcement location

Approval is enforced inside the mutating local tool implementations rather than being left to prompt instructions alone.

Current mutating actions include:

- `write_file`;
- `apply_patch`; and
- `run_shell`.

This keeps the human-authority decision close to the machine action being executed.

## Architectural boundary

In the complete stack, HACKASS carries the user-facing conversation and ARCHESTRATOR manages the engineering process.

Neither layer should silently bypass ROSIE's local approval boundary when work reaches the user's machine.

```text
HACKASS / ARCHESTRATOR request
  ↓
ROSIE local approval boundary
  ↓
authorized machine action
```

## Live escalation

Selecting `[a]lways` at an approval prompt changes the in-memory policy to `yolo` for the rest of the current process/session.

There is currently no live downgrade command. Restart standalone ROSIE with the desired flags to begin a new session in a different mode.
