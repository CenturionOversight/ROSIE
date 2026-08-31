# Devpost Submission Draft

This document is prepared submission content for Devpost. It is not itself a submitted Devpost entry.

## Project title

HACKASS

## Competition track

**Taskmaster**

HACKASS is the user-facing software-creation program. The user supplies intent or an objective in ordinary language; HACKASS carries that request into an agentic engineering stack capable of performing real multi-step work rather than requiring the user to manually direct every operation.

## Short description

A user-facing software-creation system that uses Google ADK and Gemini to turn ordinary human intent into multi-step engineering action through a structured execution stack.

## Problem

People should not need to think like software engineers before they can make software.

Most AI coding systems still expose the machinery of software construction to the user: implementation details, terminal operations, file manipulation, frameworks, deployment choices, or a long conversation in which the user effectively becomes the orchestrator.

HACKASS moves the human boundary upward.

The user tells HACKASS what they want. HACKASS carries the human-facing conversation and product decisions. The engineering and machine-action responsibilities are separated underneath it.

## What it does

HACKASS accepts an objective from the browser and executes multi-step work through Google ADK with Gemini 3.7 Flash on Vertex AI.

The broader responsibility chain is:

```text
Human
  ↓
HACKASS
  intent / conversation / product decisions
  ↓
ARCHESTRATOR
  engineering process / work / execution state / verification
  ↓
ROSIE
  local-machine bridge / translation / controlled local action
  ↓
Local machine
```

For the current hackathon implementation, HACKASS delegates tool requests into disclosed pre-existing ARCHESTRATOR execution capabilities incorporated in the submission repository.

ROSIE is the local-machine bridge/runtime role: the layer that translates authorized engineering work into file, Git, shell, workspace, and runtime operations on the machine where the work lives.

## Current hackathon execution path

```text
User
→ HACKASS browser interface
→ Firebase Hosting
→ Cloud Run
→ server.py / POST /execute
→ HACKASS run_hackass()
→ Google ADK
→ Gemini 3.7 Flash / Vertex AI
→ HACKASS bridge
→ incorporated ARCHESTRATOR tool layer
→ workspace available to deployed runtime
→ result returned to HACKASS/browser
```

The current Cloud Run demo operates on the workspace available inside the deployed runtime. It should not be represented as remotely controlling an unrelated user's laptop or desktop.

The final ROSIE web-to-local role is the architectural bridge for that separate locality problem; that transport should only be described as live after it is implemented and verified.

## Representative Taskmaster workflow

1. the user gives HACKASS an objective;
2. the system inspects the workspace for what it needs;
3. Gemini selects and invokes real tools through Google ADK;
4. tool results feed the next step;
5. the system continues until the objective is resolved; and
6. HACKASS returns the completed result to the user.

## Google technology

- **Gemini** — `gemini-3.7-flash` through Vertex AI
- **Google ADK** — hackathon agent framework
- **Vertex AI** — Gemini model execution
- **Cloud Run** — containerized HTTP execution service
- **Firebase Hosting** — browser surface and proxy for `/health` and `/execute`
- **Artifact Registry** — container image storage

## Why Taskmaster

The implemented hackathon path is centered on autonomous task completion rather than guided conversation.

The user supplies the objective. HACKASS and the execution stack handle the sequence of operations needed to complete it.

A demo objective can require the system to inspect repository information, execute a real command, interpret the result, compare it against an expected condition, and report whether the objective was satisfied.

## System responsibilities

### HACKASS — user-facing program

HACKASS is where the human communicates with the system.

It is responsible for carrying ordinary-language intent and product decisions into software work without requiring the human to operate the engineering machinery directly.

### ARCHESTRATOR — engineering engine

ARCHESTRATOR is the structured engineering layer underneath HACKASS.

It is pre-existing software incorporated into this hackathon project and disclosed as such.

Its responsibility is the engineering process around software construction rather than the human-facing product conversation.

### ROSIE — local-machine bridge/runtime

ROSIE is the locality layer.

It translates authorized engineering actions into capabilities on the machine where the work lives, including workspace discovery, files, Git, shell, and other local actions.

The current repository includes the local action surface used in the hackathon integration, but the deployed Cloud Run demo should not be confused with a completed transport to an external end-user machine.

## What was built during the hackathon

- Google ADK integration in the `hackass/` package;
- Gemini 3.7 Flash Vertex AI execution path;
- ADK ↔ incorporated ARCHESTRATOR tool bridge;
- browser-accessible `POST /execute` HTTP endpoint;
- Firebase Hosting `/execute` routing to Cloud Run;
- browser HACKASS task-submission interface;
- Cloud Run container deployment;
- concurrency protection around shared execution state;
- focused Google integration and HTTP-boundary tests; and
- hackathon deployment, architecture, provenance, and submission documentation.

## Pre-existing code disclosure

HACKASS incorporates pre-existing ARCHESTRATOR software in the `wrapper/` package.

The disclosed foundation includes the iterative execution loop, tool execution, approval policies, file and workspace operations, shell execution, Git inspection, provider abstraction, and existing tests around that foundation.

These capabilities are not represented as work created during the hackathon.

The hackathon-created HACKASS layer adds the Google ADK, Gemini, HTTP, browser, bridge, cloud deployment, and submission-specific path around the disclosed foundation.

See `docs/HACKATHON.md` for the detailed provenance record.

## Challenges

### Keeping the product boundary above the engineering machinery

The user-facing problem is not simply tool calling. HACKASS needs to let a person communicate in product intent while keeping engineering state and machine authority in separate layers underneath it.

### Bridging Google ADK into an existing engineering foundation

Google ADK manages the hackathon agent/model path, while the incorporated ARCHESTRATOR foundation already owns real execution capabilities. The HACKASS bridge delegates tool requests rather than duplicating the execution logic.

### Locality

A cloud process can operate its own runtime workspace, but that is not the same as operating the user's separate local machine.

ROSIE exists for that locality boundary: it is the local bridge/runtime that can expose authorized machine capabilities without making the cloud application itself the local execution authority.

### Shared execution state

The current incorporated execution layer uses shared process state for workspace and policy configuration. The browser-facing server serializes `/execute` operations to prevent concurrent requests from racing over that state.

## Accomplishments

- HACKASS provides a live browser-facing task surface;
- Google ADK and Gemini are genuinely in the execution path;
- real tools are invoked rather than simulated;
- multi-step Taskmaster behavior works through the deployed endpoint;
- the pre-existing ARCHESTRATOR boundary is explicitly disclosed; and
- the product architecture now separates HACKASS, ARCHESTRATOR, and ROSIE by responsibility.

## What was learned

The important problem is not adding another chat agent.

The system becomes more useful when the boundaries are explicit:

- the human should communicate with a product layer;
- engineering state should live in an engineering layer; and
- machine authority should cross through a locality layer designed for that job.

That separation makes the model one source of intelligence inside a larger software-construction system rather than forcing the model, the engineering process, the user interface, and the local machine into one component.

## What's next

The next architectural step is to complete the ROSIE web-to-local attachment so HACKASS and ARCHESTRATOR can hand authorized engineering work to a ROSIE process running on the user's actual machine while preserving local approval and workspace boundaries.

## Repository

https://github.com/ArchePersona/ROSIE

## Hosted project

https://rosie-fire.web.app

## Demo video

**Pending recording/upload.** Maximum four minutes.

The demo should establish HACKASS as the program the user is interacting with, show one real multi-step Taskmaster objective completing, identify the disclosed ARCHESTRATOR engineering/execution foundation, briefly explain ROSIE as the local-machine bridge/runtime, and show clear Google Cloud / ADK / Gemini proof.

### Planned live demo task

A safe deterministic example is:

> Read the README.md file, find the expected test count, then run the test suite and verify the results match. Report what you found.

This demonstrates inspection, real execution, interpretation, and completion without requiring the video to claim an unverified external-machine connection.

## Architecture diagram

See `docs/ARCHITECTURE.md`.

The responsibility architecture is:

```text
HACKASS → ARCHESTRATOR → ROSIE → local machine
```

The current hackathon deployment path is separately documented so the submission does not confuse product architecture with the current Cloud Run runtime boundary.

## Final submission checklist

- [x] Taskmaster selected
- [x] Google ADK integrated
- [x] Gemini 3.7 Flash integrated
- [x] Google Cloud infrastructure live
- [x] browser execution live
- [x] ARCHESTRATOR pre-existing code disclosed
- [x] HACKASS / ARCHESTRATOR / ROSIE responsibilities documented
- [x] current Cloud Run locality limitation documented
- [x] public repository available
- [x] architecture documented
- [ ] record demo video
- [ ] upload public demo video
- [ ] add demo URL here and to Devpost
- [ ] perform final live verification
- [ ] paste/finalize Devpost fields
- [ ] submit before deadline
- [ ] freeze submitted repo/app/submission during judging as required
