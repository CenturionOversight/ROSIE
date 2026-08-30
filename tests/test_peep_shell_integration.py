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

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from wrapper.peep_shell import PeepShellExecutor


class TestApprovalGate:
    """Verify approval policy still gates shell execution with PEEP."""

    def test_peep_executor_approval_denied(self, tmp_path, monkeypatch):
        """Denial in ask mode should prevent execution entirely."""
        from wrapper.tools import set_workspace_root, set_policy
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

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
        from wrapper.tools import set_workspace_root, set_policy
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

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
        from wrapper import cli
        from wrapper.tools import _shell_executor
        import wrapper.tools as tools_mod

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
        from wrapper import cli
        import wrapper.tools as tools_mod
        import builtins

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
        from wrapper.tools import set_workspace_root, set_policy, run_shell
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        from wrapper.peep_shell import PeepShellExecutor
        import wrapper.tools as tools_mod
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
        from wrapper.tools import set_workspace_root, set_policy, run_shell
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        from wrapper.peep_shell import PeepShellExecutor
        import wrapper.tools as tools_mod
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("Write-Output 'test-output-line'", timeout=30)
        finally:
            tools_mod._shell_executor = original

        assert "test-output-line" in result

    def test_peep_stderr_preserved(self, tmp_path):
        from wrapper.tools import set_workspace_root, set_policy, run_shell
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        from wrapper.peep_shell import PeepShellExecutor
        import wrapper.tools as tools_mod
        original = tools_mod._shell_executor
        tools_mod._shell_executor = PeepShellExecutor(cwd=str(tmp_path))
        try:
            result = run_shell("Write-Error 'test-error-message'", timeout=30)
        finally:
            tools_mod._shell_executor = original

        assert "STDERR:" in result
        assert "test-error-message" in result

    def test_peep_exit_code_preserved(self, tmp_path):
        from wrapper.tools import set_workspace_root, set_policy, run_shell
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        from wrapper.peep_shell import PeepShellExecutor
        import wrapper.tools as tools_mod
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
        from wrapper.tools import set_workspace_root, set_policy, run_shell
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

        from wrapper.peep_shell import PeepShellExecutor
        import wrapper.tools as tools_mod
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
        from wrapper.tools import set_workspace_root, set_policy, run_shell, set_shell_executor
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))
        set_shell_executor(None)

        result = run_shell("echo default-still-works", timeout=10)
        assert "default-still-works" in result
        assert "EXIT_CODE: 0" in result

    def test_hackass_bridge_no_peep_dependency(self):
        """Verify the hackass bridge doesn't import PEEP."""
        import inspect
        from hackass.bridge import inspect_file, write_file, run_shell

        for func in [inspect_file, write_file, run_shell]:
            source = inspect.getsource(func)
            assert "peep" not in source.lower()
            assert "PeepShell" not in source


class TestPeeperCwdSupport:
    """Verify PEEP's PowerShellAdapter cwd support."""

    def test_powershell_adapter_accepts_cwd(self):
        """PowerShellAdapter should accept an optional cwd parameter."""
        from peep.powershell import PowerShellAdapter

        import inspect
        sig = inspect.signature(PowerShellAdapter.__init__)
        params = list(sig.parameters.keys())
        assert "cwd" in params, "PowerShellAdapter.__init__ must accept cwd"

    def test_powershell_adapter_cwd_default_none(self):
        """When cwd is not provided, it defaults to None (backward compatible)."""
        from peep.powershell import PowerShellAdapter

        import inspect
        sig = inspect.signature(PowerShellAdapter.__init__)
        cwd_param = sig.parameters["cwd"]
        assert cwd_param.default is None

    def test_powershell_adapter_no_cwd_still_works(self, tmp_path):
        """Existing constructor behavior (no cwd) remains valid."""
        from datetime import UTC, datetime
        from peep.session import SESSION_STATE_ACTIVE, PeepSession
        from peep.factory import EventFactory
        from peep.powershell import PowerShellAdapter
        import shutil

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
