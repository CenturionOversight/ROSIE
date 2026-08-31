# Testing

ROSIE has an automated pytest suite covering the standalone local runtime, tool behavior, approval and security boundaries, context handling, Git/workspace inspection, PEEP integration, and the HACKASS Google integration path.

Testing here verifies implementation behavior. It does not collapse the product boundaries: HACKASS remains the user-facing program, ARCHESTRATOR the engineering engine, and ROSIE the local-machine bridge/runtime.

## Run the suite

```bash
python -m pytest tests/ -v
```

## Current verified baseline

The current baseline documented by the repository is:

```text
324 discovered
323 passed
0 failed
1 skipped
```

The skipped case is the platform-dependent symlink escape test on Windows.

## Coverage areas

The suite currently covers areas including:

### Standalone local agent loop

- direct final responses;
- iterative tool calls;
- multiple tool calls;
- conversation and tool-result propagation;
- bounded iteration behavior;
- retained final responses;
- deterministic context compaction; and
- operating system prompt behavior.

### Local workspace and file actions

- directory discovery;
- workspace search;
- file inspection;
- write previews;
- full file writes;
- targeted patching;
- path traversal protections; and
- local workspace boundary behavior.

### Git inspection

- working-tree status;
- staged and unstaged diffs;
- recent history;
- path filtering; and
- read-only error handling.

### Approval policy

- `ask`;
- `auto-write`;
- `yolo`;
- prompt decisions;
- live escalation through `[a]lways`; and
- enforcement close to mutating local actions.

### Model/provider boundary

- standalone LiteLLM completion behavior;
- fallback handling;
- provider/runtime failures; and
- tool-schema delivery.

### PEEP and execution visibility

- PEEP shell integration;
- fallback behavior when PEEP is unavailable; and
- visible attachment/fallback reporting.

### HACKASS / Google integration

- Google ADK integration seams;
- Gemini configuration path;
- bridge delegation into the incorporated execution surface; and
- HTTP/browser execution boundary behavior.

## Shared fixtures

Tests reset module-level local workspace, policy, and related runtime state between cases and use temporary workspaces where appropriate.

## Verification policy

Focused tests are appropriate for isolated changes.

Run the full suite at meaningful integration milestones, before a submission or release boundary, and whenever changes touch shared execution, local tools, approval policy, provider behavior, HACKASS integration, or the web/runtime boundary.
