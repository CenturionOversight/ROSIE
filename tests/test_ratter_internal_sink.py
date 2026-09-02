"""Focused tests for the RATTER sink's internal-of-default routing and its
nonfatal boundary, including the required failure proof.
"""
from __future__ import annotations

from wrapper.ratter_core import RatterCore
from wrapper.ratter_sink import RatterSink


class TestSinkModeSelection:
    def test_default_is_internal_core(self, monkeypatch):
        monkeypatch.delenv("RATTER_URL", raising=False)
        sink = RatterSink()
        assert sink.url is None
        assert sink.core is not None
        assert sink.core is get_core()

    def test_env_url_forces_http_mode(self, monkeypatch):
        monkeypatch.setenv("RATTER_URL", "http://custom-host:9999/ingest")
        sink = RatterSink()
        assert sink.url == "http://custom-host:9999/ingest"
        assert sink.core is None

    def test_explicit_url_forces_http_mode(self):
        sink = RatterSink(url="http://localhost:3000/api/v1/ingest/events")
        assert sink.url == "http://localhost:3000/api/v1/ingest/events"
        assert sink.core is None


def get_core():
    from wrapper.ratter_core import get_ratter_core

    return get_ratter_core()


class TestInternalSend:
    def test_send_ingests_into_core(self):
        core = RatterCore()
        sink = RatterSink(enabled=True)
        sink._core = core
        ok = sink.send([{"event_type": "process.started", "session_id": "iss1"}])
        assert ok is True
        assert len(core.events) == 1
        assert core.events[0]["session_id"] == "iss1"

    def test_send_disabled_returns_false(self):
        # Internal mode with enabled=False must not touch the core.
        core = RatterCore()
        sink = RatterSink(enabled=False)
        sink._core = core
        ok = sink.send([{"event_type": "process.started", "session_id": "iss2"}])
        assert ok is False
        assert len(core.events) == 0

    def test_empty_batch_is_true(self):
        sink = RatterSink(enabled=True)
        assert sink.send([]) is True


class TestNonfatalBoundary:
    """Core failure must never break ROSIE execution."""

    def test_core_failure_does_not_raise(self):
        sink = RatterSink(enabled=True)

        def _boom(_events):
            raise RuntimeError("core is on fire")

        sink._core = RatterCore()
        sink._core.ingest_events = _boom

        ok = sink.send([{"event_type": "process.started", "session_id": "boom"}])
        assert ok is False

    def test_executor_survives_internal_core_failure(self, tmp_path):
        """The command must complete even when the internal ingest raises."""
        from wrapper.peep_shell import PeepShellExecutor

        executor = PeepShellExecutor(cwd=str(tmp_path))
        assert executor._ratter_sink is not None

        def _boom(_events):
            raise RuntimeError("core is on fire")

        executor._ratter_sink._sink._core.ingest_events = _boom

        result = executor.execute("Write-Output still-works", timeout=30)
        assert "still-works" in result
        assert "EXIT_CODE: 0" in result
        executor.close()
