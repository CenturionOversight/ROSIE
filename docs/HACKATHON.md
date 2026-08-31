# All Things Agentic Hackathon

HACKASS is the project being submitted to Google's 2026 All Things Agentic Hackathon.

This document separates three things that are colocated in the current submission repository but have different responsibilities:

- **HACKASS** — the user-facing program and newly created hackathon project;
- **ARCHESTRATOR** — the pre-existing engineering/execution foundation incorporated into the submission; and
- **ROSIE** — the local-machine bridge/runtime role that translates authorized engineering work into local machine operations.

The names are not interchangeable.

## Competition track

**Taskmaster** is the selected competition track.

HACKASS fits Taskmaster because the user supplies an objective through the HACKASS interface and the system can reason across multiple steps through Google ADK and Gemini, invoke real incorporated execution tools, and return a completed result without the user manually directing every operation.

## Product responsibility chain

The intended software-construction stack is:

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
  local-machine bridge / translation / controlled local action
  ↓
Local machine
```

For this hackathon, the live deployed demo does not yet prove the final web-to-an-external-user-machine ROSIE transport. The Cloud Run service executes against the workspace available inside the deployed runtime.

That distinction must remain explicit in the submission and demo.

## Hackathon provenance

The official rules require projects to be newly created during the Submission Period and require disclosure of pre-existing code incorporated into a project.

For this submission:

- **HACKASS** is the newly created hackathon project.
- **ARCHESTRATOR** is pre-existing software incorporated into HACKASS and disclosed as such.
- **ROSIE** describes the local-machine bridge/runtime responsibility represented by the local action surface in this repository; it is not used to relabel pre-existing ARCHESTRATOR code as hackathon-created work.

## Pre-existing ARCHESTRATOR software

The incorporated pre-existing ARCHESTRATOR foundation includes the local execution capabilities currently exposed through `wrapper/`, including:

- the iterative execution loop and CLI foundation;
- tool execution and dispatch;
- approval policies;
- workspace controls;
- local file inspection and modification;
- shell execution;
- Git inspection;
- provider abstraction through LiteLLM; and
- the existing tests covering that foundation.

These capabilities are disclosed as pre-existing work incorporated into HACKASS.

## Hackathon-created HACKASS work

The hackathon-specific path includes:

- Google ADK integrated as the hackathon agent framework in `hackass/`;
- `gemini-3.7-flash` through Vertex AI;
- the ADK ↔ incorporated ARCHESTRATOR tool bridge;
- focused tests for the Google integration and HTTP boundary;
- `server.py` with the browser-facing `POST /execute` boundary;
- Firebase Hosting routing to Cloud Run;
- the browser HACKASS task interface and result display;
- concurrency protection around shared execution state; and
- the Google Cloud deployment and submission documentation.

## Mandatory Google technology

The submission uses:

1. **Gemini 3.5 or newer** — `gemini-3.7-flash` through Vertex AI;
2. **Google Agent Framework** — Google ADK; and
3. **Google Cloud infrastructure** — Cloud Run, Firebase Hosting, and Artifact Registry.

## Current live hackathon architecture

The currently deployed demo path is:

```text
User
  ↓
HACKASS browser interface
  ↓
Firebase Hosting
  ↓
Cloud Run
  ↓
server.py / POST /execute
  ↓
HACKASS run_hackass()
  ↓
Google ADK
  ↓
Gemini 3.7 Flash / Vertex AI
  ↓
HACKASS bridge
  ↓
incorporated ARCHESTRATOR tool layer
  ↓
workspace available to the Cloud Run runtime
  ↓
result returned to HACKASS/browser
```

This path proves real agent execution and real tool use in the deployed environment.

It does **not** by itself prove remote access to a separate user's personal machine.

## Where ROSIE fits

ROSIE is the locality bridge/runtime.

The final architectural role is:

```text
HACKASS / ARCHESTRATOR on the web side
  ↓
ROSIE connection
  ↓
ROSIE running on the user's machine
  ↓
user-authorized files / Git / shell / tools / runtime
```

The current standalone ROSIE runtime already provides the local capabilities needed on that side: workspace discovery, file operations, Git inspection, shell execution, approval modes, and local execution boundaries.

The web-to-local transport/attachment must only be described as live when that connection has actually been implemented and verified.

## Verified hackathon execution evidence

The current implementation has verified the following execution pattern:

1. the HACKASS path invokes Google ADK;
2. Google ADK uses `gemini-3.7-flash` through Vertex AI;
3. the agent requests real tool actions;
4. the HACKASS bridge delegates those actions into the incorporated ARCHESTRATOR tool dispatch layer;
5. real workspace operations execute in the runtime environment; and
6. the result returns through the browser/API path.

The Taskmaster demo candidate can use a deterministic multi-step objective such as reading the expected test count, running the test suite, comparing expected and actual results, and reporting the outcome.

## Submission artifacts

The submission requires:

- one competition category — **Taskmaster selected**;
- hosted project URL;
- project description and technology summary;
- source repository;
- spin-up instructions;
- architecture diagram;
- public demo video up to four minutes; and
- visible proof that the backend is running on Google Cloud.

## Demo framing

The video should present the architecture in this order:

1. **HACKASS** — this is the program the user talks to;
2. show HACKASS receiving a real objective and completing a multi-step task;
3. identify **ARCHESTRATOR** as the disclosed pre-existing engineering/execution foundation underneath the task path;
4. identify **ROSIE** as the local-machine bridge/runtime direction that carries authorized engineering actions to the machine where the work lives;
5. explicitly state that the current Cloud Run demonstration executes against its deployed runtime workspace rather than claiming an unverified remote-user-machine connection; and
6. show Google Cloud / ADK / Gemini proof.

## Submission checklist

Before the deadline:

- [x] Taskmaster selected;
- [x] HACKASS identified as the user-facing hackathon project;
- [x] ARCHESTRATOR disclosed as pre-existing incorporated software;
- [x] ROSIE responsibility separated from HACKASS and ARCHESTRATOR;
- [x] Gemini path implemented through Vertex AI;
- [x] Google ADK in the execution path;
- [x] Google Cloud infrastructure genuinely used;
- [x] repository available for judging;
- [x] live deployed execution verified;
- [ ] record and publish demo video;
- [ ] add final demo URL;
- [ ] finalize Devpost entry;
- [ ] perform final live verification;
- [ ] submit before deadline; and
- [ ] respect the post-deadline judging freeze.
