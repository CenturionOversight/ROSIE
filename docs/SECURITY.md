# Security Boundaries

ROSIE is the local-machine bridge/runtime. When ROSIE is attached to a machine, it is the layer where higher-level engineering work can become real local execution.

Its current safety model is based on explicit workspace boundaries for bounded file tools, validated tool arguments, and human approval for mutating actions unless the user deliberately selects a more permissive policy.

This document describes the current local runtime. It does not imply that the deployed hackathon Cloud Run service can reach a separate user's machine without an implemented and verified ROSIE connection.

## File-path boundary

The explicit file tools use safe path resolution against the configured workspace root.

Protected local operations include workspace discovery, file inspection, write previews, file writes, patches, and path-filtered Git inspection.

A resolved path outside the configured workspace is rejected.

This blocks ordinary `..` traversal and absolute-path escape through those bounded tool interfaces.

## Shell boundary

`run_shell` is different.

The workspace is the command's starting directory, not a filesystem sandbox.

A shell command can access locations outside the workspace when the operating-system identity running ROSIE has permission to do so.

Treat shell approval accordingly.

## Approval boundary

Mutating local actions consult the active `ApprovalPolicy` before executing.

Default behavior is `ask`.

`auto-write` automatically approves file mutations but not shell commands.

`yolo` automatically approves both.

See [APPROVAL_MODES.md](APPROVAL_MODES.md).

## Higher-level system boundary

HACKASS and ARCHESTRATOR sit above ROSIE in the complete product architecture.

```text
HACKASS
  ↓
ARCHESTRATOR
  ↓
ROSIE local authority boundary
  ↓
local machine
```

A request arriving from a higher-level system does not itself create local authority. Local action remains subject to the ROSIE execution and approval boundaries configured on that machine.

## Argument validation

Tool arguments are validated with Pydantic models before executable functions are called.

Unexpected fields are rejected where the tool model forbids them.

Unknown tool names are rejected by `dispatch_tool()`.

Validation prevents malformed model output from being passed directly into registered Python functions, but it does not make a valid shell command safe.

## Diff previews

File writes and targeted patches provide diff visibility before mutation in approval modes where the operator is asked to approve the change.

## Credentials

Provider and service credentials must not be committed to the repository.

Do not commit:

- `.env` files;
- API keys;
- OAuth credentials;
- Google service-account credentials;
- private keys;
- access tokens; or
- provider configuration containing secrets.

Ignore rules are not a substitute for reviewing staged content.

## Operating-system authority

ROSIE executes with the permissions of the operating-system identity that launches the local process.

In particular, shell execution can perform operations available to that identity, including commands outside the configured workspace.

Running ROSIE with elevated operating-system privileges increases the authority available through the local bridge and is not required by the current implementation.

## Web-to-local transport boundary

ROSIE's architectural role includes bridging web-side engineering work to the user's local environment.

That transport must preserve an explicit distinction between:

- a request arriving from the web side;
- the local ROSIE process accepting and translating that request; and
- the actual local action being authorized and executed.

The current Cloud Run hackathon deployment operates against its own runtime workspace. It must not be described as a completed remote-user-machine transport until an attached local ROSIE path has been implemented and verified.

## `yolo` warning

`--yolo` intentionally removes interactive approval for mutating tools.

Use it only when broad autonomous execution is intended and the target environment is appropriate for that level of authority.

## Current non-goals

The current local runtime does not claim to provide:

- OS-level sandboxing;
- container isolation for local shell execution;
- shell-command allowlisting;
- network isolation;
- secret scanning at runtime;
- remote authentication or authorization for a final web-to-local transport;
- multi-user tenancy controls.

Those capabilities should not be inferred from the existing workspace guard or approval policy.
