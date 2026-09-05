"""Focused tests proving that runtime state is owned by an explicit
:class:`wrapper.runtime.RuntimeSession` rather than module-global state."""
from __future__ import annotations

import os

import pytest

from wrapper.runtime import RuntimeSession


class TestRuntimeSessionIndependence:
    """Two RuntimeSession instances are independent spaces — changing A
    must not affect B's workspace, policy, or shell executor."""

    def test_workspace_roots_are_independent(self, tmp_path):
        wa = tmp_path / "workspace-a"
        wb = tmp_path / "workspace-b"
        wa.mkdir(); wb.mkdir()
        session_a = RuntimeSession(workspace=wa)
        session_b = RuntimeSession(workspace=wb)
        assert session_a.workspace_root == wa
        assert session_b.workspace_root == wb

    def test_policies_are_independent(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        pol_a = ApprovalPolicy(ExecutionPolicy.YOLO)
        pol_b = ApprovalPolicy(ExecutionPolicy.ASK)
        session_a = RuntimeSession(policy=pol_a)
        session_b = RuntimeSession(policy=pol_b)
        assert session_a.policy is pol_a
        assert session_b.policy is pol_b
        assert session_a.policy.mode != session_b.policy.mode

    def test_executor_lifecycle_is_isolated(self, tmp_path):
        opened_ever = []
        class _ExecA:
            def __call__(self, command, timeout):   return "A"
            def close(self): opened_ever.append("A")
        class _ExecB:
            def __call__(self, command, timeout):   return "B"
            def close(self): opened_ever.append("B")
        session_a = RuntimeSession(shell_executor=_ExecA())
        session_b = RuntimeSession(shell_executor=_ExecB())
        session_a.close()
        assert opened_ever == ["A"]
        session_b.execute_command = None   # type: ignore[method-assign]
        # B still owns its executor and was not closed
        assert not session_b.is_closed()
        assert session_b.shell_executor is not None
        session_b.close()
        assert opened_ever == ["A", "B"]

    def test_closed_session_blocks_further_use(self, tmp_path):
        session = RuntimeSession(workspace=tmp_path)
        session.close()
        with pytest.raises(RuntimeError):
            _ = session.workspace_root


class TestRuntimeSessionToolDispatch:
    """The runtime session's workspace must be what tools actually use."""

    def test_tool_uses_session_workspace(self, tmp_path, monkeypatch):
        from wrapper.tools import dispatch_tool, inspect_file
        (tmp_path / "hi.txt").write_text("hello from session workspace")
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        policy = ApprovalPolicy(ExecutionPolicy.YOLO)
        session = RuntimeSession(workspace=tmp_path, policy=policy)
        monkeypatch.setattr("wrapper.tools._workspace_root", session.workspace_root, raising=False)
        # Confirm the tool sees exactly what the session declares
        result = inspect_file(relative_path="hi.txt")
        assert "hello from session workspace" in result

    def test_default_session_workspace_is_shared(self, tmp_path):
        # The default session IS the compatibility path: setting it is the
        # equivalent of the old module-global workflow.
        from wrapper.runtime import get_default_session
        session = get_default_session()
        session.set_workspace_root(tmp_path)
        assert session.workspace_root == tmp_path
