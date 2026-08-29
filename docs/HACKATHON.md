# All Things Agentic Hackathon

HACKASS is the project being built for Google's 2026 All Things Agentic Hackathon.

ROSIE is the product identity used outside the hackathon-facing provenance distinction. For the hackathon submission, this document keeps HACKASS separate from the pre-existing ARCHESTRATOR software incorporated into it so the submission accurately discloses prior work.

## Competition track

**Taskmaster** is the selected competition track.

HACKASS fits Taskmaster because it accepts a task, reasons across multiple steps through Google ADK and Gemini 3.5+, invokes real tools through the incorporated ARCHESTRATOR execution layer, and returns the completed result. The submission and demo should emphasize autonomous task completion and real tool execution rather than conversational collaboration or multi-agent fleet behavior.

## Hackathon provenance

The official rules require projects to be newly created during the Submission Period (Aug 3, 2026 – Aug 31, 2026, 5:00pm PT). Standard development tools, frameworks, libraries, starter templates, and AI coding assistants may be used, but other pre-existing code or work incorporated into the Project must be disclosed.

For this submission:

- **HACKASS** is the newly created hackathon project.
- **ARCHESTRATOR** is pre-existing software incorporated into HACKASS and disclosed as such.
- **ROSIE** is the product identity used for the system outside this hackathon provenance boundary.

This distinction exists to keep the hackathon submission history accurate. It does not claim that ARCHESTRATOR was created during the hackathon.

## Pre-existing ARCHESTRATOR software

The incorporated pre-existing ARCHESTRATOR foundation provides:

- `wrapper/cli.py`;
- `wrapper/tools.py`;
- `wrapper/policy.py`;
- the existing iterative local agent loop;
- real tool execution;
- multi-step task completion;
- local file inspection and modification;
- shell execution;
- Git status inspection;
- configurable human approval modes;
- model-provider abstraction through LiteLLM;
- existing LiteLLM provider/fallback behavior;
- generic Gemini access through LiteLLM when configured;
- existing tests covering that core.

These capabilities are disclosed as pre-existing work incorporated into HACKASS. They are not represented as hackathon-created functionality.

## Hackathon-created HACKASS work

The following work has been added during the hackathon:

- Google ADK 2.8.0 integrated as the hackathon-specific execution framework (`hackass/agent.py`, `hackass/bridge.py`);
- `gemini-3.5-flash` via Vertex AI on `rosie-fire`, `asia-northeast1` (`hackass/config.py`);
- ADK ↔ ARCHESTRATOR tool bridge delegating to `wrapper.tools.dispatch_tool()` (`hackass/bridge.py`);
- tests covering the Google integration (`tests/test_hackass_integration.py`) and HTTP boundary (`tests/test_server_execute.py`);
- `server.py` — portable Python HTTP boundary with `POST /execute` endpoint;
- Firebase Hosting `/execute` route forwarding to Cloud Run (`firebase.json`);
- browser interface with enabled input and real result display (`public/`);
- concurrency lock in `server.py` serializing `/execute` to protect shared ARCHESTRATOR state;
- Cloud Run deployment (`rosie-api`, revision `rosie-api-00002-ncf`);
- Firebase Hosting deployment at `https://rosie-fire.web.app`.

## Mandatory hackathon technology

The official 2026 rules require every submission to use:

1. Gemini 3.5 or newer through the Gemini API or Vertex AI — **implemented** (`gemini-3.5-flash` via Vertex AI on `rosie-fire`);
2. at least one Google Agent Framework — **implemented** (Google ADK 2.8.0);
3. at least one Google Cloud infrastructure service — **implemented** (Cloud Run, Firebase Hosting, Artifact Registry).

## Live architecture

The deployed execution chain is:

```text
Browser
  → Firebase Hosting
  → Cloud Run (rosie-api)
  → server.py (POST /execute)
  → HACKASS run_hackass()
  → Google ADK (LlmAgent)
  → Gemini 3.5+ (Vertex AI)
  → ARCHESTRATOR bridge
  → inspect_file, run_shell, write_file, inspect_git_status, preview_write_file
  → workspace (local filesystem)
  → result returned to browser
```

## Verified execution evidence

Real execution has been verified both locally and through the live deployed service:

1. ADK `LlmAgent` created with `gemini-3.5-flash` via Vertex AI;
2. the agent requested real ARCHESTRATOR tools;
3. the bridge delegated requests to `wrapper.tools.dispatch_tool()`;
4. ARCHESTRATOR performed real workspace actions;
5. Gemini used the tool results to produce the final response;
6. the result returned through `POST /execute` to the browser.

The Taskmaster demo candidate verifies multi-step execution by reading the expected test count from `README.md`, running the test suite, comparing expected and actual results, and reporting the outcome.

## Submission artifacts

The current rules call for:

- one selected competition category — **Taskmaster selected**;
- a hosted project URL;
- project description and technology summary;
- a public or private source repository;
- step-by-step spin-up instructions in the root README;
- an architecture diagram;
- a public demo video up to four minutes;
- visible proof in the demo that the backend is running on Google Cloud.

For a private repository, the rules require repository access for the hackathon judging accounts. The submission repository is currently public.

## Currently implemented

- Google ADK 2.8.0 integrated as the hackathon-specific execution framework;
- Gemini 3.5+ (`gemini-3.5-flash`) configured via Vertex AI on `rosie-fire`;
- five ARCHESTRATOR tools bridged to ADK without duplicating their logic;
- `POST /execute` HTTP endpoint in `server.py` calling `run_hackass()`;
- Firebase Hosting `/execute` route forwarding to Cloud Run;
- browser interface with enabled input and real result display;
- concurrency lock serializing `/execute` to protect shared ARCHESTRATOR state;
- real agent execution verified locally and live through `https://rosie-fire.web.app`;
- Cloud Run and Firebase Hosting live and healthy;
- 21 focused HACKASS tests + 16 focused server tests pass; full regression suite passes (154 passed, 1 skipped).

## Currently not implemented

- authentication on the `/execute` endpoint;
- persistent conversation history across requests;
- per-user workspaces;
- demo video;
- final Devpost submission.

## Submission checklist

Before the deadline (Aug 31, 2026, 5:00pm PT):

- [x] Taskmaster selected as the competition track;
- [x] HACKASS clearly identified as the newly created hackathon project;
- [x] ARCHESTRATOR clearly disclosed as pre-existing incorporated software;
- [x] hackathon-created work distinguished from the incorporated ARCHESTRATOR foundation;
- [x] Gemini path implemented (`gemini-3.5-flash` via Vertex AI);
- [x] Google ADK genuinely in the execution path (2.8.0);
- [x] Google Cloud infrastructure genuinely used;
- [x] architecture documentation matches the implemented path;
- [x] repository is public;
- [x] Cloud Run deployment verified live;
- [ ] record and publish demo video (max 4 min) showing live Taskmaster execution + Google Cloud proof;
- [ ] add final demo video URL to submission;
- [ ] create/finalize Devpost entry using `docs/SUBMISSION.md`;
- [ ] perform final pre-submission live check;
- [ ] submit before deadline;
- [ ] respect post-deadline judging freeze.
