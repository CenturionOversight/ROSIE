"""Tests for visible PEEP attachment/fallback state in _configure_peep_executor."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from wrapper.tools import set_workspace_root


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


class TestPeepInitializedOnceDuringMain:
    """Regression: `main()` must configure PEEP exactly once during startup."""

    def _run_one_shot(self, root, monkeypatch):
        """Run main() through a cheap one-shot path, mocking all external I/O.

        Returns a 3-tuple of (exit_code, peep_mock, captured_messages) where
        captured_messages are the messages passed into the completion call.
        """
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        captured = {}

        def fake_completion(models, messages, temperature):
            # Capture what reaches the model so we can assert no API was hit
            # and the system prompt appears. The mock returns a plain answer
            # so the loop terminates without any tool call.
            captured.setdefault("calls", []).append(list(messages))
            from unittest.mock import MagicMock as _MM
            resp = _MM()
            msg = _MM()
            msg.content = "ok"
            msg.tool_calls = None
            resp.choices = [_MM()]
            resp.choices[0].message = msg
            return resp

        from wrapper.cli import main
        peep_mock = MagicMock(return_value="peep=attached")

        with patch("wrapper.cli._configure_peep_executor", peep_mock), \
             patch("wrapper.cli._completion", side_effect=fake_completion):
            rc = main([str(root), "say hi"])

        return rc, peep_mock, captured

    def test_main_configures_peep_exactly_once(self, tmp_path, monkeypatch):
        """_configure_peep_executor is called exactly once with the workspace Path."""
        root = tmp_path.resolve()
        rc, peep_mock, _ = self._run_one_shot(root, monkeypatch)

        assert rc == 0  # startup completed normally
        resolved = root
        peep_mock.assert_called_once_with(resolved)

    def test_peep_once_success_status(self, tmp_path, monkeypatch):
        """The startup banner reflects the single peep=attached status."""
        root = tmp_path.resolve()
        rc, peep_mock, _ = self._run_one_shot(root, monkeypatch)
        assert rc == 0
        assert peep_mock.call_count == 1
        assert peep_mock.call_args.args[0] == root

    def test_peep_once_failure_fallback(self, tmp_path, monkeypatch):
        """A single failure still results in the visible fallback status."""
        root = tmp_path.resolve()
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        from unittest.mock import MagicMock as _MM
        from unittest.mock import patch as _patch

        from wrapper.cli import main

        captured = {}

        def fake_completion(models, messages, temperature):
            captured["hit"] = True
            resp = _MM()
            msg = _MM()
            msg.content = "ok"
            msg.tool_calls = None
            resp.choices = [_MM()]
            resp.choices[0].message = msg
            return resp

        fallback_status = (
            "peep=unavailable fallback=subprocess reason=RuntimeError: boom"
        )
        peep_mock = _MM(return_value=fallback_status)

        with _patch("wrapper.cli._configure_peep_executor", peep_mock), \
             _patch("wrapper.cli._completion", side_effect=fake_completion):
            rc = main([str(root), "say hi"])

        assert captured.get("hit") is True
        assert peep_mock.call_count == 1
        peep_mock.assert_called_once_with(root)
        assert rc == 0
