# Testing

ROSIE has an automated pytest suite covering the CLI, agent loop, model fallback, approval policy, tool behavior, Pydantic validation, and path traversal protections.

## Run the suite

```bash
python -m pytest tests/ -v
```

## Current verified baseline

```text
118 discovered
117 passed
0 failed
1 skipped
```

The skipped test is the symlink escape test on Windows.

## Test files

```text
tests/
├── conftest.py
├── test_agent_loop.py
├── test_cli.py
├── test_completion_fallback.py
├── test_path_traversal.py
├── test_policy.py
├── test_pydantic_models.py
└── test_tools.py
```

## Coverage areas

### Agent loop

`test_agent_loop.py` exercises behavior such as:

- direct final text responses;
- a tool call followed by a final response;
- multiple tool calls;
- conversation/tool-result propagation;
- maximum-iteration behavior;
- CLI execution paths with mocked model responses.

### CLI

`test_cli.py` covers parser and CLI behavior, including model and execution-policy flags.

### Completion fallback

`test_completion_fallback.py` covers fallback behavior across LiteLLM/provider failure classes and status codes.

### Path traversal

`test_path_traversal.py` checks workspace path protections, including traversal attempts and the platform-dependent symlink case.

### Approval policy

`test_policy.py` verifies `ask`, `auto-write`, `yolo`, prompt decisions, and live escalation via `[a]lways`.

### Pydantic models

`test_pydantic_models.py` verifies tool argument validation and rejection of invalid/extra values.

### Tools

`test_tools.py` covers the five local tools and their core success/error paths.

## Shared fixtures

`tests/conftest.py` resets ROSIE's module-level workspace and policy state between tests and provides temporary workspaces and each approval-policy mode.

## Dependencies

The runtime dependency file currently declares only:

```text
litellm>=1.0.0
pydantic>=2.0.0
```

`pytest` is therefore currently a development/test environment dependency rather than a dependency declared in `requirements.txt`.

## Verification policy

Focused tests are appropriate for isolated changes. Run the full suite at meaningful integration milestones, before a submission/release boundary, and whenever changes touch shared execution, tool, policy, or provider behavior.
