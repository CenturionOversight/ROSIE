"""RATTER event sink for PEEP operational telemetry.

Sends PEEP PeepEvent objects to RATTER's generic telemetry ingestion
endpoint. Failures are logged locally but never propagate through the
ROSIE execution path.

This module is OUTSIDE the execution-critical path: if RATTER is
unavailable, commands still succeed normally.

RATTER ingest endpoint: POST /api/v1/ingest/events
Accepts: {events: [...]} (batch) or a single event object.
No auth required for local development.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Iterable

from peep.events import PeepEvent

__all__ = ["RatterSink", "map_peep_to_ratter_event", "DEFAULT_RATTER_URL"]

logger = logging.getLogger(__name__)

DEFAULT_RATTER_URL = "http://localhost:3000/api/v1/ingest/events"
DEFAULT_RUNTIME_ID = "rt_rosie_local"
DEFAULT_INSTANCE_ID = "inst_rosie_local_01"
HTTP_TIMEOUT_SECONDS = 5


def _peep_event_category(event_type: str) -> str:
    """Map a PEEP event_type to a RATTER event_category."""
    if event_type.startswith("session."):
        return "session"
    if event_type.startswith("command."):
        return "command"
    if event_type.startswith("output."):
        return "command"
    if event_type.startswith("process."):
        return "runtime"
    if event_type.startswith("execution."):
        return "command"
    if event_type.startswith("peep."):
        return "system"
    return "command"


def _peep_event_severity(event_type: str) -> str:
    """Map a PEEP event_type to a RATTER severity."""
    if event_type.startswith("output"):
        return "info"
    if event_type.startswith("execution.error") or event_type.startswith("execution.interrupted"):
        return "error"
    if event_type.startswith("execution.warning") or event_type.startswith("peep.event_dropped"):
        return "warning"
    if event_type.startswith("peep.adapter_failed"):
        return "critical"
    return "info"


def map_peep_to_ratter_event(
    event: PeepEvent,
    runtime_id: str,
    instance_id: str,
    command_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Convert a PeepEvent into a RATTER TelemetryEvent-compatible dict.

    Preserves PEEP identity fields verbatim:
    - event_id → external_event_id
    - event_type → event_type (verbatim)
    - occurred_at → occurred_at (ISO 8601)
    - source_type → preserved in payload
    - source_id → preserved in payload
    - session_id → session_id
    - sequence → sequence_number
    - metadata → preserved in payload
    - payload → payload
    - command_id → command_id (when available)
    - task_id → carried in the payload (when available, ROSIE task correlation)
    """
    occurred_at = event.occurred_at.isoformat() if isinstance(event.occurred_at, datetime) else event.occurred_at

    ratter_event: dict[str, Any] = {
        "event_type": event.event_type,
        "event_category": _peep_event_category(event.event_type),
        "severity": _peep_event_severity(event.event_type),
        "runtime_id": runtime_id,
        "instance_id": instance_id,
        "session_id": event.session_id,
        "external_event_id": event.event_id,
        "sequence_number": event.sequence,
        "occurred_at": occurred_at,
        "received_at": datetime.now(UTC).isoformat(),
        "component_category": "peep-adapter",
        "public_summary": f"PEEP event: {event.event_type}",
        "payload": {
            "peep_event_id": event.event_id,
            "peep_event_type": event.event_type,
            "peep_occurred_at": occurred_at,
            "peep_source_type": event.source_type,
            "peep_source_id": event.source_id,
            "peep_metadata": event.metadata or {},
            "peep_payload": event.payload or {},
            "peep_sequence": event.sequence,
            "peep_schema_version": event.schema_version,
            "rosie_task_id": task_id,
            "rosie_command_id": command_id,
        },
        "command_id": command_id,
        "sensitivity": "internal",
        "retention_class": "standard",
        "tags": ["peep", "rosie-local", event.event_type],
    }
    if command_id is None:
        command_id = (event.payload or {}).get("command_id")
        if command_id is not None:
            ratter_event["command_id"] = command_id
    return ratter_event


class RatterSink:
    """Sends batches of PEEP events to a local RATTER instance.

    All failures are caught and logged; the sink never raises into
    the ROSIE execution path.
    """

    def __init__(
        self,
        url: str | None = None,
        runtime_id: str = DEFAULT_RUNTIME_ID,
        instance_id: str = DEFAULT_INSTANCE_ID,
        enabled: bool | None = None,
    ) -> None:
        self._url = url or os.environ.get("RATTER_URL", DEFAULT_RATTER_URL)
        self._runtime_id = runtime_id
        self._instance_id = instance_id
        self._timeout = float(os.environ.get("RATTER_HTTP_TIMEOUT_SECONDS", str(HTTP_TIMEOUT_SECONDS)))

        if enabled is None:
            self._enabled = os.environ.get("RATTER_DISABLED", "").lower() not in ("1", "true", "yes")
        else:
            self._enabled = enabled

    @property
    def url(self) -> str:
        return self._url

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    def _build_request(self, events: list[dict[str, Any]]) -> urllib.request.Request:
        body = json.dumps({"events": events}).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return req

    def send(self, events: Iterable[dict[str, Any]]) -> bool:
        """Send a batch of RATTER-format events to the ingest endpoint.

        Returns True if the HTTP request succeeded (2xx), False otherwise.
        Never raises.
        """
        if not self._enabled:
            return False

        batch = list(events)
        if not batch:
            return True

        try:
            req = self._build_request(batch)
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as e:
            logger.warning(
                "RATTER ingest HTTP error: %d %s (dropped %d events)",
                e.code, e.reason, len(batch),
            )
            return False
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            logger.warning("RATTER ingest connection failed: %s (dropped %d events)", e, len(batch))
            return False
        except Exception as e:
            logger.warning("RATTER ingest unexpected error: %s (dropped %d events)", e, len(batch))
            return False

    def send_peep_events(
        self,
        events: Iterable[PeepEvent],
        command_id: str | None = None,
        task_id: str | None = None,
    ) -> bool:
        """Convert PEEP events to RATTER format and send as a batch.

        Returns True if all events were accepted by RATTER, False otherwise.
        """
        ratter_events = [
            map_peep_to_ratter_event(
                e, self._runtime_id, self._instance_id, command_id, task_id
            )
            for e in events
        ]
        return self.send(ratter_events)
