# ROSIE

ROSIE is the local-machine bridge/runtime for the software-construction stack around HACKASS and ARCHESTRATOR.

Its job is locality.

HACKASS is the program the human communicates with. ARCHESTRATOR is the engineering engine that manages the structured build process. ROSIE translates authorized engineering actions into operations the machine where the work lives can actually perform.

```text
Human
  ↓
HACKASS
  intent / conversation / product decisions
  ↓
ARCHESTRATOR
  engineering plan / work / execution state / verification
  ↓
ROSIE
  local-machine bridge / translation / controlled action
  ↓
Local machine
  files / repository / shell / tools / runtime
```

ROSIE does not replace ARCHESTRATOR's engineering process and it is not the user-facing product interface.

## Current implementation

The current ROSIE repository contains a working Python-based local runtime that gives an intelligent system controlled access to a workspace.

That runtime can inspect files, preview and write changes, inspect Git state, run shell commands, and continue across multiple tool calls. It is also usable directly as a standalone CLI for development, testing, and local operation.

The standalone runtime is an implementation of ROSIE's local side, not a claim that ROSIE owns the higher-level HACKASS product conversation or ARCHESTRATOR's engineering lifecycle.

## Current local action surface

ROSIE exposes twelve local tools:

- `list_directory` — list workspace directory contents natively.
- `search_workspace` — search file names and text contents natively (budget-bounded by `max_files`).
- `inspect_file` — read UTF-8 text files with line numbers.
- `preview_write_file` — generate a unified diff without changing disk.
- `write_file` — write or create UTF-8 files after policy approval.
- `apply_patch` — apply a small targeted edit to an existing UTF-8 file after policy approval.
- `move_path` — move (rename) a file or directory within the workspace after policy approval; never overwrites.
- `delete_path` — delete a file, or a directory recursively with `recursive=true`, after policy approval.
- `inspect_git_status` — inspect working-tree status.
- `inspect_git_diff` — inspect staged or unstaged diffs.
- `inspect_git_log` — inspect recent commit history.
- `run_shell` — execute a shell command after policy approval.

Every standalone conversation begins with a compact operating system prompt (`wrapper/system_prompt.py`) that instructs the model to inspect before modifying, prefer native/read-only inspection tools, never invent results, and only claim verified work.

## Local authority and approval

ROSIE supports three execution policies:

- `ask` — prompt before writes and shell commands.
- `auto-write` — automatically approve writes; still prompt for shell commands.
- `yolo` — automatically approve writes and shell commands.

At any approval prompt, choosing `[a]lways` upgrades the current session to `yolo`.

These controls belong close to the local action surface because ROSIE is the layer that crosses from requested engineering work into machine authority.

## Requirements

- Python 3.14+
- `litellm>=1.0.0`
- `pydantic>=2.0.0`
- `google-adk>=1.0.0` for the hackathon HACKASS integration path
- Google Cloud SDK (`gcloud`) for the current Vertex AI / Cloud Run hackathon deployment

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Standalone local quick start

Run ROSIE against the current directory:

```bash
python -m wrapper.cli .
```

Run a one-shot task:

```bash
python -m wrapper.cli /path/to/project "inspect the project and explain the architecture"
```

Automatically approve file writes but continue prompting for shell commands:

```bash
python -m wrapper.cli . --auto-write "run the tests and create a test report"
```

Automatically approve all mutating actions:

```bash
python -m wrapper.cli . --yolo "refactor the project and run the tests"
```

Select a model explicitly:

```bash
python -m wrapper.cli . --model ollama/qwen2.5-coder:7b "inspect this repository"
```

Disable fallback models:

```bash
python -m wrapper.cli . --no-fallback "quick task"
```

## Standalone model access

The standalone ROSIE CLI currently uses LiteLLM as a model-provider abstraction.

The hackathon HACKASS path is different: HACKASS uses Google ADK and Gemini through Vertex AI and delegates authorized actions into the incorporated ARCHESTRATOR/local tool surface.

ROSIE's product role does not depend on ROSIE being the primary reasoning model. Its durable responsibility is translating authorized work into local-machine action.

## Standalone agent loop

For each standalone turn ROSIE:

1. appends the user request to conversation state;
2. calls the active model through LiteLLM with the current tool schemas;
3. executes returned local tool calls;
4. appends tool results to conversation state;
5. calls the model again; and
6. repeats until the model returns a final text response or the iteration cap is reached.

The default maximum is 20 iterations.

Conversation history is compacted deterministically between turns to stay within bounded limits. The compactor does not call another model and preserves the system prompt.

## Tests

Run the complete suite:

```bash
python -m pytest tests/ -v
```

Current verified baseline documented in this repository:

```text
478 collected
474 passed
0 failed
4 skipped
```

The skipped tests require symlink privileges that are unavailable in the
local Windows environment.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Tools](docs/TOOLS.md)
- [Approval modes](docs/APPROVAL_MODES.md)
- [Models and fallback](docs/MODELS.md)
- [Security boundaries](docs/SECURITY.md)
- [Testing](docs/TESTING.md)
- [All Things Agentic hackathon](docs/HACKATHON.md)
- [Devpost submission draft](docs/SUBMISSION.md)

## Repository layout and provenance

This repository currently contains both the ROSIE local runtime and the Google All Things Agentic hackathon integration used to demonstrate HACKASS.

```text
ROSIE/
├── README.md
├── server.py
├── public/                 hackathon web surface
├── hackass/                hackathon-created Google ADK + Gemini path
├── wrapper/                incorporated local execution foundation
├── tests/
└── docs/
```

For hackathon provenance:

- **HACKASS** is the newly created user-facing hackathon project/integration.
- **ARCHESTRATOR** is pre-existing engineering/execution software incorporated into the submission and disclosed as such.
- **ROSIE** is the local-machine bridge/runtime product role represented by the local action surface in this repository.

The names describe different responsibilities even though the hackathon repository temporarily contains code serving all three boundaries.

## Current Google Cloud hackathon deployment

The current hackathon demo uses:

- Firebase Hosting for the browser surface;
- Cloud Run for the containerized HTTP service;
- Artifact Registry for the image;
- Google ADK for the hackathon agent framework; and
- Gemini 3.7 Flash through Vertex AI.

The current deployed execution path is:

```text
Browser / HACKASS interface
  ↓
Firebase Hosting
  ↓
Cloud Run
  ↓
HACKASS Google ADK + Gemini path
  ↓
incorporated ARCHESTRATOR/local tool layer
  ↓
workspace available to the deployed runtime
```

### Important locality boundary

The Cloud Run demo executes against the workspace available inside the deployed runtime.

That is not the same thing as reaching into an end user's separate laptop or desktop over the internet.

ROSIE's product role is the local-machine bridge. A web-to-user-machine path should only be described as live when a ROSIE process is actually attached on that machine and the communication path between the web-side system and ROSIE has been implemented and verified.

This distinction keeps the hackathon demonstration factual while preserving the intended architecture:

```text
HACKASS → ARCHESTRATOR → ROSIE → local machine
```
