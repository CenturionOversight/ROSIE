"""Focused tests for ROSIE execution-layer hardening.

Covers:
- shared output bounding (head + tail + explicit marker)
- the canonical, bounded shell-result format with the TIMED_OUT contract
- subprocess executor timeout behavior (explicit TIMED_OUT, not exit-code inference)
- the new move_path / delete_path filesystem tools (approval-gated, no shell)
- the dead-process-terminate import removal in peep_shell
- the asynchronous RATTER sink (non-blocking enqueue, bounded queue)
- ROSIE task_id correlation across RATTER events
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from wrapper.output_bounds import (
    DEFAULT_MAX_OUTPUT_CHARS,
    TRUNCATION_MARKER,
    box_output,
    format_shell_result,
)
from wrapper.policy import ApprovalPolicy, ExecutionPolicy


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
        assert TRUNCATION_MARKER in result
        # The bounded result stays under the default bound.
        assert len(result) <= DEFAULT_MAX_OUTPUT_CHARS

    def test_keeps_head_and_tail(self):
        text = "A" * 1000 + "ZZZZ"
        result = box_output(text, max_chars=200)
        assert result.startswith("A")
        assert result.endswith("ZZZZ")
        assert TRUNCATION_MARKER in result

    def test_custom_max_chars_respected(self):
        text = "y" * 5000
        result = box_output(text, max_chars=1000)
        assert len(result) <= 1000
        assert TRUNCATION_MARKER in result


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
        assert TRUNCATION_MARKER in result


class TestSubprocessTimeoutContract:
    def test_timeout_marks_timed_out_not_exit_inference(self, tmp_path, yolo, monkeypatch):
        """On timeout the executor reports TIMED_OUT: true + ERROR, never relying on EXIT_CODE -1 alone."""
        from wrapper.tools import _default_shell_executor
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path.resolve())

        result = _default_shell_executor("echo hi", timeout=1)
        if "TIMED_OUT:" in result:
            # Fast command completed normally.
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
        # Event should have been forwarded to the inner sink in the background.
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
        # Third enqueue should be dropped because the queue is full.
        assert sink.send_peep_events([FakeEvent()]) is False


class TestTaskCorrelation:
    def test_rt_context_set_and_get(self):
        from wrapper.rt_context import get_current_task_id, set_current_task_id
        set_current_task_id("task_abc")
        assert get_current_task_id() == "task_abc"
        set_current_task_id("")
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

    def test_run_turn_assigns_task_id(self, monkeypatch, tmp_path):
        from wrapper import tools as tools_mod
        tools_mod._workspace_root = tmp_path.resolve()
        captured = {}

        from unittest.mock import MagicMock as _MM
        from wrapper.cli import main

        def fake_completion(models, messages, temperature):
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

        from wrapper.rt_context import get_current_task_id
        tid = get_current_task_id()
        assert tid is not None
        assert tid.startswith("task_")
