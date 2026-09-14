# Testing

ROSIE uses pytest to verify the local runtime, workspace/tool boundaries, approval behavior, runtime ownership, and Strands integration.

## Run the suite

```bash
python -m pytest tests/ -v
```

## Submission-focused verification

The Agents for Humans path has focused tests for:

- `RuntimeSession` workspace ownership;
- concurrent runtime isolation;
- Strands tool bridging;
- ROSIE runtime dispatch through Strands;
- proof-program execution;
- optional BuildPrint-declared test-command execution;
- independent per-check truth merging;
- real exit-code handling;
- bounded watchdog/timeout behavior; and
- backward-compatible behavior when no declared test command is present.

Run the focused Strands verification tests with:

```bash
python -m pytest tests/test_strands_verify.py -v
```

Related focused suites include:

```bash
python -m pytest tests/test_strands_bridge_offline.py -v
python -m pytest tests/test_runtime_session.py -v
python -m pytest tests/test_runtime_concurrency.py -v
```

## What the tests prove

The submission-specific tests verify that:

1. Strands receives ROSIE capabilities rather than bypassing ROSIE;
2. local execution routes through runtime-owned dispatch;
3. the bound workspace is preserved;
4. proof and declared-test checks are independent;
5. non-zero exits remain failures;
6. timeouts remain visible as timeouts; and
7. historical single-check behavior still works when no test command is supplied.

## Live verification

The hackathon evidence is not based only on unit tests.

The end-to-end live path was exercised with real Strands Agents, Amazon Bedrock, Amazon Nova Micro, ROSIE approval prompts, local shell execution, proof-program execution, and declared pytest execution.

The final verified composite lap passed both the proof check and the declared-test check.

## Legacy tests

The repository also contains tests for older standalone and prior hackathon integrations. Those remain useful regression coverage but are not the technology path being submitted for Agents for Humans.

## Verification policy

Use focused tests for isolated changes. Run broader regression at integration, release, and submission boundaries or when a failure indicates wider impact.
