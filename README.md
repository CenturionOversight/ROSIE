# ROSIE

ROSIE is a Python-based agentic command-line interface that gives an LLM controlled access to a local workspace. It can inspect files, preview and write changes, inspect Git state, run shell commands, and continue reasoning across multiple tool calls until a task is complete.

The current runtime is deliberately small: LiteLLM handles model access, Pydantic validates tool arguments, and ROSIE owns the execution loop, approval policy, workspace boundary for file tools, and local action layer.

## Current capabilities

ROSIE exposes five tools to the model:

- `inspect_file` — read UTF-8 text files with line numbers.
- `preview_write_file` — generate a unified diff without changing disk.
- `write_file` — write or create UTF-8 files after policy approval.
- `inspect_git_status` — run `git status --short` in the workspace.
- `run_shell` — execute a shell command in the workspace after policy approval.

ROSIE supports three execution policies:

- `ask` — prompt before writes and shell commands.
- `auto-write` — automatically approve writes; still prompt for shell commands.
- `yolo` — automatically approve writes and shell commands.

At any approval prompt, choosing `[a]lways` upgrades the current session to `yolo`.

## Requirements

- Python
- `litellm>=1.0.0`
- `pydantic>=2.0.0`

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

The current development baseline was verified on Python 3.14.6. The repository does not yet declare a formal minimum or maximum Python version.

## Quick start

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

## Model access

ROSIE uses LiteLLM. The default model is:

```text
ollama/qwen2.5-coder:7b
```

The current fallback chain is:

```text
openrouter/deepseek/deepseek-chat
ollama/qwen2.5-coder:7b
```

Provider API keys are read from environment variables by LiteLLM. ROSIE recognizes the presence of:

```text
GEMINI_API_KEY
ANTHROPIC_API_KEY
OPENAI_API_KEY
DEEPSEEK_API_KEY
GROK_API_KEY
XAI_API_KEY
OPENROUTER_API_KEY
```

Do not commit credentials or `.env` files. See [docs/SECURITY.md](docs/SECURITY.md).

## Agent loop

For each turn ROSIE:

1. appends the user request to conversation state;
2. calls the active model through LiteLLM with the current tool schemas;
3. executes any returned tool calls;
4. appends tool results to conversation state;
5. calls the model again;
6. repeats until the model returns a final text response or the iteration cap is reached.

The default maximum is 20 iterations and can be changed with `--max-iterations`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full execution path.

## Tests

Run the complete suite:

```bash
python -m pytest tests/ -v
```

Current verified baseline:

```text
118 discovered
117 passed
0 failed
1 skipped
```

The skipped test is the symlink escape test on Windows.

See [docs/TESTING.md](docs/TESTING.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Tools](docs/TOOLS.md)
- [Approval modes](docs/APPROVAL_MODES.md)
- [Models and fallback](docs/MODELS.md)
- [Security boundaries](docs/SECURITY.md)
- [Testing](docs/TESTING.md)
- [All Things Agentic hackathon](docs/HACKATHON.md)

## Repository layout

```text
ROSIE/
├── README.md
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .firebaserc
├── firebase.json
├── server.py
├── public/
│   └── index.html
├── wrapper/
│   ├── __init__.py
│   ├── cli.py
│   ├── policy.py
│   └── tools.py
├── tests/
│   ├── conftest.py
│   ├── test_agent_loop.py
│   ├── test_cli.py
│   ├── test_completion_fallback.py
│   ├── test_path_traversal.py
│   ├── test_policy.py
│   ├── test_pydantic_models.py
│   └── test_tools.py
└── docs/
```

## Cloud deployment

ROSIE runs as a containerized HTTP service on Google Cloud Run under the `rosie-fire` project.

### Container image

The Docker image is built from `python:3.14-slim`, installs dependencies from `requirements.txt`, and runs `python -m server` as the entrypoint. The server binds to the `PORT` environment variable (default 8080).

### Local container run

```bash
docker build -t rosie .
docker run -p 8080:8080 rosie
curl http://localhost:8080/health
```

### Google Cloud Run service

| Field | Value |
|-------|-------|
| Service name | `rosie-api` |
| Region | `us-central1` |
| Project | `rosie-fire` |
| Image | `us-central1-docker.pkg.dev/rosie-fire/rosie-images/rosie-api` |
| URL | `https://rosie-api-rqcuxs7u6a-uc.a.run.app` |

### Firebase Hosting

Firebase Hosting acts as a static-frontend proxy to Cloud Run. The `/health` route (and future backend routes) is rewritten to the Cloud Run service; all other paths serve static files from `public/`.

Hosting URL: `https://rosie-fire.web.app`

The routing is configured in `firebase.json` using Firebase Hosting's Cloud Run rewrite mechanism. There is no Firebase Functions dependency.

### Deployment

```bash
# Build and push the container image
docker build -t us-central1-docker.pkg.dev/rosie-fire/rosie-images/rosie-api .
docker push us-central1-docker.pkg.dev/rosie-fire/rosie-images/rosie-api

# Deploy to Cloud Run
gcloud run deploy rosie-api \
  --image us-central1-docker.pkg.dev/rosie-fire/rosie-images/rosie-api \
  --project=rosie-fire \
  --region=us-central1 \
  --allow-unauthenticated

# Deploy Firebase Hosting
firebase deploy --only hosting --project rosie-fire
```

### Portability

The ROSIE application code does not depend on any Google-specific runtime APIs for normal operation. Google-specific integration is isolated to:
- `server.py` — the HTTP boundary layer
- `Dockerfile` — the container packaging

The same container can be deployed to any container platform. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture and boundary documentation.

## Web interface

ROSIE has a minimal web interface deployed at `https://rosie-fire.web.app`.

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Static frontend | HTML/CSS/JS (no framework) | Landing page, backend status, reserved interaction area |
| Firebase Hosting | Static host + proxy | Serves static files, proxies `/health` to Cloud Run |
| Cloud Run | `rosie-api` | Containerized Python HTTP server (`server.py`) |
| ROSIE core | `wrapper/` | Agent loop, tools, approval policy |

The web interface currently displays backend connectivity status via the `/health` endpoint. The ROSIE interaction/input area is visually reserved but functionally disabled — browser-based execution is not yet implemented. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the current vs future architecture boundary.
