# ROSIE Target Architecture Review

**Status:** current `main` is at `bdf10102...` after the SCRATCH merge.

1. **Intended product**: ROSIE is the complete local software-engineering application — the user supplies intent; the app interviews, plans, validates, executes, observes, repairs, and presents results.
2. **Current architecture** preserves historical HACKASS / ARCHESTRATOR provenance, coupling the generic software-engineering machinery to hackathon packaging layers (Google ADK, Cloud Run, HACKASS naming, delivery boilerplate).
3. **What must change**: responsibility boundaries become the primary architectural contracts — not package names.

This document is architecture review only.  No code has been restructured as part of this review; the only change is this document.

---

## 1. Target Product Definition

From the user's perspective ROSIE exists to turn natural-language intent into real working software on the user's own machine, without the user having to orchestrate shell commands or API calls.

ROSIE is:

- an application, not a CLI wrapper, bridge, or library;
- the owner of the entire software-engineering lifecycle on the local workspace;
- the only component the user interacts with when delivering software tasks.

ROSIE is **not**:

- a HACKASS Cloud Run / Google ADK backend;
- an ARCHESTRATOR proxy;
- a shell wrapper injected into the HACKASS demo;
- a service defining another product's product boundary.

The current standalone+dual-identity packaging (local CLI + deployable HACKASS container) is inherited from hackathon constraints, not target architecture.

---

## 2. Target User Lifecycle

For a single task the intended lifecycle is:

```text
user expresses intent
   ↓
INTERVIEW / INTENT INTAKE
   ↓ (prove access boundary, workspace, authority model)
PLANNING (planning model, possibly multi-pass / critique loop)
   ↓ (plan ready for user)
USER REVIEW / APPROVAL boundary (plan, side effects, estimated cost)
   ↓ (approved)
ORCHESTRATION (tasks → steps → handlers)
   ↓
EXECUTION
   ↓ (workspace / filesystem / shell / network tools running under policy)
OBSERVATION (PEEP spatial event capture; raw but loss-bounded)
   ↓
OPERATIONAL RECORD (RATTER: hashed, chained, ordered, readable)
   ↓
REASONING / REPAIR (analyze results; decide continuation; planner re-enters)
   ↓
COMPLETION (deliver working artifacts, mention verification done)
   ↓
ARTIFACT PRESENTATION
```

Repetition: repair, continuation, multi-step refinement are first-class. First pass planning alone is not enough.

---

## 3. Global Architectural Invariants

1. **Product-name invariance**: core classes, function parameters, module names, and state predicates do not embed product identifiers.  Language such as `run_hackass`, `hackass-fire`, "HACKASS edition", `rosie_hackass`, or branching logic guarded by `_is_hackass_surface` are anti-patterns.
2. **Responsibility-first contracts**: planner, orchestrator, executor, workspace, observer, telemetry, and policy are interchangeable capabilities; providers fire through interfaces (model provider, voice provider, execution transport, persistence, telemetry sink).
3. **Transport-vs-core separation**: CLI, web server, and Cloud Run hosting are surface/transport concerns; the core owns planning, orchestration, execution, and state.
4. **Locality before hierarchy**: ROSIE's current "local boundary" is currently framed as a product boundary between user ↔ ROSIE ↔ ARCHESTRATOR ↔ HACKASS. In the target architecture locality is a *capability*: `workspace`-oriented execution runs on the user's machine instead of in the cloud, while the application still owns task orchestration.

---

## 4. Target Responsibility Map

### 4.1 Application Experience

- user interaction is a focused task channel with clearly exposed intent → plan → review → execute → artifact stages;
- not a chat window that impersonates an always-on engineering platform;
- approval dialogs are driven by the plan/execution machine, not reverse.

### 4.2 Intelligence

- Interview/intent extraction;
- Planning (decomposition; multi-pass critique; tie-breaking cost/latency/risk);
- Runtime repair and continuation reasoning (not a fallback first seen once execution fails);
- Planner state is a runtime instance's responsibility, not a global module constant.

### 4.3 Orchestration

- Task lifecycle: goto run, track plan steps, route steps to local execution;
- Targets/priorities can change mid-run; orchestration must not hardcode a single-task shape;
- One task sequencing engine.  Must not: one per surface (cloud route → CLI → internal wrapper).

### 4.4 Execution

- Workspace is a runtime-owned resource: every execution operation resolves paths against its own workspace;
- Execution policy gates mutation via a single policy engine that owns the approve/deny decision regardless of entry surface;
- Tool-facing side provides the execution surface (file read/write, shell, Git).

### 4.5 Awareness

- PEEP = capture;
- RATTER = persist + verify + hike timeline inspectability;
- SCRATCH = working storage, possibly own intermediate plans;
- Reason learners (future WATSON) read the record, not event streams.

### 4.6 Infrastructure

- Cloud hosting, server product, browser surface are adapters with a generic reverse
 contract; they may supply the live interface and transport but cannot define ownership of planning/execution.

---

## 5. Target Ownership / State Model

| State            | Owner            | Notes                              |
|------------------|------------------|------------------------------------|
| workspace root   | RuntimeSession   | setter; not a shared static global |
| approval policy  | RuntimeSession   | created; reused; not mutated via CLI-only helper calls mid-run |
| tool registry    | RuntimeSession   | zero-argument factory built from tools module; no key wiring; model_AGAINST global |
| task id          | TaskExecution    | per-run; forwarded via ContextVar, no hidden global |
| PEEP executor    | LocalExecution   | only one per runtime when present; not a model-facing tool |
| RATTER core      | RuntimeSession   | wired in-process by default; optional remote post side effect |
| SCRATCH          | RuntimeSession   | workspace-relative; persisted on disk for reopen/restart |
| retry state      | Orchestrator     | planner-visible state, not executor-global |

Single-source runtime replaces module-global runtime state; any concurrent runs share only process-level singletons deliberately.

---

## 6. Target Runtime Topology

```
user
  └─► ApplicationSurface (CLI | WebSocket/HTTP server)               # transport only
       └─► ApplicationCore (ApplicationRuntime)                      # ownership
             ├─► Intent/Interview     → planner
             ├─► Planner              → `planning` models
             └─► Orchestrator
                   │
                   ▼
               RuntimeSession
                   ├─ workspace + execution policy
                   ├─ ToolRegistry    → dispatch_tool       (tools: file, Git, shell, patch)
                   ├─ LocalExecution  → PEEP (observation) → exec runtime
                   └─ RATTER core
                         └─► SCRATCH workspace (persistent local state)
```

Transport layers only forward user intent + render results; planning orchestration/execution/failure-policy live in the runtime.

---

## 7. Current Runtime Topology

user → **server.py** (Cloud Run service executing `hackass.run_hackass`) or → **wrapper.cli** (standalone REPL)  
`server.py` executes through `hackass.run_hackass` → `hackass.agent` → `hackass.bridge` (`create_architect_tools`) → `wrapper.tools.dispatch_tool`
`wrapper.cli` utilities `tools`, `policy`, `peep_shell`, `context`, `rt_context`, `ratter_core`, `scratch`.

This is a fork: two independent runtime entries sharing the same underlying machinery.  Governance (approval) and workspace state live as module-level globals behind `tools.py`:

```
wrapper/tools.py globals
  - _workspace_root
  - _policy
  - _shell_executor
wrapper/cli.py
  - parser defaults
  - model chain / Vertex env propagation
```

These module-level globals are reachable-and-mutated from `server.py`, from `hackass.agent.create_agent`, from `wrapper/cli.py`, and from tests. Every consumer re-establishes them, coupling surfaces.

---

## 8. Current → Target Gap Map

| Area | Current | Target | Verdict | Justification |
|------|---------|--------|---------|---------------|
| Entry surface CLI (`wrapper/cli.py`) | Standalone REPL+Fallback model loop | ApplicationRuntime as primary surface | **KEEP→RESHAPE** | loop/expansion is well-conditioned, but the surface assembly (parse args / choose model chain) must stop owning the workspace + approval system itself |
| Entry surface web (`server.py`) | Thin route→HACKASS shell | One application API (user-facing) | **RENAME/VITAL/RESPLIT** | the API surface must be generic; `hackass.run_hackass` naming paths should die |
| Tools (tools.py) | global workspace/policy/executor | Same functions, owned by task runner | **KEEP visible but reshape ownership** | tool modules must not store process state |
| Approval policy (`policy.py`) | module-global `_policy` | owned by session; store per task | **RESHAPE** | public interface remains `ApprovalPolicy(...)/ExecutionPolicy` but accepts rights by constructor arg not module mutation |
| Workspace containment (`tools.py`) | global `_workspace_root` + `_resolve_safe_path*` | per-session workspace object, callable `workspace.resolve(p)` | **KEEP internals, reshape ownership layer** | the pure safe-path logic is fine; only where it is stored is wrong |
| PEEP (`peep_shell.py`/`ratter_*`) | global executor + module default shared RATTER core | owned by session/runtime, factory-created | **KEEP machinery, reshape ownership** | today's implementation already does the capture/record correctly; only who owns the resources should change |
| SCRATCH (`scratch.py`) | module-level `set_workspace_root` w/ $SCRATCH inside | workspace member, path invariant enforced once at runtime construction | **KEEP content, reshape lookup** | the store itself is the right shape; ownership should move |
| HACKASS Google ADK path | `hackass` module imports `google-adk` / `google-genai` directly; `run_hackass()` owns local config | remove from core contract; behavioral or configuration surface only | **REMOVE_FROM_CORE** | the adapter is fine, hauling the demo pipeline into the repo is the issue |
| Browser UX (`public/`) | fixed HACKASS label + single-shot POST | application UX, not product branding on transport layer | **REMOVE branding from UX/code** | the UX exists but it's a launcher; independent of core product semantics |
| Deployment (firebase.json / Dockerfile / Cloud Run service name) | HACKASS shape | deployment data, not product core | **REMOVE product names from core config names** | deployment is a layer on top; Cloud Run target needs `ROSIE`/`runtime` not `hackass-api` |

---

## 9. Identity Leakage Audit

Searched case-insensitive for `rosie`, `hackass`, `archestrator`, and related modeled line across `*.py`, `*.md`, `*.html`, `*.js`, `*.css`, `*.json`, `*.ts`, `*.tsx`.

### Architectural leak (core naming infected by product identity)

- `hackass`, `hackass-fire`, `bosie`/Dummy model naming, `rosie_hackass`, `run_hackass`, `_MODEL_ENV_VAR = "HACKASS_GEMINI_MODEL"`, session IDs formed with `rosie-hackass` — all decorate execution config with product heritage instead of capability names.
- `wrapper/peep_shell.py` source_id `rosie_hackass` strings; `wrapper/system_prompt.py` contains `You are ROSIE (HACKASS edition)`; docstrings in `hackass/*` tools bind tool implementation semantics to GEN AI / Hackathon nomenclature ("the wrapperpackage (ARCHESTRATOR core) remains unchanged.").  These leaks translate into identifier-level coupling (`_shell_executor`'s `_configure_peep_executor` for HACKASS compatibility, plus `wrapper/tools.py` env hooks named after HACKASS).

### Identity that survives as valid branding/config (OK)

- README/docs/SECURITY/HACKATHON/SUBMISSION — historical recruitment documentation; clearly contextual.
- `.firebaserc` / `firebase.json` / Hackathon `hackass-api` / `hackass-fire` labels — deployment datum but should be converted: the default local cloud runtime should read `rosie-runtime-prod` or equivalent neutral label.
- Public web frontend header (`public/index.html:title`, `public/app.js:newline.`) — should not call ROSIE by name once the application delivers product state; the UI is application state only.

### Historical vendor/test identifiers that still carry meaning

- `tests/test_hackass_*.py` (arda wrappers, integration) and `tests/test_system_prompt.py` (prompt placeholder) are product-specific tests.  Keep the intelligent behavior but rename the tests once the source stops naming the hackathon.
- `docs/HACKATHON.md`, `docs/SUBMISSION.md`, `docs/BACKLOG.md` — allowed to remain as archived (docs); not part of runtime semantics.

---

## 10. State / Concurrency Findings

### Module-global mutable state (current `main`)

| Global | Defined in | Mutated by | Risk |
|--------|-----------|------------|------|
| `_workspace_root` | tools.py | `set_workspace_root` / CLI / `hackass.agent` | Two concurrent runs / mixed roots silently leak. Also forces storage ownership inside the tools module. |
| `_policy` | tools.py | CLI flags + request path (`set_policy` called once per run, then cli); `wrapper.cli.set_policy` | A policy per runtime is the intended semantic, but the global object's mutation persists between top-level invocations. |
| `_shell_executor` | tools.py | Created by `set_shell_executor`, never reset cleanly except after local-close | If a near-parallel path configures it, cross-contamination; HACKASS runtime + standalone both rehydrate. |
| `_current_task_id` ContextVar | `rt_context.py` | `_run_turn` | Actually fine (contextvars are threaded-correct); but the PEEP executor is still one-per-`_configure_peep_executor` call, which happens to be fine. |
| `_pending_commands` / `_pending_commandsObjs` | ADK partition inside hackass | none (not in ROSIE code) | irrelevant; direct sample size |

### Solutions (recommended shape)

Encapsulate everything into explicitly constructed RuntimeSession / RuntimeTask:
- workspace.path resolution
- task ids
- pull `ApprovalPolicy`, shared output bounds, the open console executor
- shell configuration connection
- RATTER wired in, SCRATCH materialized

Public API:

```
runtime = RuntimeSession.open(workspace)
runtime.execute(user_intent)
runtime.close()
```

Policy and model chain differ per runtime not per honored module.

---

## 11. Planning / Execution Findings

Current path: no Planner / BuildPrint phase exists — the message is placed directly into an LLM-run/PEEP loop,yolo each step.

- `hackass.run_hackass` is the only cloud-based execution loop, and `wrapper.cli` is the only standalone dev loop.
- The two loops do not share a task-plan node; each runs their own model → tool plans.

Loaded flow:

1. `wrapper.cli.main` → loads workspace + policy → attaches PEEP executor → sets `task_id` context var → `_run_turn`
2. `_run_turn` → `_resolve_tool_calls` (loop) → `_completion` via LiteLLM → emplace tool results into messages → repeat until final text
3. hacking from server.py -> hackass.run_hackass — same setup in moderation, but using ADK LlmAgent fallback rather than WHAT role wrapper.cli used (LiteLLM) but same dispatch_tool.

### Verdict

Keep `_resolve_tool_calls` as a tool-iteration loop; keep the per-tool write approval, but move them into an **execution runner** that speaks to an orchestrator, does not own global configuration, can be applied to:
- the local CLI surface;
- the HTTP service API surface; and
- future web/Uert-party surfaces.

Currently duplicated entry points split the application lifecycle ownership.

---

## 12. Provider / Deployment Findings

- Detection of product configuration inside logic: `_is_vertex_model`, `_is_ollama_model` exist to special-case cloud providers — acceptable if framed as environment detection, but the ha*kass*`, HACKASS-fired variable strings (project, location) must become config data only, not logic predicates.
- server.py + Dockerfile + firebase.json + hackass/.firebaserc are deployment machinery; they should no longer establish themselves as a distinctive HACKASS product service: the service should read as `rosie-runtime` (or similar generic tag) deployed to a generic runtime backend.
- The Python packaging already supports multiple model providers through LiteLLM — do not standardize more until after the runtime contract changes land.

---

## 13. Test Classification

`tests/` has broad coverage of tool behavior and rail integrity heuristics, but some assets are historic-test-preserving:

- **Product behavior tests:** `tests/test_cli.py`, `tests/test_tools.py`, `tests/test_system_prompt.py`, `tests/test_execution_hardening.py`, `tests/test_policy.py`, `tests/test_scratch_persistent.py`, `tests/test_task_context.py`, `tests/test_ratter_core.py`, `tests/test_ratter_sink.py`, `tests/test_ratter_async*.py`, `tests/test_peep_shell_integration.py`, `tests/test_peep_visibility.py`, `tests/test_path_traversal.py`, `tests/test_git_inspection.py` — real behavior worth keeping through restructure.
- **Architecture-fragile tests:** `tests/test_hackass_*.py` — assert HACKASS / ADK / Vertex-specific names that should not live in the core; keep the behavior but rename files/fixtures when the product API goes generic.
- **Hackathon-only:** any tests referencing `HACKASS` in name or asserting `hackass-agent` labels need to be replaced or removed; they came from submission output, not product contract.

Test-only bootstrap residue: anything that mocks global state across modules (set_workspace_root between tests) should instead build an isolated RuntimeSession per class/test — a future optimization, not a breaking change.

---

## 14. Code to Keep

- `tools.py` (tool definitions + safe-path helpers).
- `wrapper/cli.py:_resolve_tool_calls` loop with policy + workspace.
- `ratter_core.py` (the record/integrity core only: storage is permanent, integrity is recomputable, timeline construction, retention).
- `scratch.py` (pads/writes semantics — location stable at `$SCRATCH/`).
- `rt_context.py` (ContextVar plumbing — correctly scoped).
- `policy.py` (enum and per-mode rules).
- Policy + context + tools as unit-test-capable API.

---

## 15. Code to Reshape

- Move all module-level entry global shares (`_workspace_root`, `_policy`, `_shell_executor`) from `tools.py` into an explicit `RuntimeSession` object;
- Collapse the redundant CLI and web service into a single application surface owned by `ApplicationRuntime`—the existing standalone CLI `wrapper.cli` is the baseline harness;
- Refactor wrapper/cli to build the generic `RuntimeSession` instead of wiring globals;
- Refactor `hackass.*` to become a provider-specific configuration branch only (adapter, not a executed own ritual with its own names);
- Rename process paths to include neutral runtime naming in logging, error strings, and seed env vars.

---

## 16. Code / Boundaries to Remove

- The nested `hackass` package duplicated tool wrappers (`hackass.bridge`) — each ASK-callable method should be generated from the same `TOOL_REGISTRY`, not written twice.
- All HACKASS/ARCHESTRATOR brand strings from runtime code (docstrings, log lines, "HACKASS edition" JSON instruction blocks).
- HACKASS-specific docs that leak into the runtime spec (BACKLOG, HACKATHON/SUBMISSION remain as historical published record only).

Do not remove tests; functions, classes, or shared mechanics; only rename or relocate them once the new architecture is in place and only where the rename addresses a concrete leak.

---

## 17. Unresolved Decisions Requiring Darren

- **Preprocessor planning model:** Does ROSIE need a planning phase >1 pass by default (intent → BuildPlan → Review → Execute), or should the current open-ended tool loop be the primary orchestration mode?
- **Multi-task/multi-project concurrency model:** should the runtime permit parallel sessions with isolated workspaces, or serialize tasks per run today?
- **Persistence authority:** is the repository the home of persistent state (as `$SCRATCH` is today), or should ROSIE own a project-level database for user projects?
- **Browser-based transport scope:** do we need a durable final HTTP application model (separately-owned application server) after the hackathon? Or should that own down local-first? 
- **When does `hackass.run_hackass` / the Cloud Run endpoint get removed?** Until the removal gates are set, stay merged-in but unprotected.

---

## 18. Recommended Restructuring Sequence

1. **Runtime consolidation**: introduce `RuntimeSession` / `RuntimeTask` owning workspace, policy, executor, records (`scratch`, `ratter_core`, `rt_context`).
2. **Decouple tools ownership:** convert `tools.py` globals into `RuntimeSession` members (no global policy/workspace/executor).
3. **Application surface consolidation:** one web entrypoint `/execute` and CLI behind the same `ApplicationRuntime` adapter.
4. **Identity purge:** rename product naming in core code → configuration-level defaults (config json + logging metadata); move HACKASS doc prose to `docs/` archives.
5. **Telemetry export** limbs: PEEP-only external sinks should support dumping to a standalone RATTER backend by URL when configured.

Each step ends with a passing test suite.  Steps stop respecting internal packer names only when no test asserts them anymore.

---

*End of review document.*
