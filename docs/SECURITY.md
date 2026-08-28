# Security Boundaries

ROSIE gives a model real local execution capability. Its safety model is based on explicit workspace boundaries for file tools, validated tool arguments, and human approval for mutating actions unless the user selects a more permissive policy.

## File-path boundary

The explicit file tools use `_resolve_safe_path()` to resolve user/model-supplied paths against the configured workspace root.

Protected tools:

- `inspect_file`
- `preview_write_file`
- `write_file`

A resolved path that is outside the workspace root raises `PathTraversalError`.

This blocks ordinary `..` traversal and absolute-path escape through those tool interfaces.

## Shell boundary

`run_shell` is different.

It executes:

```python
subprocess.run(command, shell=True, cwd=<workspace>, ...)
```

The workspace is the command's starting directory, not a filesystem sandbox.

A shell command can access locations outside the workspace when the operating-system account running ROSIE has permission to do so.

Treat shell approval accordingly.

## Approval boundary

`write_file` and `run_shell` consult the active `ApprovalPolicy` before executing.

Default behavior is `ask`, which requires user confirmation for both actions.

`auto-write` automatically approves writes but not shell commands.

`yolo` automatically approves both.

See [APPROVAL_MODES.md](APPROVAL_MODES.md).

## Argument validation

Tool arguments are validated with Pydantic models before the executable function is called.

Unexpected extra fields are forbidden for tools with argument models.

Unknown tool names are rejected by `dispatch_tool()`.

Validation prevents malformed model output from being passed directly into the registered Python function, but it does not make a valid shell command safe.

## Diff previews

`write_file` generates and displays a unified diff before the approval decision.

This gives the operator visibility into proposed file changes in modes where approval is requested.

## Credentials

Provider credentials are expected through environment variables.

Do not commit:

- `.env` files;
- API keys;
- OAuth credentials;
- Google service-account credentials;
- private keys;
- access tokens;
- provider configuration containing secrets.

The repository `.gitignore` excludes common secret and credential patterns, but ignore rules are not a substitute for reviewing staged content.

## Operating-system authority

ROSIE executes with the permissions of the user account that launches it.

In particular, `run_shell` can perform operations available to that account, including Git operations and commands outside the configured workspace.

Running ROSIE with elevated operating-system privileges increases the authority available to the model and is not required by the current implementation.

## `yolo` warning

`--yolo` intentionally removes interactive approval for mutating tools.

Use it only when broad autonomous execution is intended and the target environment is appropriate for that level of authority.

## Current non-goals

The current core does not claim to provide:

- OS-level sandboxing;
- container isolation;
- shell-command allowlisting;
- network isolation;
- secret scanning at runtime;
- remote authentication or authorization;
- multi-user tenancy controls.

Those capabilities should not be inferred from the existing workspace path guard or approval policy.
