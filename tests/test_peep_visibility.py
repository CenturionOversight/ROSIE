"""Tests for visible PEEP attachment/fallback state in _configure_peep_executor."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from wrapper.tools import get_workspace_root, set_workspace_root


class TestConfigurePeepExecutor:
    def test_peep_attached_success(self, tmp_path, monkeypatch, capsys):
        """When PEEP imports and initializes, the status string says attached."""
        root = tmp_path.resolve()
        set_workspace_root(root)
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        from wrapper.cli import _configure_peep_executor
        result = _configure_peep_executor(Path(root))
        assert result == "peep=attached"

    def test_peep_import_failure(self, tmp_path, monkeypatch, capsys):
        """When PEEP can't import, subprocess fallback is reported."""
        root = tmp_path.resolve()
        set_workspace_root(root)
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        # Setting sys.modules entry to None makes __import__ raise ImportError.
        monkeypatch.setitem(sys.modules, "wrapper.peep_shell", None)

        from wrapper.cli import _configure_peep_executor
        result = _configure_peep_executor(Path(root))

        stderr = capsys.readouterr().err
        assert result.startswith("peep=unavailable fallback=subprocess")
        assert "reason=" in result
        assert "reason=" in stderr

    def test_peep_init_failure(self, tmp_path, monkeypatch, capsys):
        """When PEEP executor init raises, subprocess fallback is reported."""
        root = tmp_path.resolve()
        set_workspace_root(root)
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        # Create a fake peep_shell module where PeepShellExecutor raises on construction.
        fake_module = MagicMock()
        fake_module.PeepShellExecutor = MagicMock(
            side_effect=RuntimeError("PEEP adapter failed")
        )

        with patch.dict("sys.modules", {"wrapper.peep_shell": fake_module}):
            from wrapper.cli import _configure_peep_executor
            result = _configure_peep_executor(Path(root))

        stderr = capsys.readouterr().err
        assert result.startswith("peep=unavailable fallback=subprocess")
        assert "reason=" in result
        assert "RuntimeError" in result
        assert "PEEP adapter failed" in result or "PEEP adapter failed" in stderr

    def test_peep_fallback_does_not_crash(self, tmp_path, monkeypatch, capsys):
        """When PEEP is unavailable, ROSIE should still be usable via subprocess."""
        root = tmp_path.resolve()
        set_workspace_root(root)
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        # Simulate PEEP not being installed — must clear sys.modules cache
        # because earlier tests may have imported wrapper.peep_shell.
        monkeypatch.setitem(sys.modules, "wrapper.peep_shell", None)

        from wrapper.cli import _configure_peep_executor
        result = _configure_peep_executor(Path(root))

        assert result != "peep=attached"
        # The default subprocess executor should still be functional.
        from wrapper.tools import _shell_executor
        assert _shell_executor is None  # Falls back to default subprocess.
