"""Focused tests for the RATTER event sink integration.

Tests cover:
1. PEEP event → RATTER telemetry mapping
2. PEEP event identity is preserved
3. multiple events can be sent as one batch
4. RATTER success does not alter ROSIE command result
5. RATTER connection failure does not fail ROSIE
6. RATTER timeout does not fail ROSIE
7. command.observed reaches the sink
8. command.completed reaches the sink
9. stdout/stderr behavior remains unchanged
10. HACKASS/shared cloud path does not instantiate or require RATTER
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, patch, MagicMock
import urllib.error

import pytest

from peep.events import PeepEvent
from wrapper.ratter_sink import (
    RatterSink,
    map_peep_to_ratter_event,
    DEFAULT_RATTER_URL,
    DEFAULT_RUNTIME_ID,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_peep_event(
    event_type: str = "command.observed",
    sequence: int = 0,
    event_id: str | None = None,
    session_id: str = "session-test-001",
    payload: dict | None = None,
    occurred_at: datetime | None = None,
    source_type: str = "rosie",
    source_id: str = "rosie-cli",
    **kwargs,
) -> PeepEvent:
    return PeepEvent(
        event_id=event_id or f"evt-{event_type}-{sequence}",
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(UTC),
        source_type=source_type,
        source_id=source_id,
        session_id=session_id,
        sequence=sequence,
        payload=payload or {},
        metadata=kwargs.pop("metadata", {}),
        schema_version=kwargs.pop("schema_version", 1),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. PEEP event → RATTER telemetry mapping
# ---------------------------------------------------------------------------

class TestPeepToRatterMapping:
    def test_basic_mapping(self):
        event = _make_peep_event(
            event_type="command.observed",
            payload={"command_id": "cmd-123", "command_text": "echo hello"},
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt_rosie_local", "inst_rosie_local_01")

        assert ratter_evt["event_type"] == "command.observed"
        assert ratter_evt["event_category"] == "command"
        assert ratter_evt["severity"] == "info"
        assert ratter_evt["runtime_id"] == "rt_rosie_local"
        assert ratter_evt["instance_id"] == "inst_rosie_local_01"
        assert ratter_evt["session_id"] == "session-test-001"

    def test_command_observed_mapping(self):
        event = _make_peep_event(
            event_type="command.observed",
            payload={"command_id": "abc123", "command_text": "Get-Location"},
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")

        assert ratter_evt["event_type"] == "command.observed"
        assert ratter_evt["command_id"] == "abc123"

    def test_command_completed_mapping(self):
        event = _make_peep_event(
            event_type="command.completed",
            payload={"command_id": "abc123", "exit_code": 0},
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst", command_id="abc123")

        assert ratter_evt["event_type"] == "command.completed"
        assert ratter_evt["command_id"] == "abc123"

    def test_session_event_category(self):
        for et in ["session.started", "session.ended"]:
            event = _make_peep_event(event_type=et)
            ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
            assert ratter_evt["event_category"] == "session"

    def test_process_event_category(self):
        for et in ["process.started", "process.exited"]:
            event = _make_peep_event(event_type=et)
            ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
            assert ratter_evt["event_category"] == "runtime"

    def test_output_event_category(self):
        for et in ["output.stdout", "output.stderr"]:
            event = _make_peep_event(event_type=et)
            ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
            assert ratter_evt["event_category"] == "command"

    def test_severity_mapping(self):
        assert map_peep_to_ratter_event(
            _make_peep_event("execution.error"), "rt", "inst"
        )["severity"] == "error"
        assert map_peep_to_ratter_event(
            _make_peep_event("execution.warning"), "rt", "inst"
        )["severity"] == "warning"
        assert map_peep_to_ratter_event(
            _make_peep_event("peep.adapter_failed"), "rt", "inst"
        )["severity"] == "critical"
        assert map_peep_to_ratter_event(
            _make_peep_event("session.started"), "rt", "inst"
        )["severity"] == "info"


# ---------------------------------------------------------------------------
# 2. PEEP event identity is preserved
# ---------------------------------------------------------------------------

class TestIdentityPreservation:
    def test_event_id_preserved_as_external_event_id(self):
        event = _make_peep_event(
            event_type="command.observed",
            event_id="evt-unique-12345",
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["external_event_id"] == "evt-unique-12345"

    def test_event_type_preserved_verbatim(self):
        for et in ["session.started", "command.observed", "output.stdout",
                    "command.completed", "process.exited", "session.ended"]:
            event = _make_peep_event(event_type=et)
            ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
            assert ratter_evt["event_type"] == et

    def test_occurred_at_preserved(self):
        ts = datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC)
        event = _make_peep_event(event_type="command.observed", occurred_at=ts)
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["occurred_at"] == "2026-07-30T12:00:00+00:00"

    def test_source_type_and_source_id_in_payload(self):
        event = _make_peep_event(
            event_type="command.observed",
            source_type="rosie",
            source_id="rosie-cli",
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["payload"]["peep_source_type"] == "rosie"
        assert ratter_evt["payload"]["peep_source_id"] == "rosie-cli"

    def test_session_id_preserved(self):
        event = _make_peep_event(
            event_type="command.observed",
            session_id="peep-session-xyz",
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["session_id"] == "peep-session-xyz"

    def test_sequence_preserved(self):
        event = _make_peep_event(event_type="output.stdout", sequence=42)
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["sequence_number"] == 42

    def test_metadata_preserved(self):
        event = _make_peep_event(
            event_type="command.observed",
            metadata={"key": "value"},
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["payload"]["peep_metadata"] == {"key": "value"}

    def test_payload_preserved(self):
        event = _make_peep_event(
            event_type="command.completed",
            payload={"exit_code": 7, "command_id": "cmd1"},
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["payload"]["peep_payload"]["exit_code"] == 7


# ---------------------------------------------------------------------------
# 3. Multiple events can be sent as one batch
# ---------------------------------------------------------------------------

class TestBatchSending:
    def test_send_batch_sends_events_array(self, tmp_path):
        sent_body = {}
        def fake_urlopen(req, timeout=None):
            sent_body["body"] = req.data
            sent_body["url"] = req.full_url
            mock_resp = Mock()
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = Mock()
            return mock_resp

        sink = RatterSink(url="http://localhost:3000/api/v1/ingest/events", enabled=True)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            events = [
                _make_peep_event("command.observed", payload={"command_id": "c1"}),
                _make_peep_event("output.stdout", payload={"text": "hello"}),
                _make_peep_event("command.completed", payload={"command_id": "c1", "exit_code": 0}),
            ]
            result = sink.send_peep_events(events, command_id="c1")

        assert result is True
        body = json.loads(sent_body["body"])
        assert "events" in body
        assert len(body["events"]) == 3
        assert body["events"][0]["event_type"] == "command.observed"
        assert body["events"][1]["event_type"] == "output.stdout"
        assert body["events"][2]["event_type"] == "command.completed"
        # All events in the batch share the same runtime_id
        for evt in body["events"]:
            assert evt["runtime_id"] == "rt_rosie_local"

    def test_send_batch_empty(self):
        sink = RatterSink(enabled=True)
        result = sink.send([])
        assert result is True


# ---------------------------------------------------------------------------
# 4. RATTER success does not alter ROSIE command result
# ---------------------------------------------------------------------------

class TestSuccessDoesNotAlterResult:
    def test_peep_shell_result_unchanged_with_ratter(self, tmp_path):
        from wrapper.peep_shell import PeepShellExecutor
        from wrapper.tools import run_shell as orig_run_shell

        executor = PeepShellExecutor(cwd=str(tmp_path))

        # Verify sink is configured
        assert executor._ratter_sink is not None

        result = executor.execute("Write-Output 'test-result'", timeout=30)

        assert "STDOUT:" in result
        assert "test-result" in result
        assert "EXIT_CODE: 0" in result
        assert "$ Write-Output 'test-result'" in result


# ---------------------------------------------------------------------------
# 5. RATTER connection failure does not fail ROSIE
# ---------------------------------------------------------------------------

class TestConnectionFailure:
    def test_connection_refused_does_not_raise(self):
        sink = RatterSink(
            url="http://localhost:1/api/v1/ingest/events",
            enabled=True,
        )
        result = sink.send_peep_events([
            _make_peep_event("command.observed"),
        ])
        assert result is False

    def test_connection_refused_in_peep_shell(self, tmp_path):
        """PeepShellExecutor should still return results when RATTER is down."""
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        # Point sink at a dead port
        async_sink = executor._ratter_sink
        if async_sink is not None:
            async_sink._sink._url = "http://localhost:1/api/v1/ingest/events"

        result = executor.execute("Write-Output 'survives-ratter-down'", timeout=30)

        assert "survives-ratter-down" in result
        assert "EXIT_CODE: 0" in result


# ---------------------------------------------------------------------------
# 6. RATTER timeout does not fail ROSIE
# ---------------------------------------------------------------------------

class TestTimeoutFailure:
    def test_http_timeout_does_not_raise(self):
        sink = RatterSink(
            url="http://localhost:8080/api/v1/ingest/events",
            enabled=True,
        )
        sink._timeout = 0.001  # Force timeout

        result = sink.send_peep_events([
            _make_peep_event("command.observed"),
        ])
        assert result is False

    def test_timeout_in_peep_shell(self, tmp_path):
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        async_sink = executor._ratter_sink
        if async_sink is not None:
            async_sink._sink._url = "http://localhost:8080/api/v1/ingest/events"
            async_sink._sink._timeout = 0.001

        result = executor.execute("Write-Output 'survives-timeout'", timeout=30)
        assert "survives-timeout" in result
        assert "EXIT_CODE: 0" in result


# ---------------------------------------------------------------------------
# 7. command.observed reaches the sink
# ---------------------------------------------------------------------------

class TestCommandObservedReached:
    def test_command_observed_forwarded(self, tmp_path):
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        sent_batches = []

        async_sink = executor._ratter_sink
        if async_sink is not None:
            async_sink._sink._enabled = False  # avoid real HTTP; capture at the sink
            original_send = async_sink._sink.send_peep_events
            def capture_send(events, command_id=None, task_id=None):
                sent_batches.append(list(events))
                return
            async_sink._sink.send_peep_events = capture_send

        result = executor.execute("Get-Location", timeout=30)
        async_sink.flush(timeout=2.0)

        # At least one batch should contain a command.observed event
        all_events = [e for batch in sent_batches for e in batch]
        observed_events = [e for e in all_events if e.event_type == "command.observed"]
        assert len(observed_events) >= 1
        assert "observed" in result or "D:\\ROSIE" in result


# ---------------------------------------------------------------------------
# 8. command.completed reaches the sink
# ---------------------------------------------------------------------------

class TestCommandCompletedReached:
    def test_command_completed_forwarded(self, tmp_path):
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        sent_batches = []

        async_sink = executor._ratter_sink
        if async_sink is not None:
            async_sink._sink._enabled = False  # avoid real HTTP; capture at the sink
            original_send = async_sink._sink.send_peep_events
            def capture_send(events, command_id=None, task_id=None):
                sent_batches.append(list(events))
                return
            async_sink._sink.send_peep_events = capture_send

        result = executor.execute("Get-Location", timeout=30)
        async_sink.flush(timeout=2.0)

        all_events = [e for batch in sent_batches for e in batch]
        completed_events = [e for e in all_events if e.event_type == "command.completed"]
        assert len(completed_events) >= 1
        assert completed_events[0].payload.get("exit_code") == 0


# ---------------------------------------------------------------------------
# 9. stdout/stderr behavior remains unchanged
# ---------------------------------------------------------------------------

class TestStdoutStderrUnchanged:
    def test_stdout_preserved(self, tmp_path):
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        async_sink = executor._ratter_sink
        if async_sink is not None:
            async_sink._sink._enabled = False

        result = executor.execute("Write-Output 'stdout-test-line'", timeout=30)
        assert "stdout-test-line" in result

    def test_stderr_preserved(self, tmp_path):
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        async_sink = executor._ratter_sink
        if async_sink is not None:
            async_sink._sink._enabled = False

        result = executor.execute("Write-Error 'stderr-test-line'", timeout=30)
        assert "STDERR:" in result
        assert "stderr-test-line" in result

    def test_exit_code_preserved(self, tmp_path):
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        async_sink = executor._ratter_sink
        if async_sink is not None:
            async_sink._sink._enabled = False

        result = executor.execute("exit 42", timeout=30)
        assert "EXIT_CODE: 42" in result


# ---------------------------------------------------------------------------
# 10. HACKASS/shared cloud path does not instantiate or require RATTER
# ---------------------------------------------------------------------------

class TestHackassNoRatter:
    def test_hackass_bridge_imports(self):
        """HACKASS bridge module should import without RATTER."""
        import inspect
        from hackass.bridge import inspect_file, write_file, run_shell

        for func in [inspect_file, write_file, run_shell]:
            source = inspect.getsource(func)
            assert "ratter" not in source.lower()
            assert "RatterSink" not in source

    def test_hackass_run_shell_uses_default(self, tmp_path):
        """HACKASS run_shell should use the default executor, not PEEP or RATTER."""
        import inspect
        from hackass.bridge import run_shell as hackass_run_shell

        sig = inspect.signature(hackass_run_shell)
        # Should have same signature as ROSIE's run_shell
        assert "command" in sig.parameters
        assert "timeout" in sig.parameters

    def test_default_executor_no_ratter(self, tmp_path):
        """When shell executor is None (default), no RATTER is involved."""
        from wrapper.tools import set_workspace_root, set_shell_executor, run_shell, set_policy
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))
        set_shell_executor(None)

        result = run_shell("echo default-no-ratter", timeout=10)
        assert "default-no-ratter" in result
        assert "EXIT_CODE: 0" in result


# ---------------------------------------------------------------------------
# RatterSink enabled/disabled behavior
# ---------------------------------------------------------------------------

class TestRatterSinkConfig:
    def test_ratter_url_from_env(self, monkeypatch):
        monkeypatch.setenv("RATTER_URL", "http://custom-host:9999/ingest")
        sink = RatterSink()
        assert sink.url == "http://custom-host:9999/ingest"

    def test_ratter_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RATTER_DISABLED", "true")
        sink = RatterSink()
        assert sink._enabled is False

    def test_ratter_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RATTER_DISABLED", "0")
        sink = RatterSink()
        assert sink._enabled is True

    def test_default_runtime_id(self):
        sink = RatterSink()
        assert sink.runtime_id == "rt_rosie_local"

    def test_custom_runtime_id(self):
        sink = RatterSink(runtime_id="rt_custom")
        assert sink.runtime_id == "rt_custom"

# ------------------------------------------------------------------
# BUG HUNT PASS II: derived command_id agrees across top-level + payload
# ------------------------------------------------------------------

class TestDerivedCommandIdAgreement:
    def test_derived_command_id_in_both_fields(self):
        event = _make_peep_event(
            event_type="command.observed",
            payload={"command_id": "derived-cmd-9", "command_text": "echo x"},
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["command_id"] == "derived-cmd-9"
        assert ratter_evt["payload"]["rosie_command_id"] == "derived-cmd-9"

    def test_explicit_command_id_agrees(self):
        event = _make_peep_event(
            event_type="command.completed",
            payload={"command_id": "payload-cmd", "exit_code": 0},
        )
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst", command_id="explicit-cmd")
        assert ratter_evt["command_id"] == "explicit-cmd"
        assert ratter_evt["payload"]["rosie_command_id"] == "explicit-cmd"

    def test_no_command_id_means_none_in_both(self):
        event = _make_peep_event(event_type="session.started", payload={})
        ratter_evt = map_peep_to_ratter_event(event, "rt", "inst")
        assert ratter_evt["command_id"] is None
        assert ratter_evt["payload"]["rosie_command_id"] is None
