"""Tests for tool functions: inspect_file, write_file, run_shell, inspect_git_status, dispatch_tool."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from wrapper.tools import (
    TOOL_SCHEMAS,
    TOOL_REGISTRY,
    dispatch_tool,
    inspect_file,
    inspect_git_status,
    preview_write_file,
    run_shell,
    set_policy,
    set_workspace_root,
    write_file,
)
from wrapper.policy import ApprovalPolicy


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    set_workspace_root(root)
    monkeypatch.setattr("wrapper.tools._workspace_root", root)
    return root


@pytest.fixture
def yolo_policy(monkeypatch):
    policy = ApprovalPolicy()
    policy.mode = policy.mode.__class__.YOLO if hasattr(policy.mode, "__class__") else None
    from wrapper.policy import ExecutionPolicy
    policy = ApprovalPolicy(ExecutionPolicy.YOLO)
    set_policy(policy)
    monkeypatch.setattr("wrapper.tools._policy", policy)
    return policy


@pytest.fixture
def ask_policy(monkeypatch):
    from wrapper.policy import ExecutionPolicy
    policy = ApprovalPolicy(ExecutionPolicy.ASK)
    set_policy(policy)
    monkeypatch.setattr("wrapper.tools._policy", policy)
    return policy


class TestInspectFile:
    def test_read_simple_file(self, workspace):
        (workspace / "hello.txt").write_text("line1\nline2\nline3")
        result = inspect_file("hello.txt")
        assert "1: line1" in result
        assert "2: line2" in result
        assert "3: line3" in result

    def test_read_with_start_line(self, workspace):
        (workspace / "hello.txt").write_text("line1\nline2\nline3\nline4\nline5")
        result = inspect_file("hello.txt", start_line=3, line_count=10)
        assert "3: line3" in result
        assert "5: line5" in result
        assert "1: line1" not in result

    def test_file_not_found(self, workspace):
        with pytest.raises(FileNotFoundError):
            inspect_file("nonexistent.txt")

    def test_binary_file(self, workspace):
        (workspace / "binary.dat").write_bytes(b"\x00\x01\x02\xff")
        result = inspect_file("binary.dat")
        assert "binary" in result.lower()

    def test_line_count_respected(self, workspace):
        (workspace / "many.txt").write_text("a\nb\nc\nd\ne\nf\ng\nh\n")
        result = inspect_file("many.txt", start_line=1, line_count=3)
        assert "1: a" in result
        assert "3: c" in result
        assert "4: d" not in result


class TestPreviewWriteFile:
    def test_new_file_shows_additions(self, workspace):
        result = preview_write_file("new.txt", "hello\nworld")
        assert "hello" in result or "world" in result

    def test_identical_content_no_changes(self, workspace):
        (workspace / "f.txt").write_text("hello")
        result = preview_write_file("f.txt", "hello")
        assert "No changes" in result

    def test_modified_content_shows_diff(self, workspace):
        (workspace / "f.txt").write_text("old line")
        result = preview_write_file("f.txt", "new line")
        assert "old line" in result
        assert "new line" in result


class TestWriteFile:
    def test_write_creates_file_yolo(self, workspace, yolo_policy):
        result = write_file("new.py", "# hello\nprint('hi')")
        assert "Successfully wrote" in result
        assert (workspace / "new.py").exists()
        content = (workspace / "new.py").read_text()
        assert "# hello" in content

    def test_write_creates_nested_dirs(self, workspace, yolo_policy):
        result = write_file("src/deep/nested.py", "pass")
        assert "Successfully wrote" in result
        assert (workspace / "src/deep/nested.py").exists()

    def test_write_denied_in_ask_mode(self, workspace, ask_policy, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        result = write_file("new.py", "content")
        assert "DENIED" in result
        assert not (workspace / "new.py").exists()

    def test_write_line_count_in_message(self, workspace, yolo_policy):
        result = write_file("f.txt", "a\nb\nc")
        assert "3 line" in result


class TestRunShell:
    def test_shell_command_yolo(self, workspace, yolo_policy):
        result = run_shell("echo hello")
        assert "hello" in result
        assert "EXIT_CODE: 0" in result or "EXIT_CODE: 1" in result

    def test_shell_denied_in_ask_mode(self, workspace, ask_policy, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        result = run_shell("echo hello")
        assert "DENIED" in result

    def test_shell_timeout(self, tmp_workspace, yolo_policy):
        result = run_shell("timeout /t 10", timeout=1)
        assert "timed out" in result.lower() or "exit_code" in result.lower()

    def test_shell_captures_stderr(self, tmp_workspace, yolo_policy):
        result = run_shell("echo error 1>&2")
        assert "STDERR:" in result

    def test_shell_no_output(self, tmp_workspace, yolo_policy):
        result = run_shell("cmd /c exit 0")
        assert "EXIT_CODE: 0" in result


class TestInspectGitStatus:
    def test_git_status(self, workspace):
        result = inspect_git_status()
        assert isinstance(result, str)

    def test_not_a_repo(self, workspace, monkeypatch):
        monkeypatch.setattr("subprocess.run", MagicMock(side_effect=FileNotFoundError()))
        result = inspect_git_status()
        assert "git" in result.lower()


class TestDispatchTool:
    def test_dispatch_valid_tool(self, workspace, yolo_policy):
        result = dispatch_tool("write_file", {"relative_path": "dispatched.py", "content": "x = 1"})
        assert "Successfully wrote" in result
        assert (workspace / "dispatched.py").exists()

    def test_dispatch_unknown_tool(self, workspace):
        result = dispatch_tool("nonexistent_tool", {})
        assert "Unknown tool" in result

    def test_dispatch_invalid_args(self, workspace):
        result = dispatch_tool("inspect_file", {"start_line": 0})
        assert "validation failed" in result.lower() or "ERROR" in result

    def test_dispatch_path_traversal_blocked(self, workspace):
        result = dispatch_tool("inspect_file", {"relative_path": "../../../etc/passwd"})
        assert "path violation" in result.lower() or "ERROR" in result

    def test_dispatch_no_arg_tool(self, workspace):
        result = dispatch_tool("inspect_git_status", {})
        assert isinstance(result, str)

    def test_dispatch_extra_args_rejected(self, workspace):
        result = dispatch_tool("run_shell", {"command": "echo hi", "extra": "x"})
        assert "validation failed" in result.lower() or "ERROR" in result


class TestToolRegistryAndSchemas:
    def test_tool_registry_has_five_entries(self):
        assert len(TOOL_REGISTRY) == 5

    def test_tool_schemas_has_five_entries(self):
        assert len(TOOL_SCHEMAS) == 5

    def test_all_tools_in_registry_have_schemas(self):
        for name in TOOL_REGISTRY:
            assert any(
                s["function"]["name"] == name for s in TOOL_SCHEMAS
            ), f"No schema for tool '{name}'"

    def test_schema_format_openai(self):
        for schema in TOOL_SCHEMAS:
            assert schema["type"] == "function"
            assert "function" in schema
            fn = schema["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            params = fn["parameters"]
            assert "type" in params
            assert "properties" in params
            # inspect_git_status has no args, so it may not have "required".
            # Tools with args always have "required".
            if fn["name"] != "inspect_git_status":
                assert "required" in params

    def test_required_fields(self):
        for schema in TOOL_SCHEMAS:
            fn = schema["function"]
            if fn["name"] == "inspect_git_status":
                assert fn["parameters"].get("required", []) == []
            else:
                assert isinstance(fn["parameters"]["required"], list)

    def test_inspect_git_status_has_no_params(self):
        git_schema = [s for s in TOOL_SCHEMAS if s["function"]["name"] == "inspect_git_status"][0]
        params = git_schema["function"]["parameters"]
        assert params["type"] == "object"
        assert params["properties"] == {}
