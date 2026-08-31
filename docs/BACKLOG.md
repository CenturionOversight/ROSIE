# Backlog / deferred items

## Deferred — Planner voice input

A planner voice-input mode (capture a spoken prompt -> STT -> feed the
transcription as the HACKASS `prompt`) was considered during the hosted
HACKASS ADK service source preparation.

Status: **DEFERRED** (not implemented).

Reason: out of scope for the hosted HACKASS ADK service OCME. Voice input
would add a speech-to-text dependency and a new input channel, which expands
the architecture beyond the current Gemini/Google-ADK compliance path.

Reconsider when one of these is answered:
- Which STT provider? (Vertex AI Speech / Google Speech-to-Text / Whisper)
- Is voice input an All Things Agentic submission requirement, or optional polish?
- Should the hook live on the hosted `POST /execute` route or on the local
  `python -m hackass.run` entrypoint?

No code path depends on this. No secret is involved.

## Deferred — /execute route hosting rewrite plan

The hosted HACKASS ADK service (`server.py`) exposes `POST /execute` and
`GET /health`, but the Firebase Hosting rewrite that maps a public path
(e.g. `/api/execute`) to this service's `/execute` route has not been
decided.

Status: **DEFERRED** (no rewrite configured; `firebase.json` in this repo is
present but unused until a deploy decision is made).

Reason: Hosting deploy is out of scope for the current source-prep OCME.
The exact public path prefix and whether `/execute` is gated behind the
existing `hackass-fire` snippet or a separate hosted HACKASS domain is a
deploy-time decision.

Reconsider when one of these is answered:
- Is the HACKASS service exposed at `/api/execute` on `hackass-fire`, or on a
  dedicated `hackass-api` Cloud Run URL reached directly?
- Should `/execute` be behind the tiun snippet auth gate, or open to the
  hosted service with server-side workspace/approval config?
- Confirm Cloud Run service name (`hackass-api`) and region.

No code change is needed to keep this deferred — `server.py` already binds
`PORT` and exposes `/execute`; only the Hosting `rewrites` block in
`firebase.json` changes when the decision is made.
