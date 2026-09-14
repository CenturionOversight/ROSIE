# AWS Agents for Humans Hackathon

ROSIE is the project being submitted to the **AWS Agents for Humans Hackathon** in the **Professional Agents** track.

## Submission project

ROSIE is a local-machine execution and verification runtime for agentic software work.

For this hackathon, ROSIE uses **Strands Agents** with **Amazon Nova Micro through Amazon Bedrock** to perform post-delivery local verification through ROSIE-owned tools and a real human approval boundary.

## Product chain

```text
Human
  ↓
HACKASS
  pre-existing upstream software-construction system
  ↓
BuildPrint / deterministic build delivery
  ↓
ROSIE
  local-machine runtime and authority boundary
  ↓
Strands Agents
  ↓
Amazon Nova Micro / Bedrock
  ↓
ROSIE tool dispatch
  ↓
Local workspace / shell / Git / tests
  ↓
verification result returned upstream
```

## Provenance and disclosure

The hackathon rules require disclosure of pre-existing work incorporated into a submission.

### Built during the hackathon window

- ROSIE runtime ownership/session work used by the submission path;
- Strands Agents adapter and tool bridge;
- Amazon Bedrock / Nova Micro integration;
- post-delivery Strands verification;
- declared BuildPrint test-command propagation and execution;
- same-workspace runtime binding from delivery through verification;
- approval-gated shell execution through ROSIE;
- bounded execution/timeout handling;
- truthful per-check stdout, stderr, exit code, and status reporting; and
- the live HACKASS → ROSIE → Strands/Nova integration used for the demo.

### Pre-existing work

**HACKASS** existed before this hackathon and is used as the upstream software-construction and delivery system.

HACKASS is not represented as newly created for this submission. Its role in the demo is to provide the build, BuildPrint metadata, and deterministic delivery that ROSIE receives and verifies locally.

The repository also contains older Google hackathon assets from prior development. Those assets are not the basis of the Agents for Humans submission and should not be confused with the current Strands/AWS path.

## What the live proof demonstrates

The verified live path demonstrates that:

1. HACKASS produces and delivers a build to the selected local workspace;
2. the BuildPrint's declared test command is preserved as build metadata;
3. ROSIE receives the delivered build without changing its authoritative bytes;
4. Strands Agents runs with Amazon Nova Micro through Bedrock;
5. Strands selects ROSIE-owned capabilities rather than bypassing ROSIE;
6. shell execution crosses the real ROSIE approval boundary;
7. the delivered proof program is actually executed;
8. the declared test command is actually executed;
9. real stdout and exit codes are returned; and
10. the verification result is surfaced back to the upstream build flow.

The final verified composite lap completed with both the proof check and declared test-command check passing.

## Deterministic-delivery invariant

Strands does not generate or rewrite the delivered program during verification.

The delivered artifact bytes remain authoritative. Strands is the post-delivery local agentic execution/verification layer.

This keeps two questions separate:

- **What software was delivered?** — answered by the deterministic build/manifest chain.
- **What happened when it was executed locally?** — answered by ROSIE + Strands verification evidence.

## Human approval boundary

The submission does not remove the human from machine authority.

The demonstrated policy is `auto-write`:

- writes may be automatically approved;
- shell commands still require explicit human approval.

The live proof used real `[APPROVAL REQUIRED]` prompts and explicit approval. It did not use `yolo`.

## AWS / Strands technology

The submission uses:

- **Strands Agents** — agent framework;
- **Amazon Bedrock** — model access;
- **Amazon Nova Micro** (`us.amazon.nova-micro-v1:0`) — model used in the verified live path.

## Representative demo

A submission demo should show one real build moving through this sequence:

```text
HACKASS build
→ local delivery
→ ROSIE attached to the selected workspace
→ Strands/Nova chooses ROSIE tools
→ human approves shell execution
→ proof program executes
→ BuildPrint-declared test command executes
→ passing/failing truth is surfaced back to HACKASS
```

The strongest visible evidence is the real local command, approval prompt, pytest output, exit code, and final surfaced verification result.

## Submission requirements

The Devpost submission requires, among other items:

- one track selection;
- public source repository;
- MIT or Apache-2.0 license;
- README/setup instructions;
- architecture diagram;
- public demo video of no more than five minutes;
- project description covering the problem, user, operation, and impact; and
- AWS Builder ID email.

Optional items include a live demo URL and eligible builder.aws posts.

## Current checklist

- [x] ROSIE repository public
- [x] Strands Agents integrated
- [x] Amazon Bedrock / Nova Micro live path verified
- [x] real ROSIE approval boundary exercised
- [x] proof program executed through Strands/ROSIE
- [x] BuildPrint-declared test command executed through Strands/ROSIE
- [x] deterministic delivered bytes preserved
- [x] HACKASS identified as pre-existing work
- [x] MIT license selected
- [ ] make the current Strands submission branch the public submission/default state
- [ ] finalize architecture diagram
- [ ] record and upload demo video
- [ ] finalize Devpost text
- [ ] enter AWS Builder ID email
- [ ] submit before deadline
