# Devpost Submission Draft

This document is a draft of the submission content for Devpost. Do not submit until Darren approves.

## Project title
HACKASS

## Short description
An autonomous agentic CLI with a browser interface that executes multi-step tasks using Google ADK and Gemini 3.5+, leveraging pre-existing ARCHESTRATOR tooling for real file, shell, and Git operations.

## Problem
Developers and operators need an autonomous agent that can perform real, multi-step tasks in a local or containerized workspace — inspecting files, running shell commands, checking Git state, and making file edits — rather than just conversing in a chat loop.

## What it does
HACKASS accepts a task from the browser or CLI, dispatches it through Google ADK with Gemini 3.5+ (Vertex AI), and uses the ARCHESTRATOR tool layer to inspect files, preview and write changes, inspect Git status, and run shell commands until the task is complete. Results are returned to the user through the browser interface or HTTP API.

## How it works
```
Browser → Firebase Hosting → Cloud Run → server.py → HACKASS run_hackass()
  → Google ADK (LlmAgent) → Gemini 3.5+ (Vertex AI)
  → ARCHESTRATOR bridge → inspect_file, run_shell, write_file, etc.
  → workspace (local filesystem) → result returned to browser
```

## Google technology
- **Gemini 3.5+** — `gemini-3.5-flash` via Vertex AI (model configured in `hackass/config.py`)
- **Google ADK** — version 2.8.0 (agent framework in `hackass/agent.py`)
- **Cloud Run** — containerized HTTP server (`server.py`) on `rosie-api` service
- **Firebase Hosting** — static frontend + proxy for `/health` and `/execute`
- **Vertex AI** — `asia-northeast1` region (gemini-3.5-flash availability)
- **Artifact Registry** — container image storage

## What was built during the hackathon
- Google ADK integration (`hackass/` package)
- Gemini 3.5+ Vertex AI execution path
- ADK ↔ ARCHESTRATOR tool bridge
- `POST /execute` HTTP endpoint
- Firebase Hosting `/execute` route
- Browser interface with task submission
- Concurrency safety lock
- Full test coverage for the integration boundary

## Pre-existing code disclosure
HACKASS incorporates pre-existing ARCHESTRATOR software (`wrapper/` package), including:
- The agent loop and CLI (`wrapper/cli.py`)
- Tool execution layer (`wrapper/tools.py`)
- Approval policies (`wrapper/policy.py`)
- LiteLLM model abstraction

This pre-existing code handles the agent loop, tool dispatch, file/shell/Git operations, and approval modes. HACKASS adds the Google-specific execution path on top of this foundation. See `docs/HACKASS.md` for the full disclosure.

## Challenges
- **Gemini 3.5+ regional availability**: `gemini-3.5-flash` is available in `asia-northeast1` via Vertex AI, not in `us-central1`. Cloud Run remains in `us-central1`; only the Vertex AI region differs.
- **Bridging ADK into ARCHESTRATOR**: ADK manages its own tool calling; the bridge delegates to `dispatch_tool()` to reuse the existing ARCHESTRATOR tools and approval policies without duplicating file, shell, or Git logic.
- **Concurrency safety**: ARCHESTRATOR uses module-level globals for workspace and policy; a `threading.Lock` in `server.py` serializes `/execute` requests to prevent state races.

## Accomplishments
- Real agent execution verified: a browser task was submitted, processed through Google ADK + Gemini 3.5+ + ARCHESTRATOR `inspect_file`, and produced a real response quoting README.md content.
- Full regression suite passes (154 passed, 1 skipped).
- Live deployment at `https://rosie-fire.web.app` with healthy `/health` and working `/execute`.

## What's next
ROSIE continues as the product identity beyond the hackathon. Planned improvements include persistent conversation history, per-user workspaces, and authentication on the `/execute` endpoint.

## Repository
https://github.com/ArchePersona/ROSIE

## Hosted project
https://rosie-fire.web.app

## Demo video
[To be added when recorded — max 4 minutes, English, showing live execution + Google Cloud proof]

## Architecture diagram
See `docs/ARCHITECTURE.md` for the full diagram showing browser → Firebase → Cloud Run → HACKASS → ADK → Gemini → ARCHESTRATOR → tools.
