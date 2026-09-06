"""Focused tests proving that runtime (RuntimeSession) owns workspace/policy/executor."""

from __future__ import annotations

import pytest

from wrapper.policy import ApprovalPolicy, ExecutionPolicy
from wrapper.runtime import RuntimeSession
from wrapper.tools import dispatch_tool


class TestRuntimeSessionDispatchIsolation:
    """dispatch_tool(["..."]) executed against an explicitly-scoped runtime
    uses that session's state (workspace, policy, executor), not defaults."""

    def test_workspace_root_isolation(self, tmp_path):
        # Runtime A sees only its workspace; runtime B sees only its own.
        ws_a = tmp_path / "ws_a"
        ws_a.mkdir()
        session_a = RuntimeSession(workspace=ws_a)
        session_b = RuntimeSession(workspace=tmp_path)

        (ws_a / "a.txt").write_text("unique-to-a")
        (session_b.workspace_root / "b.txt").write_text("unique-to-b")

        a1 = dispatch_tool("inspect_file", {"relative_path": "a.txt"}, runtime=session_a)
        assert "unique-to-a" in a1
        a2 = dispatch_tool("inspect_file", {"relative_path": "b.txt"}, runtime=session_a)
        assert "unique-to-b" not in a2

        b1 = dispatch_tool("inspect_file", {"relative_path": "b.txt"}, runtime=session_b)
        assert "unique-to-b" in b1
        b2 = dispatch_tool("inspect_file", {"relative_path": "a.txt"}, runtime=session_b)
        assert "unique-to-a" not in b2

    def test_policy_isolation(self, tmp_path, monkeypatch):
        ws = tmp_path
        (ws / "seed.txt").write_text("seed")

        yolo = RuntimeSession(workspace=ws, policy=ApprovalPolicy(ExecutionPolicy.YOLO))
        ask = RuntimeSession(workspace=ws, policy=ApprovalPolicy(ExecutionPolicy.ASK))
        monkeypatch.setattr("builtins.input", lambda *_: "n")

        yolo_res = dispatch_tool(
            "write_file", {"relative_path": "w.txt", "content": "y"}, runtime=yolo
        )
        ask_res = dispatch_tool(
            "write_file", {"relative_path": "a.txt", "content": "x"}, runtime=ask
        )

        assert "Successfully wrote" in yolo_res
        assert "DENIED" in ask_res
        assert (ws / "w.txt").read_text() == "y"
        assert not (ws / "a.txt").exists()

    def test_executor_lifecycle_independence(self):
        class _Exe:
            def __init__(self, name):
                self.name = name
                self.closed = False
            def __call__(self, command, timeout=None):
                return f"{self.name}:{command}"
            def close(self):
                self.closed = True

        a = RuntimeSession(shell_executor=_Exe("A"))
        b = RuntimeSession(shell_executor=_Exe("B"))
        a.close()
        assert a.is_closed()
        assert not b.is_closed()
        assert b.shell_executor.name == "B"
        b.close()
        assert b.is_closed()
        assert b.shell_executor is None


class TestRuntimeScopeApi:
    def test_default_session_still_works(self):
        assert RuntimeSession() is not None

    def test_runtime_exposed_via_dispatch_tool(self, tmp_path):
        """An explicit runtime= call controls the dispatch path."""
        (tmp_path / "t.txt").write_text("clean")
        session = RuntimeSession(workspace=tmp_path)
        rc = dispatch_tool("inspect_file", {"relative_path": "/no/such/path"}, runtime=session)
        assert "do not exist" in rc or "ERROR" in rc
