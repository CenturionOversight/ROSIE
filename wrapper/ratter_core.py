"""In-process RATTER operational-record core for ROSIE.

This module is a faithful Python port of RATTER's canonical ingest,
sequencing, hashing, chain-hash, and signature machinery:

- ``canonicalize_json``           ← src/server/runtimeRegistry.ts:canonicalizeJson
- ``compute_payload_hash``        ← src/server/runtimeRegistry.ts:computePayloadHash
- ``compute_chain_hash``          ← src/server/runtimeRegistry.ts:computeChainHash
- ``generate_signature``          ← src/server/runtimeRegistry.ts:generateSignature
- ``RatterCore.ingest_events``    ← src/server/store.ts:ingestEvent
- ``RatterCore.get_timeline``     ← server.ts GET /api/v1/sessions/:id/timeline
- ``RatterCore.get_integrity``    ← server.ts GET /api/v1/sessions/:id/integrity

RATTER remains the standalone development repository for this machinery;
ROSIE mines the parts it actually needs for the local operational record so
ROSIE local operation no longer depends on a separately-running RATTER HTTP
service (RATTER_URL / localhost:3000 are no longer required for the default
local path).

RATTER is observational machinery: this core must never block or break ROSIE
execution.  Callers (e.g. wrapper.ratter_sink.RatterSink) are responsible for
wrapping it in a bounded, nonfatal boundary.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

__all__ = [
    "GENESIS_CHAIN_HASH",
    "RatterCore",
    "canonicalize_json",
    "compute_chain_hash",
    "compute_payload_hash",
    "generate_signature",
    "get_ratter_core",
]


GENESIS_CHAIN_HASH = "sha256:" + "0" * 64
_DEFAULT_TENANT_ID = "tenant_rosie_local"
_DEFAULT_RUNTIME_ID = "rt_rosie_local"
_DEFAULT_INSTANCE_ID = "inst_rosie_local_01"
_DEFAULT_SIGNATURE_KEY = "ratter-secret-key-2026"
_DEFAULT_SIGNATURE_KEY_ID = "key_sentinel_2026_pub"
# Bounded in-process retention: sessions (and all their events), alerts, and
# events are each capped independently.  When exceeded, the oldest complete
# sessions/alerts are dropped wholesale, so surviving sessions always keep
# intact chain links and sequence ordering.
_DEFAULT_MAX_SESSIONS = 1_000
_DEFAULT_MAX_EVENTS = 100_000
_DEFAULT_MAX_ALERTS = 500


# ---------------------------------------------------------------------------
# Hashing machinery (ported from runtimeRegistry.ts)
# ---------------------------------------------------------------------------


def canonicalize_json(value: Any) -> str:
    """Produce RATTER's canonical JSON string for a value.

    Matches ``canonicalizeJson`` in RATTER: no whitespace, object keys are
    sorted, keys whose value is ``None``/``undefined`` are omitted, unicode
    is preserved verbatim (no ``\\uXXXX`` escapes), and non-finite numbers
    serialize as ``null``.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        # ECMAScript JSON.stringify(NaN / ±Infinity) → "null".
        if math.isnan(value) or math.isinf(value):
            return "null"
        # JSON.stringify renders integral floats with no fractional part
        if value == int(value):
            return str(int(value))
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonicalize_json(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(k for k in value if value[k] is not None)
        return "{" + ",".join(
            json.dumps(k, ensure_ascii=False) + ":" + canonicalize_json(value[k])
            for k in keys
        ) + "}"
    raise TypeError(f"cannot canonicalize value of type {type(value).__name__}")


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Return ``sha256:<hex>`` of the canonical JSON form of *payload*."""
    canonical = canonicalize_json(payload)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_chain_hash(prev_chain_hash: str, payload_hash: str, sequence_number: int) -> str:
    """Return ``sha256:<hex>`` of ``prev_chain | payload_hash | seq``."""
    data = f"{prev_chain_hash}|{payload_hash}|{sequence_number}"
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def generate_signature(data: str, secret_key: str = _DEFAULT_SIGNATURE_KEY) -> str:
    """Return RATTER's HMAC-SHA256 base64 signature of *data*."""
    digest = hmac.new(
        secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("ascii")


# ---------------------------------------------------------------------------
# Core record store (ported from store.ts ingestEvent + session/timeline/
# integrity query handlers from server.ts)
# ---------------------------------------------------------------------------


class RatterCore:
    """Thread-safe in-process operational record.

    Stores ingested telemetry events with RATTER-equivalent payload hashing,
    chain hashing, signature generation, sequence-gap detection, and
    broken-chain detection.  Query helpers mirror RATTER's session /
    timeline / integrity endpoint semantics.

    Bounded in-process retention: when either ``max_sessions`` or
    ``max_events`` is exceeded, the oldest sessions and the events belonging
    to them are dropped wholesale, so surviving sessions keep intact chain
    links and sequence ordering.  ``max_alerts`` similarly bounds the alert
    record.  No background worker or database is required.
    """

    def __init__(
        self,
        runtime_id: str = _DEFAULT_RUNTIME_ID,
        instance_id: str = _DEFAULT_INSTANCE_ID,
        max_sessions: int = _DEFAULT_MAX_SESSIONS,
        max_events: int = _DEFAULT_MAX_EVENTS,
        max_alerts: int = _DEFAULT_MAX_ALERTS,
    ) -> None:
        self.runtime_id = runtime_id
        self.instance_id = instance_id
        self.events: list[dict[str, Any]] = []
        self.sessions: list[dict[str, Any]] = []
        self.alerts: list[dict[str, Any]] = []
        self._max_sessions = max_sessions
        self._max_events = max_events
        self._max_alerts = max_alerts
        # Incremental ingest state: last chain_hash + sequence per session,
        # populated as events arrive. ``None`` markers are never stored here;
        # missing keys mean the session has not been seen before.
        self._last_chain: dict[str, str] = {}
        self._last_seq: dict[str, int] = {}
        self._session_index: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def ingest_event(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        """Ingest a single RATTER-format event.

        Returns ``{"event": stored_event, "status": integrity_status}``.
        """
        with self._lock:
            return self._ingest_event_locked(dict(raw_event))

    def ingest_events(self, raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ingest a batch of events in order.  One lock for the whole batch
        so interleaved threads cannot split a session's record."""
        with self._lock:
            return [self._ingest_event_locked(dict(e)) for e in raw_events]

    def _ingest_event_locked(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        runtime_id = raw_event.get("runtime_id") or self.runtime_id
        instance_id = raw_event.get("instance_id") or self.instance_id
        session_id = raw_event.get("session_id") or f"session_live_{uuid4().hex[:12]}"
        tenant_id = raw_event.get("tenant_id") or _DEFAULT_TENANT_ID

        payload = raw_event.get("payload") or {}
        payload_hash = compute_payload_hash(payload)

        # Incremental ingest: read prior-session state from the cached
        # last-chain / last-seq indexes instead of rescanning the full
        # retained event list.
        prev_chain_hash = self._last_chain.get(session_id, GENESIS_CHAIN_HASH)
        last_seq = self._last_seq.get(session_id, 0)

        seq_num = raw_event.get("sequence_number")
        if seq_num is None:
            seq_num = last_seq + 1

        chain_hash = compute_chain_hash(prev_chain_hash, payload_hash, seq_num)

        integrity_status = "verified"
        if session_id in self._session_index:
            if seq_num != last_seq + 1:
                integrity_status = "sequence_gap"
        given_prev = (raw_event.get("integrity") or {}).get("previous_chain_hash")
        if given_prev and given_prev != prev_chain_hash:
            integrity_status = "broken_chain"

        signature = (raw_event.get("integrity") or {}).get("signature") or generate_signature(
            f"{payload_hash}:{chain_hash}"
        )

        event_id = raw_event.get("event_id") or f"evt_live_{uuid4().hex[:12]}"

        event: dict[str, Any] = {
            "schema_version": raw_event.get("schema_version") or "1.0.0",
            "event_id": event_id,
            "external_event_id": raw_event.get("external_event_id") or f"ext_{event_id}",
            "tenant_id": tenant_id,
            "runtime_id": runtime_id,
            "instance_id": instance_id,
            "session_id": session_id,
            "turn_id": raw_event.get("turn_id"),
            "sequence_number": seq_num,
            "occurred_at": raw_event.get("occurred_at") or datetime.now(UTC).isoformat(),
            "received_at": datetime.now(UTC).isoformat(),
            "event_type": raw_event.get("event_type") or "runtime.heartbeat",
            "event_category": raw_event.get("event_category") or "runtime",
            "severity": raw_event.get("severity") or "info",
            "component_category": raw_event.get("component_category") or "runtime-core",
            "public_summary": raw_event.get("public_summary") or "Live runtime telemetry event",
            "public_explanation": raw_event.get("public_explanation"),
            "reason_code": raw_event.get("reason_code"),
            "previous_public_value": raw_event.get("previous_public_value"),
            "new_public_value": raw_event.get("new_public_value"),
            "actor_type": raw_event.get("actor_type"),
            "actor_reference": raw_event.get("actor_reference"),
            "correlation_id": raw_event.get("correlation_id"),
            "causation_id": raw_event.get("causation_id"),
            "trace_id": raw_event.get("trace_id"),
            "command_id": raw_event.get("command_id"),
            "payload": payload,
            "integrity": {
                "payload_hash": payload_hash,
                "previous_chain_hash": prev_chain_hash,
                "chain_hash": chain_hash,
                "signature": signature,
                "signature_key_id": _DEFAULT_SIGNATURE_KEY_ID,
            },
            "integrity_status": integrity_status,
            "sensitivity": raw_event.get("sensitivity") or "internal",
            "retention_class": raw_event.get("retention_class") or "standard",
            "tags": raw_event.get("tags") or ["live"],
        }

        self.events.append(event)

        # Incremental ingest state
        self._last_chain[session_id] = chain_hash
        self._last_seq[session_id] = seq_num

        session = self._session_index.get(session_id)
        if session is None:
            session = {
                "session_id": session_id,
                "tenant_id": tenant_id,
                "runtime_id": runtime_id,
                "instance_id": instance_id,
                "external_session_id": f"ext_{session_id}",
                "status": "active",
                "started_at": datetime.now(UTC).isoformat(),
                "tags": ["live_stream"],
                "event_count": 0,
                "turn_count": 0,
                "integrity_status": "verified",
            }
            self.sessions.append(session)
            self._session_index[session_id] = session
        session["event_count"] += 1
        if integrity_status != "verified":
            session["integrity_status"] = integrity_status

        if integrity_status in ("broken_chain", "sequence_gap"):
            self.alerts.append(
                {
                    "alert_id": f"alert_anom_{uuid4().hex[:8]}",
                    "tenant_id": tenant_id,
                    "runtime_id": runtime_id,
                    "instance_id": instance_id,
                    "session_id": session_id,
                    "alert_type": f"event.{integrity_status}",
                    "severity": "warning",
                    "status": "open",
                    "title": f"Integrity Alert: {integrity_status.upper()}",
                    "summary": f"Event {event_id} reported {integrity_status} during stream ingestion.",
                    "detected_at": datetime.now(UTC).isoformat(),
                    "source_event_ids": [event_id],
                    "is_ratter_generated": True,
                }
            )

        # Bounded retention: keep memory bounded by evicting oldest sessions/events/alerts
        self._enforce_retention_limits_locked()

        return {"event": event, "status": integrity_status}

    def _enforce_retention_limits_locked(self) -> None:
        """Evict oldest sessions (and associated events) / oldest alerts beyond
        bounds.  Only whole sessions are dropped: a surviving session's
        timeline and chain links therefore remain perfectly intact.
        """
        # alert bound: drop oldest entries
        if len(self.alerts) > self._max_alerts:
            self.alerts = self.alerts[len(self.alerts) - self._max_alerts :]
        # session bound: evict oldest sessions until within limit
        while len(self.sessions) > self._max_sessions:
            self._evict_session_locked(self.sessions[0])
        # event count bound via whole-session eviction (no mid-chain amputation)
        while len(self.events) > self._max_events and self.sessions:
            self._evict_session_locked(self.sessions[0])

    def _evict_session_locked(self, session: dict[str, Any]) -> None:
        sid = session["session_id"]
        self._session_index.pop(sid, None)
        self._last_chain.pop(sid, None)
        self._last_seq.pop(sid, None)
        self.sessions = [s for s in self.sessions if s["session_id"] != sid]
        self.events = [e for e in self.events if e["session_id"] != sid]
        self.alerts = [a for a in self.alerts if a["session_id"] != sid]

    # ------------------------------------------------------------------
    # Queries (mirror RATTER's session/timeline/integrity endpoints)
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Return the session record for *session_id*, or None."""
        with self._lock:
            return self._session_index.get(session_id)

    def get_timeline(self, session_id: str) -> list[dict[str, Any]]:
        """Return the session's events sorted by sequence number."""
        with self._lock:
            evs = [e for e in self.events if e["session_id"] == session_id]
            return sorted(evs, key=lambda e: e["sequence_number"])

    def get_integrity(self, session_id: str) -> dict[str, Any]:
        """Evaluate a session's chain integrity and sequence completeness.

        Mirrors RATTER's ``GET /api/v1/sessions/:id/integrity`` semantics
        and additionally recomputes payload/chain hashes from stored event
        payloads, so post-ingest payload tampering fails verification.
        An event whose ingest was flagged ``broken_chain`` is never ignored,
        even at index 0.
        """
        events = self.get_timeline(session_id)
        gaps: list[int] = []
        broken: list[str] = []
        for idx, evt in enumerate(events):
            rebuilt_payload_hash = compute_payload_hash(evt["payload"])
            stored_integrity = evt["integrity"]
            stored_prev = stored_integrity["previous_chain_hash"]
            stored_chain = stored_integrity["chain_hash"]
            if rebuilt_payload_hash != stored_integrity["payload_hash"]:
                broken.append(evt["event_id"])
            rebuilt_chain = compute_chain_hash(
                stored_prev, rebuilt_payload_hash, evt["sequence_number"]
            )
            if rebuilt_chain != stored_chain:
                broken.append(evt["event_id"])
            if idx == 0:
                # First event in a session: chain starts from the genesis hash.
                # Anything else (or an ingest-flagged broken_chain) breaks it.
                if stored_prev != GENESIS_CHAIN_HASH:
                    broken.append(evt["event_id"])
                elif evt.get("integrity_status") == "broken_chain":
                    broken.append(evt["event_id"])
                continue
            prev = events[idx - 1]
            if evt["sequence_number"] != prev["sequence_number"] + 1:
                gaps.append(evt["sequence_number"])
            if stored_prev != prev["integrity"]["chain_hash"]:
                broken.append(evt["event_id"])
        verified = bool(events) and not gaps and not broken
        uniq_broken = sorted(set(broken))
        return {
            "session_id": session_id,
            "total_events": len(events),
            "is_verified": verified,
            "sequence_gaps": gaps,
            "broken_links": uniq_broken,
            "integrity_status": "verified" if verified else ("broken_chain" if uniq_broken else "sequence_gap"),
        }


# ---------------------------------------------------------------------------
# Shared in-process instance (one operational record per ROSIE process)
# ---------------------------------------------------------------------------

_shared_core: RatterCore | None = None
_shared_lock = threading.Lock()


def get_ratter_core() -> RatterCore:
    """Return the process-wide shared RATTER core (created on first use)."""
    global _shared_core
    if _shared_core is None:
        with _shared_lock:
            if _shared_core is None:
                _shared_core = RatterCore()
    return _shared_core
