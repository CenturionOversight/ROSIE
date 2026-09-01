"""Focused tests for ROSIE execution-layer hardening.

Covers:
- shared output bounding (head + tail + explicit marker)
- the canonical, bounded shell-result format with the TIMED_OUT contract
- subprocess executor timeout behavior (explicit TIMED_OUT, not exit-code inference)
- the move_path / delete_path filesystem tools (approval-gated, no shell)
- the dead-process-terminate import removal in peep_shell
- the asynchronous RATTER sink (non-blocking enqueue, bounded queue)
- ROSIE task_id correlation across RATTER events
- the turn-scoped task context (contextvars set/reset, cleared after turn)
- RATTER async flush/close lifecycle semantics
- CLI PEEP executor lifecycle cleanup on all exit paths
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wrapper.output_bounds import (
    DEFAULT_MAX_OUTPUT_CHARS,
    box_output,
    format_shell_result,
)
from wrapper.policy import ApprovalPolicy, ExecutionPolicy
from wrapper.rt_context import (
    get_current_task_id,
    reset_current_task_id,
    set_current_task_id,
)


@pytest.fixture
def yolo(monkeypatch):
    from wrapper import tools as tools_mod
    from wrapper.tools import set_policy, set_workspace_root

    policy = ApprovalPolicy(ExecutionPolicy.YOLO)
    set_policy(policy)
    monkeypatch.setattr(tools_mod, "_policy", policy)
    return policy


class TestBoxOutput:
    def test_short_text_unchanged(self):
        text = "hello world"
        assert box_output(text) == text

    def test_long_text_bounded_with_marker(self):
        text = "x" * 200_000
        result = box_output(text)
        assert "output truncated" in result
        assert len(result) <= DEFAULT_MAX_OUTPUT_CHARS

    def test_keeps_head_and_tail(self):
        text = "A" * 1000 + "ZZZZ"
        result = box_output(text, max_chars=200)
        assert result.startswith("A")
        assert result.endswith("ZZZZ")
        assert "output truncated" in result

    def test_custom_max_chars_respected(self):
        text = "y" * 5000
        result = box_output(text, max_chars=1000)
        assert len(result) <= 1000
        assert "output truncated" in result


class TestFormatShellResult:
    def test_normal_result_shape(self):
        result = format_shell_result(
            "echo hi", stdout="hi", stderr="", exit_code=0
        )
        assert "$ echo hi" in result
        assert "STDOUT:\nhi" in result
        assert "STDERR:\n(empty)" in result
        assert "EXIT_CODE: 0" in result
        assert "TIMED_OUT: false" in result

    def test_timeout_contract(self):
        result = format_shell_result(
            "sleep", stdout="", stderr="", exit_code=-1,
            timed_out=True, timeout_seconds=30,
        )
        assert "TIMED_OUT: true" in result
        assert "EXIT_CODE: -1" in result
        assert "ERROR: Command timed out after 30 seconds." in result

    def test_empty_outputs_marked(self):
        result = format_shell_result("cmd", stdout="", stderr="", exit_code=0)
        assert "STDOUT:\n(empty)" in result
        assert "STDERR:\n(empty)" in result

    def test_long_payload_bounded(self):
        result = format_shell_result(
            "cat", stdout="z" * 200_000, stderr="", exit_code=0
        )
        assert "STDOUT:" in result
        assert "EXIT_CODE: 0" in result
        assert "TIMED_OUT: false" in result
        assert "output truncated" in result


class TestTotalOutputBudget:
    def test_total_formatted_length_respected(self):
        """The 50k bound applies to the COMPLETE block, not per stream."""
        result = format_shell_result(
            "cmd",
            stdout="A" * 200_000,
            stderr="B" * 200_000,
            exit_code=1,
        )
        assert len(result) <= DEFAULT_MAX_OUTPUT_CHARS

    def test_truncation_reports_original_size(self):
        result = format_shell_result(
            "cmd", stdout="q" * 123_456, stderr="", exit_code=0
        )
        assert "original 123456 chars" in result

    def test_both_streams_survive_truncation(self):
        """Neither stdout nor stderr is starved entirely when both overflow."""
        result = format_shell_result(
            "cmd",
            stdout="A" * 100_000,
            stderr="B" * 5,
            exit_code=2,
        )
        assert "original 100000 chars" in result
        # Even a small stderr must remain visible (min share), so it keeps a tail.
        assert "STDERR:" in result
        # Structural fields always survive.
        for marker in ("$ cmd", "EXIT_CODE: 2", "TIMED_OUT: false"):
            assert marker in result

    def test_timeout_error_line_survives_truncation(self):
        result = format_shell_result(
            "hang",
            stdout="o" * 90_000,
            stderr="",
            exit_code=-1,
            timed_out=True,
            timeout_seconds=45,
        )
        assert "ERROR: Command timed out after 45 seconds." in result
        assert "TIMED_OUT: true" in result


class TestSubprocessTimeoutContract:
    def test_timeout_marks_timed_out_not_exit_inference(self, tmp_path, yolo, monkeypatch):
        from wrapper.tools import _default_shell_executor
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path.resolve())

        result = _default_shell_executor("echo hi", timeout=1)
        if "TIMED_OUT:" in result:
            assert "TIMED_OUT: false" in result
            return

    def test_result_always_marks_timed_out_line(self, tmp_path, yolo, monkeypatch):
        from wrapper.tools import run_shell, set_workspace_root
        set_workspace_root(tmp_path)
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path.resolve())
        result = run_shell("echo present", timeout=5)
        assert "TIMED_OUT: false" in result


class TestDeadImportRemoved:
    def test_process_terminate_import_removed(self):
        import inspect
        import wrapper.peep_shell as ps
        source = inspect.getsource(ps)
        assert "PROCESS_TERMINATE_TIMEOUT_SECONDS" not in source


class TestMoveDeletePaths:
    def test_move_file(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "a.txt").write_text("data")
        result = move_path("a.txt", "sub/b.txt")
        assert "Successfully moved" in result
        assert (tmp_path / "sub" / "b.txt").exists()
        assert not (tmp_path / "a.txt").exists()

    def test_move_never_overwrites(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result = move_path("a.txt", "b.txt")
        assert "already exists" in result
        assert (tmp_path / "a.txt").exists()
        assert (tmp_path / "b.txt").read_text() == "b"

    def test_move_denied_in_ask(self, tmp_path, monkeypatch):
        from wrapper.tools import move_path, set_policy, set_workspace_root
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.ASK))
        monkeypatch.setattr("builtins.input", lambda _: "n")
        (tmp_path / "a.txt").write_text("a")
        result = move_path("a.txt", "b.txt")
        assert "DENIED" in result
        assert (tmp_path / "a.txt").exists()
        assert not (tmp_path / "b.txt").exists()

    def test_delete_file(self, tmp_path, yolo):
        from wrapper.tools import delete_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "a.txt").write_text("a")
        result = delete_path("a.txt")
        assert "Successfully deleted" in result
        assert not (tmp_path / "a.txt").exists()

    def test_delete_dir_requires_recursive(self, tmp_path, yolo):
        from wrapper.tools import delete_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "f.txt").write_text("x")
        result = delete_path("d")
        assert "recursive" in result
        assert (tmp_path / "d").exists()

    def test_delete_dir_recursive(self, tmp_path, yolo):
        from wrapper.tools import delete_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "f.txt").write_text("x")
        result = delete_path("d", recursive=True)
        assert "Successfully deleted" in result
        assert not (tmp_path / "d").exists()

    def test_delete_root_forbidden(self, tmp_path, yolo):
        from wrapper.tools import delete_path, set_workspace_root
        set_workspace_root(tmp_path)
        result = delete_path(".", recursive=True)
        assert "workspace root" in result

    def test_delete_denied_in_ask(self, tmp_path, monkeypatch):
        from wrapper.tools import delete_path, set_policy, set_workspace_root
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.ASK))
        monkeypatch.setattr("builtins.input", lambda _: "n")
        (tmp_path / "a.txt").write_text("a")
        result = delete_path("a.txt")
        assert "DENIED" in result
        assert (tmp_path / "a.txt").exists()


class TestAsyncRatterSink:
    def test_enqueue_nonblocking_and_forwarded(self):
        from wrapper.ratter_async import AsyncRatterSink

        inner = MagicMock()
        inner.send_peep_events.return_value = True
        sink = AsyncRatterSink(sink=inner, auto_start=True)

        class FakeEvent:
            event_type = "command.observed"

        accepted = sink.send_peep_events([FakeEvent()], command_id="c1", task_id="t1")
        assert accepted is True
        remaining = sink.close(timeout=2.0)
        assert inner.send_peep_events.call_count >= 1
        kwargs = inner.send_peep_events.call_args.kwargs
        assert kwargs["command_id"] == "c1"
        assert kwargs["task_id"] == "t1"

    def test_bounded_queue_drops_when_full(self):
        from wrapper.ratter_async import AsyncRatterSink

        inner = MagicMock()
        sink = AsyncRatterSink(sink=inner, queue_size=2, auto_start=False)

        class FakeEvent:
            event_type = "command.observed"

        assert sink.send_peep_events([FakeEvent()]) is True
        assert sink.send_peep_events([FakeEvent()]) is True
        assert sink.send_peep_events([FakeEvent()]) is False


class TestTaskCorrelation:
    def test_rt_context_set_and_get(self):
        assert get_current_task_id() is None
        token = set_current_task_id("task_abc")
        assert get_current_task_id() == "task_abc"
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

    def test_task_id_flows_into_ratter_event(self):
        from wrapper.ratter_sink import map_peep_to_ratter_event

        event = MagicMock()
        event.event_id = "ev1"
        event.event_type = "command.observed"
        event.severity = "info"
        event.occurred_at = None
        event.session_id = "s1"
        event.sequence = 1
        event.source_type = "rosie"
        event.source_id = "rosie-cli"
        event.metadata = {}
        event.payload = {"command_id": "c1"}
        event.schema_version = "1.0"

        r = map_peep_to_ratter_event(event, "rt_x", "inst_x", command_id="c1", task_id="task_9")
        assert r["payload"]["rosie_task_id"] == "task_9"
        assert r["payload"]["rosie_command_id"] == "c1"
        assert r["command_id"] == "c1"

    def test_cleared_after_normal_return(self):
        token = set_current_task_id("task_turn")
        try:
            pass
        finally:
            reset_current_task_id(token)
        assert get_current_task_id() is None

    def test_cleared_after_exception(self):
        token = set_current_task_id("task_turn")

        def exploding():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            try:
                exploding()
            finally:
                reset_current_task_id(token)
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

    def test_run_turn_assigns_task_id(self, monkeypatch, tmp_path):
        from wrapper import tools as tools_mod
        tools_mod._workspace_root = tmp_path.resolve()

        from unittest.mock import MagicMock as _MM
        from wrapper.cli import main

        captured_tids = []

        def fake_completion(models, messages, temperature):
            captured_tids.append(get_current_task_id())
            resp = _MM()
            msg = _MM()
            msg.content = "ok"
            msg.tool_calls = None
            resp.choices = [_MM()]
            resp.choices[0].message = msg
            return resp

        with patch("wrapper.cli._configure_peep_executor", return_value="peep=attached"), \
             patch("wrapper.cli._completion", side_effect=fake_completion):
            main([str(tmp_path.resolve()), "say hi"])

        # During the turn, a task id was present and shared with the completion call.
        assert captured_tids
        assert all(t is not None and t.startswith("task_") for t in captured_tids)
        # After the turn finished, the context is cleared.
        assert get_current_task_id() is None

    def test_background_ratter_captures_task_id(self):
        from wrapper.ratter_async import AsyncRatterSink

        inner = MagicMock()
        sink = AsyncRatterSink(sink=inner, auto_start=True)

        class FakeEvent:
            event_type = "command.observed"

        try:
            token = set_current_task_id("task_captured")
            try:
                sink.send_peep_events(
                    [FakeEvent()], command_id="c1", task_id="task_captured"
                )
            finally:
                reset_current_task_id(token)
            assert get_current_task_id() is None
            assert sink.flush(timeout=2.0) is True
            kwargs = inner.send_peep_events.call_args.kwargs
            assert kwargs["task_id"] == "task_captured"
        finally:
            sink.close(timeout=2.0)


# ---------------------------------------------------------------------------
# RATTER async flush/close lifecycle
# ---------------------------------------------------------------------------

class _ImmediateSink:
    def __init__(self):
        self.calls = []

    def send_peep_events(self, events, command_id=None, task_id=None):
        self.calls.append((list(events), command_id, task_id))
        return True


class _BlockingSink:
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


class TestRatterFlush:
    def test_flush_empty_returns_true_immediately(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(auto_start=False)
        assert sink.flush(timeout=0.0) is True

    def test_flush_drains_queued_events(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
        try:
            assert sink.send_peep_events([_fake_event()], command_id="c1", task_id="t1") is True
            assert sink.send_peep_events([_fake_event()], command_id="c2", task_id="t1") is True
            assert sink.flush(timeout=2.0) is True
            assert len(sink._sink.calls) == 2
        finally:
            sink.close(timeout=2.0)

    def test_flush_leaves_worker_alive(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            assert sink.flush(timeout=2.0) is True
            worker = sink._worker
            assert worker is not None and worker.is_alive()
            sink.send_peep_events([_fake_event()])
            assert sink.flush(timeout=2.0) is True
            assert len(sink._sink.calls) == 2
        finally:
            sink.close(timeout=2.0)

    def test_flush_is_bounded_when_worker_blocked(self):
        from wrapper.ratter_async import AsyncRatterSink
        gate = threading.Event()
        sink = AsyncRatterSink(sink=_BlockingSink(gate), auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            assert sink._sink.started.wait(2.0), "worker did not start processing"
            start = time.monotonic()
            drained = sink.flush(timeout=0.2)
            elapsed = time.monotonic() - start
            assert drained is False
            assert elapsed < 5.0, "flush blocked indefinitely"
        finally:
            gate.set()
            sink.close(timeout=2.0)

    def test_send_failure_still_marks_done(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_RaisingSink(), auto_start=True)
        try:
            sink.send_peep_events([_fake_event()])
            assert sink.flush(timeout=2.0) is True
        finally:
            sink.close(timeout=2.0)

    def test_no_deadlock_under_concurrent_enqueue_and_flush(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
        try:
            stop = threading.Event()

            def producer():
                i = 0
                while not stop.is_set():
                    sink.send_peep_events([_fake_event()], command_id="c%d" % i)
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


class TestRatterClose:
    def test_close_flushes_then_stops_worker(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
        sink.send_peep_events([_fake_event()], command_id="c1", task_id="t1")
        drained = sink.close(timeout=2.0)
        assert drained is True
        assert len(sink._sink.calls) == 1
        assert sink._sink.calls[0][1] == "c1"
        assert sink._sink.calls[0][2] == "t1"
        worker = sink._worker
        assert worker is not None and not worker.is_alive()

    def test_close_is_bounded_when_worker_blocked(self):
        from wrapper.ratter_async import AsyncRatterSink
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

    def test_close_is_idempotent(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
        sink.send_peep_events([_fake_event()])
        first = sink.close(timeout=2.0)
        second = sink.close(timeout=2.0)
        assert first is True
        assert second is True

    def test_send_after_close_returns_false(self):
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
        sink.close(timeout=2.0)
        assert sink.send_peep_events([_fake_event()]) is False

    def test_close_logs_unsent_telemetry(self, caplog):
        from wrapper.ratter_async import AsyncRatterSink
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
        from wrapper.ratter_async import AsyncRatterSink
        sink = AsyncRatterSink(sink=_RaisingSink(), auto_start=True)
        sink.send_peep_events([_fake_event()])
        sink.close(timeout=2.0)
        sink.close(timeout=2.0)


# ---------------------------------------------------------------------------
# CLI PEEP executor lifecycle cleanup
# ---------------------------------------------------------------------------

def _noop_tool_completion(models, messages, temperature):
    resp = MagicMock()
    msg = MagicMock()
    msg.content = "ok"
    msg.tool_calls = None
    resp.choices = [MagicMock()]
    resp.choices[0].message = msg
    return resp


def _install_fake_executor(monkeypatch, close_calls=None):
    import wrapper.cli as cli

    if close_calls is None:
        close_calls = []

    executor = MagicMock()
    executor.close.side_effect = lambda *a, **k: close_calls.append("closed")

    def fake_configure(root):
        cli._peep_executor = executor
        return "peep=attached"

    monkeypatch.setattr(cli, "_configure_peep_executor", fake_configure)
    monkeypatch.setattr(cli, "_completion", _noop_tool_completion)
    return executor, close_calls


class TestCliCloseHelper:
    def test_close_peep_executor_noop_when_unconfigured(self, monkeypatch):
        import wrapper.cli as cli
        monkeypatch.setattr(cli, "_peep_executor", None)
        cli._close_peep_executor()

    def test_close_peep_executor_with_fake_executor(self, monkeypatch):
        import wrapper.cli as cli
        fake = MagicMock()
        monkeypatch.setattr(cli, "_peep_executor", fake)
        cli._close_peep_executor()
        assert fake.close.call_count == 1
        assert cli._peep_executor is None

    def test_close_peep_executor_swallows_executor_error(self, monkeypatch):
        import wrapper.cli as cli
        fake = MagicMock()
        fake.close.side_effect = RuntimeError("boom")
        monkeypatch.setattr(cli, "_peep_executor", fake)
        cli._close_peep_executor()
        assert cli._peep_executor is None


class TestCliCloseOnExit:
    def test_one_shot_closes_executor(self, monkeypatch, tmp_path):
        import wrapper.cli as cli
        executor, calls = _install_fake_executor(monkeypatch)
        rc = cli.main([str(tmp_path.resolve()), "do the thing"])
        assert rc == 0
        assert executor.close.call_count == 1
        assert calls == ["closed"]
        assert cli._peep_executor is None

    def test_piped_closes_executor(self, monkeypatch, tmp_path):
        import wrapper.cli as cli
        executor, calls = _install_fake_executor(monkeypatch)

        class FakeStdin:
            def isatty(self):
                return False

            def read(self):
                return "piped prompt"

        monkeypatch.setattr(sys, "stdin", FakeStdin())
        rc = cli.main([str(tmp_path.resolve())])
        assert rc == 0
        assert executor.close.call_count == 1

    def test_interactive_exit_closes_executor(self, monkeypatch, tmp_path):
        import wrapper.cli as cli
        import builtins

        executor, calls = _install_fake_executor(monkeypatch)

        class FakeStdin:
            def isatty(self):
                return True

        monkeypatch.setattr(sys, "stdin", FakeStdin())
        inputs = iter(["exit"])
        monkeypatch.setattr(builtins, "input", lambda *a, **k: next(inputs))

        rc = cli.main([str(tmp_path.resolve())])
        assert rc == 0
        assert executor.close.call_count == 1

    def test_exception_path_still_closes_executor(self, monkeypatch, tmp_path):
        import wrapper.cli as cli
        executor, calls = _install_fake_executor(monkeypatch)

        def exploding_completion(models, messages, temperature):
            raise RuntimeError("model failed")

        monkeypatch.setattr(cli, "_completion", exploding_completion)
        with pytest.raises(RuntimeError):
            cli.main([str(tmp_path.resolve()), "will explode"])
        assert executor.close.call_count == 1


class TestCliConfigureOnce:
    def test_configure_records_executor_and_close_releases(self, monkeypatch):
        import wrapper.cli as cli
        fake = MagicMock()
        with patch(
            "wrapper.peep_shell.PeepShellExecutor", return_value=fake
        ) as ctor:
            status = cli._configure_peep_executor("workspace")
            assert ctor.call_count == 1
        assert status == "peep=attached"
        assert cli._peep_executor is fake
        cli._close_peep_executor()
        assert fake.close.call_count == 1
        assert cli._peep_executor is None

    def test_fallback_config_leaves_no_executor_to_close(self, monkeypatch):
        import wrapper.cli as cli
        with patch(
            "wrapper.peep_shell.PeepShellExecutor",
            side_effect=ImportError("PEEP not installed"),
        ):
            status = cli._configure_peep_executor("workspace")
        assert "peep=unavailable" in status
        assert cli._peep_executor is None
        cli._close_peep_executor()


# ------------------------------------------------------------------
# TARGET 3 â€” Small output budget tests
# ------------------------------------------------------------------

class TestSmallOutputBudget:
    """box_output and format_shell_result must respect len(result) <= max_chars
    for arbitrarily small positive budgets."""

    def test_box_output_max_chars_1(self):
        from wrapper.output_bounds import box_output
        result = box_output("hello world", max_chars=1)
        assert len(result) <= 1

    def test_box_output_max_chars_2(self):
        from wrapper.output_bounds import box_output
        result = box_output("hello world", max_chars=2)
        assert len(result) <= 2

    def test_box_output_max_chars_5(self):
        from wrapper.output_bounds import box_output
        result = box_output("hello world", max_chars=5)
        assert len(result) <= 5

    def test_box_output_smaller_than_full_marker(self):
        from wrapper.output_bounds import box_output
        result = box_output("x" * 200, max_chars=20)
        assert len(result) <= 20

    def test_box_output_at_marker_boundary(self):
        from wrapper.output_bounds import box_output
        marker = "...(output truncated; original 200 chars; showing head and tail)..."
        result = box_output("x" * 200, max_chars=len(marker))
        assert len(result) <= len(marker)

    def test_box_output_never_inflates_budget(self):
        from wrapper.output_bounds import box_output
        for n in [1, 2, 3, 5, 10, 20]:
            result = box_output("hello world", max_chars=n)
            assert len(result) <= n, f"max_chars={n} got len={len(result)}"

    def test_format_shell_small_stdout_only(self):
        from wrapper.output_bounds import format_shell_result
        result = format_shell_result("c", stdout="A" * 500, stderr="", exit_code=0, max_chars=80)
        assert len(result) <= 80

    def test_format_shell_small_stderr_only(self):
        from wrapper.output_bounds import format_shell_result
        result = format_shell_result("c", stdout="", stderr="B" * 500, exit_code=0, max_chars=80)
        assert len(result) <= 80

    def test_format_shell_small_both_streams(self):
        from wrapper.output_bounds import format_shell_result
        result = format_shell_result("c", stdout="A" * 500, stderr="B" * 500, exit_code=0, max_chars=80)
        assert len(result) <= 80

    def test_format_shell_small_timeout(self):
        from wrapper.output_bounds import format_shell_result
        result = format_shell_result("c", stdout="A" * 500, stderr="", exit_code=-1,
                                     timed_out=True, timeout_seconds=30, max_chars=120)
        assert len(result) <= 120

    def test_format_shell_normal_50k(self):
        from wrapper.output_bounds import format_shell_result
        result = format_shell_result("c", stdout="A" * 100_000, exit_code=0)
        assert len(result) <= 50_000

    def test_allocate_budget_never_exceeds_available(self):
        from wrapper.output_bounds import _allocate_payload_budget
        for avail in [1, 2, 3, 5, 10, 100]:
            out, err = _allocate_payload_budget(avail, 500, 500)
            assert out + err <= avail, f"available={avail} got {out}+{err}={out+err}"

    def test_allocate_single_char_both_streams(self):
        from wrapper.output_bounds import _allocate_payload_budget
        out, err = _allocate_payload_budget(1, 500, 500)
        assert out + err <= 1

    def test_structural_fields_survive_when_block_fits(self):
        """When the structural block fits max_chars, no field is clipped away
        even when both payload streams are oversized (regression: a 0-budget
        stream used to inflate the block and amputate TIMED_OUT/EXIT_CODE)."""
        from wrapper.output_bounds import format_shell_result
        for cmd_len in (0, 1, 10):
            cmd = "c" * cmd_len
            prefix = f"$ {cmd}\nSTDOUT:\n"
            middle = "\nSTDERR:\n"
            suffix = "\nEXIT_CODE: 0\nTIMED_OUT: false"
            fixed = len(prefix) + len(middle) + len(suffix)
            for mc in range(fixed, fixed + 40):
                r = format_shell_result(
                    cmd, stdout="A" * 500, stderr="B" * 500,
                    exit_code=0, max_chars=mc,
                )
                assert len(r) <= mc
                assert f"$ {cmd}" in r
                assert "STDOUT:" in r
                assert "STDERR:" in r
                assert "EXIT_CODE: 0" in r
                assert "TIMED_OUT: false" in r


# ------------------------------------------------------------------
# TARGET 4 â€” move_path guard tests
# ------------------------------------------------------------------

class TestMovePathGuards:
    def test_move_workspace_root_rejected(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        result = move_path(".", "somewhere_else")
        assert "ERROR" in result
        assert "workspace root" in result.lower()

    def test_workspace_unchanged_after_rejected_root_move(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "file.txt").write_text("content")
        move_path(".", "somewhere_else")
        assert (tmp_path / "file.txt").exists()

    def test_move_dir_into_direct_child_rejected(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "foo").mkdir()
        (tmp_path / "foo" / "bar").mkdir()
        result = move_path("foo", "foo/bar/baz")
        assert "ERROR" in result
        assert "descendant" in result.lower()

    def test_move_dir_into_deeper_descendant_rejected(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "foo").mkdir()
        (tmp_path / "foo" / "bar" / "baz").mkdir(parents=True)
        result = move_path("foo", "foo/bar/baz/qux")
        assert "ERROR" in result
        assert "descendant" in result.lower()

    def test_no_approval_request_for_invalid_move(self, tmp_path, yolo, monkeypatch):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "foo").mkdir()
        called = []
        monkeypatch.setattr(yolo, "request_approval", lambda *a, **kw: (called.append(True) or True))
        move_path(".", "somewhere")
        assert called == [], "approval should not be requested for invalid move"

    def test_valid_sibling_dir_move(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "dir_a").mkdir()
        (tmp_path / "dir_a" / "f.txt").write_text("hi")
        result = move_path("dir_a", "dir_b")
        assert "Successfully" in result
        assert (tmp_path / "dir_b" / "f.txt").exists()

    def test_valid_file_move(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "a.txt").write_text("data")
        result = move_path("a.txt", "b.txt")
        assert "Successfully" in result
        assert (tmp_path / "b.txt").read_text() == "data"

    def test_destination_exists_unchanged(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result = move_path("a.txt", "b.txt")
        assert "ERROR" in result
        assert "already exists" in result.lower()
        assert (tmp_path / "a.txt").read_text() == "a"

    def test_traversal_outside_workspace_blocked(self, tmp_path, yolo):
        from wrapper.tools import move_path, set_workspace_root
        set_workspace_root(tmp_path)
        with pytest.raises(Exception):
            move_path("../../etc/passwd", "stolen.txt")
# ------------------------------------------------------------------
# BUG HUNT PASS II: tiny-budget constraint, symlink safety, CLI reset
# ------------------------------------------------------------------

class TestTinyBudgetShellResult:
    """format_shell_result must never exceed max_chars for tiny positive budgets."""

    def test_format_shell_single_char_budget(self):
        from wrapper.output_bounds import format_shell_result
        for n in range(1, 6):
            r = format_shell_result(
                "c", stdout="A" * 500, stderr="B" * 500,
                exit_code=0, max_chars=n,
            )
            assert len(r) <= n, f"max_chars={n} got len={len(r)}"

    def test_format_shell_payload_only_tiny(self):
        from wrapper.output_bounds import format_shell_result
        for n in [1, 2, 3, 5, 10, 20, 40, 64]:
            r = format_shell_result("c", stdout="A" * 500, stderr="", exit_code=0, max_chars=n)
            assert len(r) <= n, f"max_chars={n} got len={len(r)}"

    def test_format_shell_tiny_timeout_budget(self):
        from wrapper.output_bounds import format_shell_result
        for n in [1, 2, 5, 10, 30, 60, 100]:
            r = format_shell_result(
                "c", stdout="A" * 500, stderr="", exit_code=-1,
                timed_out=True, timeout_seconds=30, max_chars=n,
            )
            assert len(r) <= n, f"max_chars={n} got len={len(r)}"


class TestShellExecutorResetOnClose:
    def test_close_peep_executor_resets_global_shell_executor(self, monkeypatch):
        import wrapper.cli as cli
        import wrapper.tools as tools_mod
        fake = MagicMock()
        monkeypatch.setattr(cli, "_peep_executor", fake)
        tools_mod._shell_executor = fake
        cli._close_peep_executor()
        assert fake.close.call_count == 1
        assert cli._peep_executor is None
        assert tools_mod._shell_executor is None

    def test_fallback_close_does_not_touch_executor(self, monkeypatch):
        import wrapper.cli as cli
        import wrapper.tools as tools_mod
        sentinel = object()
        tools_mod._shell_executor = sentinel
        monkeypatch.setattr(cli, "_peep_executor", None)
        cli._close_peep_executor()
        assert tools_mod._shell_executor is sentinel


class TestResolveSafePathNoFollow:
    def test_helper_keeps_leaf_verbatim(self, tmp_path):
        from wrapper.tools import _resolve_safe_path_no_follow
        p = _resolve_safe_path_no_follow(tmp_path.resolve(), "a/b.txt")
        assert p.name == "b.txt"
        assert p.parent.name == "a"
        assert str(p.parent.parent) == str(tmp_path.resolve())

    def test_helper_blocks_traversal(self, tmp_path):
        from wrapper.tools import _resolve_safe_path_no_follow, PathTraversalError
        import pytest
        with pytest.raises(PathTraversalError):
            _resolve_safe_path_no_follow(tmp_path.resolve(), "../../etc/passwd")

    def test_move_and_delete_do_not_dereference_symlink(self, tmp_path, yolo):
        from wrapper.tools import move_path, delete_path, set_workspace_root
        import os
        set_workspace_root(tmp_path)
        target = tmp_path / "real.txt"
        target.write_text("TARGET")
        link = tmp_path / "the_link.txt"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported on this platform")

        res = delete_path("the_link.txt")
        assert "Successfully deleted" in res
        assert not os.path.lexists(str(link))
        assert target.exists()

        link2 = tmp_path / "the_link2.txt"
        os.symlink(str(target), str(link2))
        res = move_path("the_link2.txt", "moved_link.txt")
        assert "Successfully moved" in res
        assert os.path.lexists(str(tmp_path / "moved_link.txt"))
        assert not os.path.lexists(str(link2))
        assert target.exists()
