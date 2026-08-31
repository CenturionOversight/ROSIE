"""Focused tests for the turn-scoped task context (contextvars-based).

Covers the intended behavior from the execution-hardening cleanup pass:
- the task id is ``None`` outside any turn;
- set/reset with the returned token restores the previous value;
- the id is restored after a turn returns normally;
- the id is restored even when a turn body raises;
- nested set/reset restores correctly;
- distinct turns get distinct ids and stay isolated;
- the background RATTER worker captures the task id bound before a turn ends.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wrapper.rt_context import (
    get_current_task_id,
    reset_current_task_id,
    set_current_task_id,
)


@pytest.fixture(autouse=True)
def _clear_task_context():
    """Ensure no task context leaks across tests."""
    tid = get_current_task_id()
    if tid is not None:
        raise AssertionError("task context leaked into test: " + str(tid))
    yield
    assert get_current_task_id() is None, "test leaked task context"


class TestContextVarSetReset:
    def test_none_outside_any_turn(self):
        assert get_current_task_id() is None

    def test_set_returns_token_and_reset_restores(self):
        assert get_current_task_id() is None
        token = set_current_task_id("task_x")
        assert get_current_task_id() == "task_x"
        reset_current_task_id(token)
        assert get_current_task_id() is None

    def test_nested_set_reset_restores(self):
        outer = set_current_task_id("task_outer")
        inner = set_current_task_id("task_inner")
        assert get_current_task_id() == "task_inner"
        reset_current_task_id(inner)
        assert get_current_task_id() == "task_outer"
        reset_current_task_id(outer)
        assert get_current_task_id() is None

    def test_reset_out_of_order_token_is_harmless(self):
        outer = set_current_task_id("task_1")
        stale = set_current_task_id("task_2")
        active = set_current_task_id("task_3")
        # Resetting the now-out-of-order token must not raise or corrupt.
        reset_current_task_id(stale)
        # Clean up all tokens (innermost first) so the fixture sees the default.
        # Resetting `stale` above was out-of-order and silently failed, so the
        # context still holds "task_3"; resetting `active` then `outer` restores
        # the default None without leaving residual state.
        reset_current_task_id(active)
        reset_current_task_id(outer)


class TestTurnScopedLifecycle:
    def _run_turn(self, body):
        token = set_current_task_id("task_turn")
        try:
            body()
        finally:
            reset_current_task_id(token)

    def test_id_present_during_turn_and_cleared_after(self):
        observed = []

        def body():
            observed.append(get_current_task_id())

        self._run_turn(body)
        assert observed == ["task_turn"]
        assert get_current_task_id() is None

    def test_cleared_after_normal_return(self):
        self._run_turn(lambda: None)
        assert get_current_task_id() is None

    def test_cleared_after_exception(self):
        def exploding():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            self._run_turn(exploding)
        assert get_current_task_id() is None

    def test_distinct_turns_get_distinct_ids(self):
        from uuid import uuid4

        ids = []

        def capture():
            ids.append(get_current_task_id())

        for _ in range(2):
            token = set_current_task_id(f"task_{uuid4().hex[:8]}")
            try:
                capture()
            finally:
                reset_current_task_id(token)

        assert len(ids) == 2
        assert ids[0] is not None and ids[1] is not None
        assert ids[0] != ids[1]


class TestBackgroundRatterCapture:
    def test_worker_captures_task_id_bound_before_turn_ends(self):
        """The async sink forwards the turn's task id even after the turn ends.

        The PEEP executor reads the current id on the execution thread and
        passes it into the enqueue call, so the background worker forwards the
        already-bound value rather than re-reading a cleared context.
        """
        from wrapper.ratter_async import AsyncRatterSink

        inner = MagicMock()
        sink = AsyncRatterSink(sink=inner, auto_start=True)

        try:
            token = set_current_task_id("task_captured")

            class FakeEvent:
                event_type = "command.observed"

            try:
                sink.send_peep_events([FakeEvent()], command_id="c1", task_id="task_captured")
            finally:
                reset_current_task_id(token)

            # After the turn, the context is cleared...
            assert get_current_task_id() is None

            # ...but the worker still forwards the value captured at enqueue time.
            drained = sink.flush(timeout=2.0)
            assert drained is True
            kwargs = inner.send_peep_events.call_args.kwargs
            assert kwargs["task_id"] == "task_captured"
        finally:
            sink.close(timeout=2.0)
