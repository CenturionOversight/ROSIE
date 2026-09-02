"""Focused tests for the PEEP shell integration into ROSIE.

Tests cover:
- approval behavior still gates shell execution (with PEEP executor)
- local CLI configures the PEEP executor
- PEEP-backed shell execution returns the existing result format
- stdout is preserved
- stderr is preserved
- exit code is preserved
- workspace cwd is respected
- default executor still works without PEEP configured
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from wrapper.peep_shell import PeepShellExecutor


class TestApprovalGate:
    """Verify approval policy still gates shell execution with PEEP."""

    def test_peep_executor_approval_denied(self, tmp_path, monkeypatch):
        """Denial in ask mode should prevent execution entirely."""
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        monkeypatch.setattr("wrapper.tools._shell_executor", PeepShellExecutor(cwd=str(tmp_path)), raising=False)

        ask_policy = ApprovalPolicy(ExecutionPolicy.ASK)
        set_policy(ask_policy)

        from wrapper.tools import run_shell

        with patch("builtins.input", side_effect=EOFError):
            result = run_shell(command="echo test")
            assert "DENIED" in result

    def test_peep_executor_approval_granted(self, tmp_path, monkeypatch):
        """Approval in ask mode should allow execution through PEEP."""
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        monkeypatch.setattr("wrapper.tools._shell_executor", PeepShellExecutor(cwd=str(tmp_path)), raising=False)

        ask_policy = ApprovalPolicy(ExecutionPolicy.ASK)
        set_policy(ask_policy)

        from wrapper.tools import run_shell

        with patch("builtins.input", return_value="y"):
            result = run_shell(command="Write-Output 'approved'")
            assert "approved" in result
            assert "EXIT_CODE: 0" in result


class TestLocalCliConfiguresPeep:
    """Verify local CLI configures the PEEP executor."""

    def test_cli_configures_peep_executor(self, tmp_path):
        """_configure_peep_executor should call set_shell_executor."""
        import wrapper.tools as tools_mod
        from wrapper import cli

        original = tools_mod._shell_executor
        tools_mod._shell_executor = None
        try:
            cli._configure_peep_executor(tmp_path)
            assert tools_mod._shell_executor is not None
            assert isinstance(tools_mod._shell_executor, PeepShellExecutor)
            assert tools_mod._shell_executor._cwd == str(tmp_path)
        finally:
            tools_mod._shell_executor = original

    def test_peep_not_available_falls_back(self, tmp_path):
        """When PEEP is not importable, the default executor is used."""
        import builtins

        import wrapper.tools as tools_mod
        from wrapper import cli

        original = tools_mod._shell_executor
        tools_mod._shell_executor = None
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "wrapper.peep_shell" or name == "peep":
                raise ImportError("No PEEP")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = mock_import
        try:
            cli._configure_peep_executor(tmp_path)
            # _shell_executor should remain None (not configured)
            assert tools_mod._shell_executor is None
        finally:
            builtins.__import__ = real_import
            tools_mod._shell_executor = original


class TestPeepResultFormat:
    """Verify PEEP-backed shell returns the existing ROSIE result format."""

    def test_peep_result_has_command_line(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import run_shell, set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        import wrapper.tools as tools_mod
        from wrapper.peep_shell import PeepShellExecutor
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("Write-Output 'hello'", timeout=30)
        finally:
            tools_mod._shell_executor = original

        assert "$ Write-Output 'hello'" in result
        assert "STDOUT:" in result
        assert "STDERR:" in result
        assert "EXIT_CODE:" in result

    def test_peep_stdout_preserved(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import run_shell, set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        import wrapper.tools as tools_mod
        from wrapper.peep_shell import PeepShellExecutor
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("Write-Output 'test-output-line'", timeout=30)
        finally:
            tools_mod._shell_executor = original

        assert "test-output-line" in result

    def test_peep_stderr_preserved(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import run_shell, set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        import wrapper.tools as tools_mod
        from wrapper.peep_shell import PeepShellExecutor
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("Write-Error 'test-error-message'", timeout=30)
        finally:
            tools_mod._shell_executor = original

        assert "STDERR:" in result
        assert "test-error-message" in result

    def test_peep_exit_code_preserved(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import run_shell, set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        import wrapper.tools as tools_mod
        from wrapper.peep_shell import PeepShellExecutor
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("exit 7", timeout=30)
        finally:
            tools_mod._shell_executor = original

        assert "EXIT_CODE: 7" in result


class TestWorkspaceCwd:
    """Verify workspace cwd is respected through PEEP."""

    def test_peep_cwd_matches_workspace(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import run_shell, set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        import wrapper.tools as tools_mod
        from wrapper.peep_shell import PeepShellExecutor
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("Get-Location", timeout=30)
        finally:
            tools_mod._shell_executor = original

        # The workspace path should appear in the output
        assert str(tmp_path) in result or tmp_path.name in result


class TestDefaultExecutorUnaffected:
    """Verify the default executor works without PEEP configuration."""

    def test_default_executor_still_works(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import (
            run_shell,
            set_policy,
            set_shell_executor,
            set_workspace_root,
        )

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))
        set_shell_executor(None)

        result = run_shell("echo default-still-works", timeout=10)
        assert "default-still-works" in result
        assert "EXIT_CODE: 0" in result

    def test_hackass_bridge_no_peep_dependency(self):
        """Verify the hackass bridge doesn't import PEEP."""
        import inspect

        from hackass.bridge import inspect_file, run_shell, write_file

        for func in [inspect_file, write_file, run_shell]:
            source = inspect.getsource(func)
            assert "peep" not in source.lower()
            assert "PeepShell" not in source


class TestPeeperCwdSupport:
    """Verify PEEP's PowerShellAdapter cwd support."""

    def test_powershell_adapter_accepts_cwd(self):
        """PowerShellAdapter should accept an optional cwd parameter."""
        import inspect

        from peep.powershell import PowerShellAdapter
        sig = inspect.signature(PowerShellAdapter.__init__)
        params = list(sig.parameters.keys())
        assert "cwd" in params, "PowerShellAdapter.__init__ must accept cwd"

    def test_powershell_adapter_cwd_default_none(self):
        """When cwd is not provided, it defaults to None (backward compatible)."""
        import inspect

        from peep.powershell import PowerShellAdapter
        sig = inspect.signature(PowerShellAdapter.__init__)
        cwd_param = sig.parameters["cwd"]
        assert cwd_param.default is None

    def test_powershell_adapter_no_cwd_still_works(self, tmp_path):
        """Existing constructor behavior (no cwd) remains valid."""
        import shutil
        from datetime import UTC, datetime

        from peep.factory import EventFactory
        from peep.powershell import PowerShellAdapter
        from peep.session import SESSION_STATE_ACTIVE, PeepSession

        if shutil.which("powershell.exe") is None and shutil.which("pwsh.exe") is None:
            pytest.skip("PowerShell not available")

        session = PeepSession(
            session_id="test-no-cwd",
            created_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
            state=SESSION_STATE_ACTIVE,
        )
        factory = EventFactory(
            session_id="test-no-cwd",
            source_type="test",
            source_id="test",
        )
        adapter = PowerShellAdapter(
            session=session,
            event_factory=factory,
        )
        assert adapter._cwd is None


class TestPeepHarnessEchoSuppressed:
    """PowerShell echoes the submitted PEEP wrapper line on stdout (prompt
    prefixed, so the boundary decoder never consumes it).  The echoed
    harness scaffolding must never surface in the ROSIE shell result."""

    def test_result_contains_no_peep_harness_scaffolding(self, tmp_path):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import run_shell, set_policy, set_workspace_root

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        import wrapper.tools as tools_mod
        from wrapper.peep_shell import PeepShellExecutor
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("Write-Output 'clean-marker'", timeout=30)
        finally:
            tools_mod._shell_executor = original

        assert "clean-marker" in result
        assert "__PEEP_COMMAND_START__" not in result
        assert "__PEEP_COMMAND_END__" not in result
        assert "FromBase64String" not in result


class TestPeepCommandCorrelation:
    """Every PEEP event for an execution must carry the command ID when
    forwarded to RATTER, not just events after COMMAND_OBSERVED."""

    def test_all_peep_events_carry_same_command_id(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from wrapper.peep_shell import PeepShellExecutor

        sink_calls = []

        class _Sink:
            def send_peep_events(self, events, command_id=None, task_id=None):
                sink_calls.append({"events": list(events), "command_id": command_id, "task_id": task_id})
                return True

        def _ev(event_type, payload):
            return SimpleNamespace(event_type=event_type, payload=payload)

        class FakeAdapter:
            def __init__(self):
                self._polls = [
                    [_ev("session.started", {"session_id": "s1"}), _ev("process.started", {"process_id": 1234})],
                    [_ev("command.observed", {"command_id": "c1"})],
                    [_ev("command.completed", {"command_id": "c1", "exit_code": 0})],
                ]
                self._poll_idx = 0
            def start(self): pass
            def submit(self, cmd): pass
            def poll(self):
                if self._poll_idx < len(self._polls):
                    batch = self._polls[self._poll_idx]
                    self._poll_idx += 1
                    return list(batch)
                return []
            def stop(self): pass

        executor = PeepShellExecutor(cwd=".")
        executor._ratter_sink = _Sink()
        with patch("wrapper.peep_shell.PowerShellAdapter", return_value=FakeAdapter()):
            result = executor.execute("echo hi", timeout=30)

        assert result, "executor returned empty result"
        assert sink_calls, "no events forwarded to RATTER"
        ids = {c["command_id"] for c in sink_calls}
        assert ids == {sink_calls[0]["command_id"]}, f"mixed command_ids: {ids}"
        assert ids != {None}, "command_id None on some forwarded events"
        assert "" not in ids, "command_id empty"



