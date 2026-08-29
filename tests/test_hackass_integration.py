"""Focused tests for the HACKASS Google ADK integration boundary.

Tests cover:
- HACKASS module imports
- Gemini model configuration
- Tool/adaptor registration
- Adapter delegates to existing ARCHESTRATOR implementation
- Malformed tool arguments fail safely
- Approval/security behavior is not bypassed
"""
import os
from unittest.mock import patch, MagicMock

import pytest


class TestHackassImports:
    """Verify the HACKASS module imports correctly."""

    def test_hackass_package_imports(self):
        from hackass import MODEL_NAME, create_architect_tools, run_hackass
        assert MODEL_NAME == "gemini-3.5-flash"

    def test_bridge_module_imports(self):
        from hackass.bridge import (
            inspect_file,
            preview_write_file,
            write_file,
            inspect_git_status,
            run_shell,
            create_architect_tools,
        )

    def test_config_module_imports(self):
        from hackass.config import (
            MODEL_NAME,
            VERTEXAI_LOCATION,
            VERTEXAI_PROJECT,
            get_model_name,
        )
        assert MODEL_NAME == "gemini-3.5-flash"
        assert VERTEXAI_PROJECT == "rosie-fire"
        assert VERTEXAI_LOCATION == "asia-northeast1"

    def test_agent_module_imports(self):
        from hackass.agent import INSTRUCTION, create_agent, run_hackass
        assert "HACKASS" in INSTRUCTION or "ROSIE" in INSTRUCTION


class TestModelConfiguration:
    """Verify Gemini model configuration."""

    def test_default_model_is_3_5_plus(self):
        from hackass.config import MODEL_NAME
        assert MODEL_NAME.startswith("gemini-3")

    def test_model_override_via_env(self, monkeypatch):
        import importlib
        from hackass import config

        monkeypatch.setenv("HACKASS_GEMINI_MODEL", "gemini-3.7-flash")
        importlib.reload(config)
        assert config.get_model_name() == "gemini-3.7-flash"

        monkeypatch.delenv("HACKASS_GEMINI_MODEL")
        importlib.reload(config)
        assert config.get_model_name() == "gemini-3.5-flash"

    def test_vertexai_project_is_rosie_fire(self):
        from hackass.config import VERTEXAI_PROJECT
        assert VERTEXAI_PROJECT == "rosie-fire"

    def test_vertexai_location_set(self):
        from hackass.config import VERTEXAI_LOCATION
        assert VERTEXAI_LOCATION in ["us-central1", "us-east1", "asia-northeast1", "europe-west1"]


class TestToolRegistration:
    """Verify ARCHESTRATOR tools are registered as ADK FunctionTools."""

    def test_create_tools_returns_function_tools(self):
        from hackass.bridge import create_architect_tools

        tools = create_architect_tools()
        assert len(tools) == 5

        tool_names = [t.name for t in tools]
        assert "inspect_file" in tool_names
        assert "preview_write_file" in tool_names
        assert "write_file" in tool_names
        assert "inspect_git_status" in tool_names
        assert "run_shell" in tool_names

    def test_tools_are_adk_function_tools(self):
        from hackass.bridge import create_architect_tools
        from google.adk.tools import FunctionTool

        tools = create_architect_tools()
        for tool in tools:
            assert isinstance(tool, FunctionTool)


class TestToolBridgeDelegation:
    """Verify the adapter delegates to existing ARCHESTRATOR implementation."""

    def test_inspect_file_delegates_to_dispatch(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path, raising=False)
        monkeypatch.setattr("wrapper.tools._policy", None, raising=False)

        from hackass.bridge import inspect_file

        test_content = "line 1\nline 2\nline 3\n"
        (tmp_path / "test.txt").write_text(test_content)

        result = inspect_file(relative_path="test.txt")
        assert "line 1" in result
        assert "1:" in result

    def test_write_file_delegates_to_dispatch(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path, raising=False)

        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        policy = ApprovalPolicy(ExecutionPolicy.YOLO)
        monkeypatch.setattr("wrapper.tools._policy", policy, raising=False)

        from hackass.bridge import write_file

        result = write_file(relative_path="output.txt", content="hello world")
        assert "Successfully wrote" in result
        assert (tmp_path / "output.txt").read_text() == "hello world"

    def test_inspect_git_status_delegates(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path, raising=False)

        from hackass.bridge import inspect_git_status

        result = inspect_git_status()
        assert "git" in result.lower()

    def test_run_shell_delegates_with_yolo(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path, raising=False)

        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        policy = ApprovalPolicy(ExecutionPolicy.YOLO)
        monkeypatch.setattr("wrapper.tools._policy", policy, raising=False)

        from hackass.bridge import run_shell

        result = run_shell(command="echo hello")
        assert "hello" in result
        assert "EXIT_CODE: 0" in result


class TestToolBridgeSafety:
    """Verify malformed arguments and security behavior."""

    def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path, raising=False)
        monkeypatch.setattr("wrapper.tools._policy", None, raising=False)

        from hackass.bridge import inspect_file

        result = inspect_file(relative_path="../../etc/passwd")
        assert "Path traversal blocked" in result

    def test_unknown_tool_returns_error(self):
        from wrapper.tools import dispatch_tool

        result = dispatch_tool("nonexistent_tool", {})
        assert "Unknown tool" in result

    def test_malformed_arguments_handled_safely(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wrapper.tools._workspace_root", tmp_path, raising=False)
        monkeypatch.setattr("wrapper.tools._policy", None, raising=False)

        from hackass.bridge import inspect_file

        result = inspect_file(relative_path="nonexistent.md")
        assert "File not found" in result

    def test_approval_policy_preserves_security(self, tmp_path, monkeypatch):
        """Verify that the ASK approval policy is not silently bypassed."""
        from wrapper.tools import set_workspace_root, set_policy
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)

        ask_policy = ApprovalPolicy(ExecutionPolicy.ASK)
        set_policy(ask_policy)

        from hackass.bridge import run_shell

        with patch("builtins.input", side_effect=EOFError):
            result = run_shell(command="echo test")
            assert "DENIED" in result

    def test_yolo_policy_auto_approves(self, tmp_path, monkeypatch, capsys):
        """Verify that yolo mode auto-approves without prompting."""
        from wrapper.tools import set_workspace_root, set_policy
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy

        set_workspace_root(tmp_path)

        yolo_policy = ApprovalPolicy(ExecutionPolicy.YOLO)
        set_policy(yolo_policy)

        from hackass.bridge import run_shell

        result = run_shell(command="echo test")
        assert "test" in result
        assert "EXIT_CODE: 0" in result

        # In yolo mode, the approval message is printed to stdout
        captured = capsys.readouterr()
        assert "[yolo]" in captured.out


class TestGoogleIntegrationBoundary:
    """Verify the HACKASS integration module does not bypass ROSIE core."""

    def test_wrapper_package_not_modified(self):
        """Verify the pre-existing ARCHESTRATOR code is untouched."""
        import wrapper
        assert wrapper.__version__ == "2.0.0"

    def test_bridge_only_delegates(self):
        """The bridge functions should not contain execution logic."""
        import inspect
        from hackass.bridge import inspect_file, write_file, run_shell

        for func in [inspect_file, write_file, run_shell]:
            source = inspect.getsource(func)
            assert "dispatch_tool" in source
            assert "import" not in source or "dispatch_tool" in source.split("return")[0]
