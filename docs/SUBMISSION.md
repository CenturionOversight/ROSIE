# Devpost Submission Draft

This document is the prepared submission content for Devpost. It is not itself a submitted Devpost entry.

## Project title
HACKASS

## Competition track
**Taskmaster**

HACKASS is entered as a Taskmaster: it accepts an objective, reasons across the work required, invokes real tools, and completes multi-step tasks without requiring the user to manually direct each operation.

## Short description
A Taskmaster agent that uses Google ADK and Gemini 3.5+ to autonomously complete multi-step workspace tasks through real file, shell, and Git operations.

## Problem
AI coding assistants can describe what should be done while leaving the user to perform or supervise each step. HACKASS is built around task completion instead: give it an objective, let the agent determine the required operations, execute those operations through real tools, and return the result.

## What it does
HACKASS accepts a task from the browser or CLI and executes it through Google ADK with Gemini 3.5+ on Vertex AI. Gemini can invoke the incorporated ARCHESTRATOR tool layer to inspect files, preview or write changes, inspect Git state, and run shell commands across multiple steps until the task is complete. The final result is returned through the browser interface or HTTP API.

A representative Taskmaster workflow is:

1. receive an objective;
2. inspect the workspace for the information needed;
3. choose and invoke real tools;
4. use tool results to decide the next step;
5. continue until the objective is resolved;
6. report the completed result.

## How it works

```text
Browser
→ Firebase Hosting
→ Cloud Run
→ server.py / POST /execute
→ HACKASS run_hackass()
→ Google ADK (LlmAgent)
→ Gemini 3.5+ (Vertex AI)
→ HACKASS bridge
→ ARCHESTRATOR tools
→ real workspace actions
→ result returned to browser
```

## Google technology

- **Gemini 3.5+** — `gemini-3.7-flash` via Vertex AI (`hackass/config.py`)
- **Google ADK** — version 2.8.0 (`hackass/agent.py`)
- **Vertex AI** — model execution in `global`
- **Cloud Run** — containerized HTTP service `rosie-api` in `us-central1`
- **Firebase Hosting** — static frontend and proxy for `/health` and `/execute`
- **Artifact Registry** — container image storage

## Why Taskmaster

The implemented system is centered on autonomous execution rather than guided conversation. HACKASS can take a task requiring multiple operations and use real tools to work through it. The user provides the objective; the agent handles the sequence of actions.

The demo is designed to show this directly: HACKASS reads the expected test count from the repository, runs the actual test suite, compares expected and observed results, and reports whether they match. That requires inspection, shell execution, result interpretation, and completion of a verifiable objective.

## What was built during the hackathon

- Google ADK integration in the `hackass/` package
- Gemini 3.5+ Vertex AI execution path
- ADK ↔ ARCHESTRATOR tool bridge
- browser-accessible `POST /execute` HTTP endpoint
- Firebase Hosting `/execute` routing to Cloud Run
- browser task-submission interface
- Cloud Run container deployment
- concurrency protection around shared ARCHESTRATOR execution state
- focused Google integration and HTTP-boundary tests
- hackathon deployment, architecture, provenance, and submission documentation

## Pre-existing code disclosure

HACKASS incorporates pre-existing ARCHESTRATOR software in the `wrapper/` package.

The pre-existing foundation includes:

- the original iterative agent loop and CLI (`wrapper/cli.py`);
- tool execution (`wrapper/tools.py`);
- approval policies (`wrapper/policy.py`);
- file inspection and modification;
- shell execution;
- Git status inspection;
- workspace controls;
- LiteLLM model abstraction and fallback behavior;
- existing tests for that foundation.

These capabilities are disclosed as pre-existing work. HACKASS adds the Google ADK, Gemini 3.5+, cloud, HTTP, browser, integration, and hackathon-specific execution path around that foundation.

See `docs/HACKATHON.md` for the detailed provenance record.

## Challenges

### Gemini regional availability

`gemini-3.7-flash` is configured through Vertex AI in `global`; the Cloud Run service remains in `us-central1`. Keeping model configuration isolated from the portable execution layer allowed those deployment regions to differ without moving the core application.

### Bridging ADK into an existing execution layer

Google ADK manages agent/model tool calling, while ARCHESTRATOR already owned the real file, shell, Git, approval, and workspace operations. The HACKASS bridge delegates ADK tool requests to `wrapper.tools.dispatch_tool()` rather than duplicating the pre-existing execution logic.

### Shared execution state

ARCHESTRATOR uses module-level workspace and policy state. The browser-facing Cloud Run server uses an execution lock to serialize `/execute` requests and avoid concurrent requests racing over that shared state.

## Accomplishments

- real browser-to-agent execution is live;
- Google ADK and Gemini 3.5+ are genuinely in the execution path;
- real ARCHESTRATOR tools are invoked rather than simulated;
- multi-step Taskmaster behavior has been exercised through the live endpoint;
- the full regression suite passes: 154 passed, 1 skipped;
- the public application is live through Firebase Hosting with Cloud Run behind it.

## What was learned

The important integration problem was not adding another agent loop. It was giving Google ADK and Gemini access to an existing action layer without duplicating or replacing that layer. Keeping the HACKASS bridge narrow preserved the pre-existing ARCHESTRATOR execution behavior while making the Google-specific path explicit and independently testable.

The deployment also reinforced the value of separating application, model, and hosting boundaries: Cloud Run can host the portable HTTP service while Vertex AI model availability is configured independently.

## What's next

After the hackathon, the combined product direction is ROSIE. Future work can add persistent sessions, per-user workspaces, authentication, and broader execution surfaces while retaining the same task-oriented model: give the system an objective and let it do the work.

## Repository

https://github.com/ArchePersona/ROSIE

## Hosted project

https://rosie-fire.web.app

## Demo video

**Pending recording/upload.** Maximum four minutes. The planned demo centers on a real multi-step Taskmaster objective and includes visible Google Cloud proof.

### Planned live demo task

> Read the README.md file, find the expected test count, then run the test suite and verify the results match. Report what you found.

Expected proof:

- `inspect_file` reads the documented expectation;
- `run_shell` runs the real test suite;
- Gemini compares the actual result with the documented result;
- HACKASS reports whether they match;
- the result returns through the deployed browser path.

### Demo timing target

- **0:00–0:20** — problem: assistants talk; Taskmaster completes the task
- **0:20–0:40** — architecture and explicit ARCHESTRATOR pre-existing-code disclosure
- **0:40–2:30** — submit the live multi-step task and show the real result
- **2:30–3:10** — show Cloud Run / Google Cloud proof and identify ADK + Gemini
- **3:10–3:35** — briefly distinguish HACKASS hackathon work from ARCHESTRATOR
- **3:35–3:50** — close

## Architecture diagram

See `docs/ARCHITECTURE.md` for the architecture showing:

Browser → Firebase Hosting → Cloud Run → HACKASS → Google ADK → Gemini 3.5+ → ARCHESTRATOR → tools/actions.

## Final submission checklist

- [x] Taskmaster selected
- [x] Google ADK integrated
- [x] Gemini 3.5+ integrated
- [x] Google Cloud infrastructure live
- [x] browser execution live
- [x] ARCHESTRATOR pre-existing code disclosed
- [x] public repository available
- [x] spin-up instructions documented
- [x] architecture documented
- [ ] record demo video
- [ ] upload public demo video
- [ ] add demo URL here and to Devpost
- [ ] perform final live verification
- [ ] paste/finalize Devpost fields
- [ ] submit before deadline
- [ ] freeze submitted repo/app/submission during judging as required
