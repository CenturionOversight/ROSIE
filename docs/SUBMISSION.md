# Devpost Submission Draft

This document is prepared submission content for the AWS **Agents for Humans Hackathon**. It is not itself the submitted Devpost entry.

## Project title

ROSIE

## Track

**Professional Agents**

## Short description

ROSIE is a local-machine execution and verification runtime that lets Strands Agents perform real software work through explicit human approval boundaries and truthful local evidence.

## Problem

Agentic software systems can plan and generate work in the cloud, but the final mile is different: software has to land on a real machine, execute in the intended workspace, respect local authority, and report what actually happened.

That local boundary is where trust breaks down if the agent bypasses approval, rewrites the delivered artifact, runs in the wrong directory, or reports success without real execution evidence.

ROSIE is built for that boundary.

## Who it is for

ROSIE is for developers and teams using autonomous or semi-autonomous software agents who need those agents to operate on a real local workspace without giving up control over machine authority.

## What it does

ROSIE receives a delivered software build, binds the runtime to the selected local workspace, exposes ROSIE-owned local capabilities to Strands Agents, and preserves the human approval boundary for consequential shell execution.

For the hackathon demo, HACKASS is the pre-existing upstream builder. ROSIE is the newly built local-agent layer.

```text
HACKASS
→ BuildPrint / deterministic delivery
→ ROSIE local workspace
→ Strands Agents
→ Amazon Nova Micro / Bedrock
→ ROSIE tool dispatch
→ explicit shell approval
→ proof execution + declared test command
→ truthful result returned upstream
```

## How Strands is used

Strands Agents is not a decorative wrapper around a fixed subprocess.

After delivery, the Strands agent receives ROSIE capabilities and chooses how to inspect and execute inside the bound workspace. In the verified live path it uses tools such as:

- `rosie_inspect_git_status`
- `rosie_run_shell`

The execution still goes through ROSIE-owned dispatch and approval semantics.

## Declared test-command verification

The BuildPrint can declare the project's verification command, for example:

```text
python -m pytest
```

That command is carried as build metadata without changing the frozen artifact hash. After delivery, Strands runs the declared verification through ROSIE in the same local workspace.

The resulting stdout, stderr, exit code, timeout state, and pass/fail status are surfaced truthfully.

## Human control

The demonstrated policy is `auto-write`:

- file writes may be automatically approved;
- shell commands still require explicit human approval.

The live proof used real approval prompts and explicit `y` confirmation. It did not use `yolo`.

## Deterministic-delivery invariant

ROSIE does not let Strands rewrite the delivered software during verification.

The delivered artifact bytes remain authoritative. Strands operates after materialization to answer a different question: what happens when this exact delivered software is executed and tested locally?

## AWS technology

- **Strands Agents** — agent framework
- **Amazon Bedrock** — model runtime
- **Amazon Nova Micro** — `us.amazon.nova-micro-v1:0` in the verified live path

## Live proof

The verified live integration demonstrated:

- deterministic local delivery into the selected workspace;
- Strands/Nova operating against that same workspace;
- ROSIE-owned tool selection and dispatch;
- real approval prompts;
- execution of the delivered proof program;
- execution of the BuildPrint-declared test command;
- real pytest output and exit codes; and
- final verification truth surfaced back to the upstream build flow.

The final composite proof passed both verification checks.

## What was built during the hackathon

- ROSIE runtime/session ownership used by the local agent path;
- Strands Agents integration;
- Bedrock / Nova Micro model path;
- ROSIE capability adapters for Strands;
- same-workspace runtime binding;
- post-delivery proof execution;
- BuildPrint-declared test-command execution;
- bounded timeout behavior;
- truthful composite verification results; and
- the end-to-end HACKASS delivery → ROSIE → Strands/Nova demo integration.

## Pre-existing work disclosure

**HACKASS is pre-existing software.**

It is used in the demo as the upstream software-construction and delivery system. It provides the build and BuildPrint metadata that ROSIE receives.

The Agents for Humans contribution is the ROSIE local-agent execution/verification layer and its Strands/AWS integration.

The repository also contains legacy Google hackathon assets from earlier development. Those assets are not represented as new Agents for Humans work and are not the technology path being submitted here.

## Why Professional Agents

ROSIE performs professional software-development work at the local execution boundary: inspecting a real workspace, invoking real tools, running verification commands, preserving approval controls, and returning evidence that can be used by an upstream autonomous builder.

## Challenges

### Preserving local authority

A useful local agent must be capable enough to run real commands without silently turning machine authority over to the model. ROSIE keeps approval enforcement in the execution layer rather than relying only on prompting.

### Preserving artifact identity

Verification must not invalidate the evidence chain by changing the software being tested. The delivered artifact stays frozen while Strands operates as a post-delivery execution/verification layer.

### Correct workspace identity

The delivery workspace, ROSIE RuntimeSession, Strands agent, and shell executor must all refer to the same project location. The submission path binds that workspace explicitly rather than creating a second temporary project copy.

### Truthful failure handling

A failed command, timeout, missing credential, or failed materialization must remain a failure in the evidence chain. ROSIE reports the real result rather than manufacturing a successful completion.

## Accomplishments

- real Strands Agents integration;
- real Amazon Nova Micro turns through Bedrock;
- real local ROSIE tool use;
- real human approval prompts;
- deterministic artifact identity preserved;
- declared project tests executed after delivery;
- stdout and exit codes surfaced as evidence; and
- full end-to-end verification returned to the upstream builder.

## Repository

https://github.com/CenturionOversight/ROSIE

## Demo video

Pending recording/upload. Maximum five minutes.

Recommended demo spine:

1. state the local-agent problem;
2. show HACKASS producing/delivering a build;
3. show ROSIE attached to the local workspace;
4. show Strands/Nova selecting ROSIE execution capability;
5. show the real approval boundary;
6. show proof execution;
7. show the declared pytest command and real passing output; and
8. show the verification result returned upstream.

## Architecture diagram

See [ARCHITECTURE.md](ARCHITECTURE.md).

## Submission checklist

- [x] public repository
- [x] MIT license
- [x] Strands Agents in the execution path
- [x] Amazon Bedrock / Nova Micro verified live
- [x] pre-existing HACKASS disclosed
- [x] README/setup documentation updated
- [ ] publish the current Strands branch as the submission/default repository state
- [ ] finalize architecture diagram asset
- [ ] record/upload public demo video
- [ ] add video URL
- [ ] enter AWS Builder ID email
- [ ] finalize Devpost fields
- [ ] submit before deadline
