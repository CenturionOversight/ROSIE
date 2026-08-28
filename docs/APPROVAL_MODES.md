# Approval Modes

ROSIE uses `ApprovalPolicy` in `wrapper/policy.py` to control mutating actions.

## Modes

| Mode | File writes | Shell commands |
|---|---|---|
| `ask` | prompt | prompt |
| `auto-write` | auto-approve | prompt |
| `yolo` | auto-approve | auto-approve |

## `ask`

This is the default mode.

Before `write_file` or `run_shell` executes, ROSIE displays an approval prompt:

```text
[y]es  [N]o  [a]lways
```

- `y` / `yes` approves only the current action.
- `n` / `no` or an empty response denies the action.
- `a` / `always` approves the current action and upgrades the session to `yolo`.

Interrupted approval input is treated as denial.

## `auto-write`

Start with:

```bash
python -m wrapper.cli . --auto-write
```

File writes are automatically approved.

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

Both file writes and shell commands execute without an interactive confirmation prompt.

Because `run_shell` can execute arbitrary shell commands, `yolo` grants the active model broad execution authority within the permissions of the operating-system user running ROSIE.

## Enforcement location

Approval is enforced inside the mutating tool implementations:

- `write_file`
- `run_shell`

The CLI installs the active policy before the tool loop begins.

This keeps the approval decision close to the action being executed instead of relying only on prompt instructions to the model.

## Live escalation

Selecting `[a]lways` at an approval prompt changes the in-memory policy to `yolo` for the rest of the current process/session.

There is currently no live downgrade command. Restart ROSIE with the desired flags to begin a new session in a different mode.
