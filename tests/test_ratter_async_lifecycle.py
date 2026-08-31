"""Focused tests for RATTER async sink flush/close lifecycle semantics.

Covers the intended behavior from the execution-hardening cleanup pass:
- ``flush`` genuinely waits for the worker to drain, returns promptly when
  drained, leaves the worker alive, and never blocks indefinitely;
- ``close`` stops accepting new telemetry, best-effort flushes, stops the
  worker, is idempotent, never raises, and logs anything unsent.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from wrapper.ratter_async import AsyncRatterSink


class _ImmediateSink:
    def __init__(self):
        self.calls = []

    def send_peep_events(self, events, command_id=None, task_id=None):
        self.calls.append((list(events), command_id, task_id))
        return True


class _BlockingSink:
    """send_peep_events blocks on a caller-controlled gate."""

    def __init__(self, gate):
        self.gate = gate
        self.started = threading.Event()

    def send_peep_events(self, events, command_id=None, task_id=None):
        self.started.set()
        self.gate.wait(10)


class _RaisingSink:
    def send_peep_events(self, events, command_id=None, task_id=None):
        raise RuntimeError("send failed")


def _fake_event(event_type="command.observed"):
    class FakeEvent:
        pass

    ev = FakeEvent()
    ev.event_type = event_type
    return ev


@pytest.fixture
def immediate_sink():
    return _ImmediateSink()


# ---------------------------------------------------------------------------
# flush semantics
# ---------------------------------------------------------------------------

class TestFlush:
    def test_flush_empty_returns_true_immediately(self):
        sink = AsyncRatterSink(auto_start=False)
        assert sink.flush(timeout=0.0) is True

    def test_flush_drains_queued_events(self, immediate_sink):
        sink = AsyncRatterSink(sink=immediate_sink, auto_start=True)
        try:
            assert sink.send_peep_events([_fake_event()], command_id="c1", task_id="t1") is True
            assert sink.send_peep_events([_fake_event()], command_id="c2", task_id="t1") is True
            assert sink.flush(timeout=2.0) is True
            assert len(immediate_sink.calls) == 2
        finally:
            sink.close(timeout=2.0)

    def test_flush_leaves_worker_alive(self, immediate_sink):
        sink = AsyncRatterSink(sink=immediate_sink, auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            assert sink.flush(timeout=2.0) is True
            worker = sink._worker
            assert worker is not None and worker.is_alive()
            # A subsequent drain still works after flush.
            sink.send_peep_events([_fake_event()])
            assert sink.flush(timeout=2.0) is True
            assert len(immediate_sink.calls) == 2
        finally:
            sink.close(timeout=2.0)

    def test_flush_is_bounded_when_worker_blocked(self):
        gate = threading.Event()
        sink = AsyncRatterSink(sink=_BlockingSink(gate), auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            block = sink._sink
            assert block.started.wait(2.0), "worker did not start processing"
            start = time.monotonic()
            drained = sink.flush(timeout=0.2)
            elapsed = time.monotonic() - start
            assert drained is False
            assert elapsed < 5.0, "flush blocked indefinitely"
        finally:
            gate.set()
            sink.close(timeout=2.0)

    def test_send_failure_still_marks_done(self):
        sink = AsyncRatterSink(sink=_RaisingSink(), auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            # The failed send was still processed, so the queue drained.
            assert sink.flush(timeout=2.0) is True
        finally:
            sink.close(timeout=2.0)

    def test_no_deadlock_under_concurrent_enqueue_and_flush(self, immediate_sink):
        sink = AsyncRatterSink(sink=immediate_sink, auto_start=True)
        try:
            stop = threading.Event()

            def producer():
                i = 0
                while not stop.is_set():
                    sink.send_peep_events([_fake_event()], command_id=f"c{i}")
                    i = (i + 1) % 1000

            t = threading.Thread(target=producer, daemon=True)
            t.start()
            try:
                for _ in range(5):
                    sink.flush(timeout=0.1)
            finally:
                stop.set()
            t.join(timeout=2.0)
        finally:
            sink.close(timeout=2.0)


# ---------------------------------------------------------------------------
# close semantics
# ---------------------------------------------------------------------------

class TestClose:
    def test_close_flushes_then_stops_worker(self, immediate_sink):
        sink = AsyncRatterSink(sink=immediate_sink, auto_start=True)
        sink.send_peep_events([_fake_event()], command_id="c1", task_id="t1")
        drained = sink.close(timeout=2.0)
        assert drained is True
        assert len(immediate_sink.calls) == 1
        assert immediate_sink.calls[0][1] == "c1"
        assert immediate_sink.calls[0][2] == "t1"
        worker = sink._worker
        assert worker is not None and not worker.is_alive()

    def test_close_is_bounded_when_worker_blocked(self):
        gate = threading.Event()
        sink = AsyncRatterSink(sink=_BlockingSink(gate), auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            assert sink._sink.started.wait(2.0)
            start = time.monotonic()
            drained = sink.close(timeout=0.2)
            elapsed = time.monotonic() - start
            assert drained is False
            assert elapsed < 5.0, "close blocked indefinitely"
        finally:
            gate.set()

    def test_close_is_idempotent(self, immediate_sink):
        sink = AsyncRatterSink(sink=immediate_sink, auto_start=True)
        sink.send_peep_events([_fake_event()])
        first = sink.close(timeout=2.0)
        second = sink.close(timeout=2.0)
        assert first is True
        assert second is True

    def test_send_after_close_returns_false(self, immediate_sink):
        sink = AsyncRatterSink(sink=immediate_sink, auto_start=True)
        sink.close(timeout=2.0)
        assert sink.send_peep_events([_fake_event()]) is False

    def test_close_logs_unsent_telemetry(self, caplog):
        gate = threading.Event()
        sink = AsyncRatterSink(sink=_BlockingSink(gate), auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            assert sink._sink.started.wait(2.0)
            with caplog.at_level("WARNING"):
                drained = sink.close(timeout=0.05)
            assert drained is False
            assert any(
                "not forwarded during shutdown" in r.message for r in caplog.records
            )
        finally:
            gate.set()

    def test_close_never_raises_with_failing_inner(self):
        sink = AsyncRatterSink(sink=_RaisingSink(), auto_start=True)
        sink.send_peep_events([_fake_event()])
        # Even though the send fails, close must not raise.
        sink.close(timeout=2.0)
        sink.close(timeout=2.0)
