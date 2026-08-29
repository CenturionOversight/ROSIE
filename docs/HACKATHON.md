# All Things Agentic Hackathon

ROSIE is being prepared for Google's 2026 All Things Agentic Hackathon.

This document separates the existing ROSIE core from hackathon-specific requirements and future integration work.

## Current ROSIE state

The existing core already provides:

- an iterative agent loop;
- real tool execution;
- multi-step task completion;
- local file inspection and modification;
- shell execution;
- Git status inspection;
- configurable human approval modes;
- model-provider abstraction through LiteLLM;
- generic Gemini access through LiteLLM when configured.

The current repository does **not** yet contain a Google Agent Framework integration. The following Google Cloud deployment infrastructure has been established:

- A containerized Python HTTP server (`server.py`) that imports and wraps ROSIE's core
- A Dockerfile producing a portable container image
- Cloud Run deployment under the `rosie-fire` project (`us-central1`, service name `rosie-api`)
- Firebase Hosting (`https://rosie-fire.web.app`) routing `/health` to Cloud Run

The existing Gemini support is generic LiteLLM provider support rather than a Google Agent Framework integration.

## Mandatory hackathon technology

The official 2026 rules require every submission to use:

1. Gemini 3.5 or newer through the Gemini API or Vertex AI;
2. at least one Google Agent Framework:
   - Google ADK,
   - GenAI SDK,
   - Antigravity SDK, or
   - GenKit;
3. at least one Google Cloud infrastructure service, such as Cloud Run, Cloud SQL, Firestore, GKE, or Pub/Sub.

The submission must also provide evidence in the demo that the backend is running on Google Cloud.

## Submission artifacts

The current rules call for:

- one selected competition category;
- a hosted project URL when available (strongly encouraged);
- project description and technology summary;
- a public or private source repository;
- step-by-step spin-up instructions in the root README;
- an architecture diagram;
- a public demo video up to approximately four minutes;
- visible proof in the demo that the backend is running on Google Cloud.

For a private repository, the rules currently require repository access for the hackathon judging accounts specified by Devpost.

## Existing code disclosure

The hackathon FAQ states that submitted projects must be newly created during the submission period, while pre-existing code incorporated into the project must be disclosed.

ROSIE therefore needs a clear boundary between:

### Pre-existing ROSIE core

- `wrapper/cli.py`
- `wrapper/tools.py`
- `wrapper/policy.py`
- existing local agent loop;
- existing tool layer;
- existing approval modes;
- existing LiteLLM provider/fallback behavior;
- existing tests covering that core.

### Hackathon-specific work

Not yet implemented in this repository. This section should be updated as Google Agent Framework, Gemini 3.5+, Google Cloud deployment, and submission/demo-specific integration are added.

## Architecture diagram

The existing core architecture is documented in [ARCHITECTURE.md](ARCHITECTURE.md), including a Mermaid diagram.

The diagram must be updated when the Google-specific execution path is implemented so that the final submission clearly shows how Gemini, the selected Google Agent Framework, ROSIE's execution layer, and Google Cloud infrastructure connect.

## Spin-up instructions

The root [README.md](../README.md) contains the current local ROSIE setup and execution instructions.

Cloud deployment instructions have been added:

```bash
# Build and push
docker build -t us-central1-docker.pkg.dev/rosie-fire/rosie-images/rosie-api .
docker push us-central1-docker.pkg.dev/rosie-fire/rosie-images/rosie-api

# Deploy to Cloud Run
gcloud run deploy rosie-api \
  --image us-central1-docker.pkg.dev/rosie-fire/rosie-images/rosie-api \
  --project=rosie-fire \
  --region=us-central1 \
  --allow-unauthenticated

# Deploy Firebase Hosting (proxy to Cloud Run)
firebase deploy --only hosting --project rosie-fire
```

The service is live at `https://rosie-api-rqcuxs7u6a-uc.a.run.app/health` and proxied through `https://rosie-fire.web.app/health`.

## Current category status

No final competition category is documented here yet. Category selection should reflect the implemented hackathon system rather than being inferred from the existing local core.

## Before submission

Update this document and the README with the actual implemented Google stack, then verify at minimum:

- Gemini version/path is compliant;
- a permitted Google Agent Framework is genuinely in the execution path;
- at least one Google Cloud infrastructure service is genuinely used (Cloud Run ✅, Firebase Hosting ✅, Artifact Registry ✅);
- cloud deployment can be demonstrated live;
- architecture diagram matches reality;
- local/cloud spin-up instructions are reproducible;
- pre-existing versus hackathon-built code is disclosed accurately;
- private-repository judge access is configured if the repository remains private;
- demo video stays within the competition time limit;
- repository state is frozen appropriately for judging.
