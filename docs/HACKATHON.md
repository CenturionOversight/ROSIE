# All Things Agentic Hackathon

HACKASS is the project being built for Google's 2026 All Things Agentic Hackathon.

ROSIE is the working/product identity used outside the hackathon-facing provenance distinction. For the hackathon submission, this document keeps HACKASS separate from the pre-existing ARCHESTRATOR software incorporated into it so the submission accurately discloses prior work.

## Hackathon provenance

The official rules require projects to be newly created during the Submission Period. Standard development tools, frameworks, libraries, starter templates, and AI coding assistants may be used, but other pre-existing code or work incorporated into the project must be disclosed.

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

The following work has been added during the hackathon project:

- `server.py` — portable Python HTTP boundary around the incorporated execution core;
- `Dockerfile` and `.dockerignore` — portable container packaging;
- Google Cloud Run deployment under project `rosie-fire` in `us-central1`, service `rosie-api`;
- Firebase Hosting deployment at `https://rosie-fire.web.app`;
- Firebase Hosting `/health` routing to the Cloud Run service;
- static browser interface under `public/` using HTML, CSS, and JavaScript;
- live backend-health integration from the browser through `/health`;
- hackathon/cloud deployment documentation and configuration.

The current browser interface reports backend connectivity. Browser-based agent execution has not yet been implemented.

The current repository does **not** yet contain a Google Agent Framework integration. Existing Gemini support remains generic LiteLLM provider support rather than the hackathon-required Google Agent Framework integration.

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

Cloud Run already supplies a Google Cloud infrastructure service for HACKASS. The required Gemini 3.5+ and Google Agent Framework execution path still needs to be implemented and demonstrated.

## Submission artifacts

The current rules call for:

- one selected competition category;
- a hosted project URL when available;
- project description and technology summary;
- a public or private source repository;
- step-by-step spin-up instructions in the root README;
- an architecture diagram;
- a public demo video up to approximately four minutes;
- visible proof in the demo that the backend is running on Google Cloud.

For a private repository, the required judging access must be configured according to the Devpost submission requirements.

## Architecture diagram

The incorporated execution architecture and current hackathon deployment architecture are documented in [ARCHITECTURE.md](ARCHITECTURE.md), including Mermaid diagrams.

The diagram must be updated when the Google-specific execution path is implemented so that the final submission clearly shows how Gemini, the selected Google Agent Framework, HACKASS, the incorporated ARCHESTRATOR execution foundation, and Google Cloud infrastructure connect.

## Spin-up instructions

The root [README.md](../README.md) contains the current local setup and execution instructions.

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

# Deploy Firebase Hosting
firebase deploy --only hosting --project rosie-fire
```

The service is live at `https://rosie-api-rqcuxs7u6a-uc.a.run.app/health` and proxied through `https://rosie-fire.web.app/health`.

## Current category status

No final competition category is documented here yet. Category selection should reflect the implemented HACKASS system rather than being inferred from the incorporated ARCHESTRATOR foundation.

## Before submission

Update this document and the README with the actual implemented Google stack, then verify at minimum:

- HACKASS is clearly identified as the newly created hackathon project;
- ARCHESTRATOR is clearly disclosed as pre-existing incorporated software;
- hackathon-created work is distinguished from the incorporated ARCHESTRATOR foundation;
- Gemini version/path is compliant;
- a permitted Google Agent Framework is genuinely in the execution path;
- at least one Google Cloud infrastructure service is genuinely used (Cloud Run is already deployed);
- cloud deployment can be demonstrated live;
- architecture diagram matches reality;
- local/cloud spin-up instructions are reproducible;
- private-repository judge access is configured if the repository remains private;
- demo video stays within the competition time limit;
- repository and submission state are handled according to the judging-period rules.
