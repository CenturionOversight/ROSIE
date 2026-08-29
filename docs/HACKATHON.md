# All Things Agentic Hackathon

HACKASS is the project being built for Google's 2026 All Things Agentic Hackathon.

ROSIE is the product identity used outside the hackathon-facing provenance distinction. For the hackathon submission, this document keeps HACKASS separate from the pre-existing ARCHESTRATOR software incorporated into it so the submission accurately discloses prior work.

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

1. ADK `LlmAgent` created with `gemini-3.5-flash` model via Vertex AI;
2. Agent requested `inspect_file(relative_path="README.md")`;
3. Bridge adapter called `wrapper.tools.dispatch_tool("inspect_file", ...)`;
4. ARCHESTRATOR read the file and returned content;
5. Gemini produced a final response quoting README.md content;
6. Result returned as `{"status": "ok", "result": "..."}` HTTP response via `POST /execute`.

## Submission artifacts

The current rules call for:

- one selected competition category (Taskmaster, Collaborative Partner, or Fortified Enterprise Fleet);
- a hosted project URL;
- project description and technology summary;
- a public or private source repository;
- step-by-step spin-up instructions in the root README;
- an architecture diagram;
- a public demo video up to four minutes;
- visible proof in the demo that the backend is running on Google Cloud.

For a private repository, the rules require repository access for the hackathon judging accounts: `testing@devpost.com` and `cloudhackathons@google.com`.

## Currently implemented

- Google ADK 2.8.0 integrated as the hackathon-specific execution framework;
- Gemini 3.5+ (`gemini-3.5-flash`) configured via Vertex AI on `rosie-fire`;
- Five ARCHESTRATOR tools bridged to ADK without duplicating their logic;
- `POST /execute` HTTP endpoint in `server.py` calling `run_hackass()`;
- Firebase Hosting `/execute` route forwarding to Cloud Run;
- Browser interface with enabled input and real result display;
- Concurrency lock serializes `/execute` to protect shared ARCHESTRATOR state;
- Real agent execution verified locally and live through `https://rosie-fire.web.app`;
- Cloud Run and Firebase Hosting live and healthy;
- 21 focused HACKASS tests + 16 focused server tests pass; full regression suite passes (154 passed, 1 skipped).

## Currently not implemented

- Authentication on the `/execute` endpoint (currently anonymous — acceptable for hackathon demo scope);
- Persistent conversation history across requests (each request is a fresh ADK session);
- Per-user workspaces;
- Demo video (pending recording);
- Devpost submission entry.

## Track selection

No final competition category is selected yet. The three official tracks are:

- **Taskmaster** — multi-step background workflow agent;
- **Collaborative Partner** — clarifying questions and guided interaction;
- **Fortified Enterprise Fleet** — scalable institutional agent network.

HACKASS primarily demonstrates Taskmaster characteristics (autonomous multi-step task execution with real tool use and file/shell actions). Track selection is pending Darren's decision.

## Submission checklist

Before the deadline (Aug 31, 2026, 5:00pm PT):

- [ ] HACKASS is clearly identified as the newly created hackathon project;
- [ ] ARCHESTRATOR is clearly disclosed as pre-existing incorporated software;
- [ ] hackathon-created work is distinguished from the incorporated ARCHESTRATOR foundation;
- [ ] Gemini version/path is compliant (`gemini-3.5-flash` via Vertex AI);
- [ ] Google ADK is genuinely in the execution path (2.8.0);
- [ ] At least one Google Cloud infrastructure service is genuinely used (Cloud Run, Firebase Hosting);
- [ ] Architecture diagram matches reality;
- [ ] Local/cloud spin-up instructions are reproducible;
- [ ] Repository judge access is configured (public or private with `testing@devpost.com` + `cloudhackathons@google.com`);
- [ ] Cloud Run deployment is live and verifiable;
- [ ] Demo video (max 4 min) shows live execution + Google Cloud proof;
- [ ] Devpost submission entry is created with all required fields;
- [ ] Post-deadline freeze rule is respected (no edits after submission period ends).
