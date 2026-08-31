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
