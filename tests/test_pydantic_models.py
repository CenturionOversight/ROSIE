"""Tests for pydantic argument validation models."""
import pytest
from pydantic import ValidationError

from wrapper.tools import (
    ApplyPatchArgs,
    InspectFileArgs,
    InspectGitDiffArgs,
    InspectGitLogArgs,
    ListDirectoryArgs,
    PreviewWriteFileArgs,
    RunShellArgs,
    SearchWorkspaceArgs,
    WriteFileArgs,
)


class TestInspectFileArgs:
    def test_valid_defaults(self):
        args = InspectFileArgs(relative_path="README.md")
        assert args.relative_path == "README.md"
        assert args.start_line == 1
        assert args.line_count == 100

    def test_valid_explicit(self):
        args = InspectFileArgs(relative_path="src/main.py", start_line=10, line_count=50)
        assert args.start_line == 10
        assert args.line_count == 50

    def test_missing_path(self):
        with pytest.raises(ValidationError):
            InspectFileArgs(start_line=1, line_count=100)

    def test_start_line_too_low(self):
        with pytest.raises(ValidationError):
            InspectFileArgs(relative_path="f.txt", start_line=0)

    def test_line_count_too_low(self):
        with pytest.raises(ValidationError):
            InspectFileArgs(relative_path="f.txt", line_count=0)

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            InspectFileArgs(relative_path="f.txt", unexpected="value")


class TestPreviewWriteFileArgs:
    def test_valid(self):
        args = PreviewWriteFileArgs(relative_path="f.txt", content="hello")
        assert args.content == "hello"

    def test_missing_content(self):
        with pytest.raises(ValidationError):
            PreviewWriteFileArgs(relative_path="f.txt")

    def test_missing_path(self):
        with pytest.raises(ValidationError):
            PreviewWriteFileArgs(content="hello")


class TestWriteFileArgs:
    def test_valid(self):
        args = WriteFileArgs(relative_path="f.txt", content="hello\nworld")
        assert args.relative_path == "f.txt"

    def test_missing_path(self):
        with pytest.raises(ValidationError):
            WriteFileArgs(content="hello")

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            WriteFileArgs(relative_path="f.txt", content="x", extra="y")


class TestRunShellArgs:
    def test_valid_required_only(self):
        args = RunShellArgs(command="ls -la")
        assert args.command == "ls -la"
        assert args.timeout is None

    def test_valid_with_timeout(self):
        args = RunShellArgs(command="git status", timeout=60)
        assert args.timeout == 60

    def test_timeout_too_low(self):
        with pytest.raises(ValidationError):
            RunShellArgs(command="ls", timeout=0)

    def test_missing_command(self):
        with pytest.raises(ValidationError):
            RunShellArgs()

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            RunShellArgs(command="ls", unknown="x")


class TestListDirectoryArgs:
    def test_valid_defaults(self):
        args = ListDirectoryArgs()
        assert args.relative_path == "."
        assert args.recursive is False
        assert args.max_entries == 200

    def test_valid_explicit(self):
        args = ListDirectoryArgs(relative_path="src", recursive=True, max_entries=50)
        assert args.relative_path == "src"
        assert args.recursive is True
        assert args.max_entries == 50

    def test_max_entries_zero_rejected(self):
        with pytest.raises(ValidationError):
            ListDirectoryArgs(max_entries=0)

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            ListDirectoryArgs(relative_path=".", unknown="x")


class TestSearchWorkspaceArgs:
    def test_valid_defaults(self):
        args = SearchWorkspaceArgs(query="hello")
        assert args.query == "hello"
        assert args.relative_path == "."
        assert args.max_results == 50
        assert args.max_files == 5000

    def test_valid_explicit(self):
        args = SearchWorkspaceArgs(query="import", relative_path="src", max_results=10, max_files=100)
        assert args.query == "import"
        assert args.relative_path == "src"
        assert args.max_results == 10
        assert args.max_files == 100

    def test_missing_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchWorkspaceArgs()

    def test_max_results_zero_rejected(self):
        with pytest.raises(ValidationError):
            SearchWorkspaceArgs(query="x", max_results=0)

    def test_max_files_zero_rejected(self):
        with pytest.raises(ValidationError):
            SearchWorkspaceArgs(query="x", max_files=0)

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            SearchWorkspaceArgs(query="x", unknown="y")


class TestApplyPatchArgs:
    def test_valid(self):
        args = ApplyPatchArgs(relative_path="f.txt", old_text="a", new_text="b")
        assert args.relative_path == "f.txt"
        assert args.old_text == "a"
        assert args.new_text == "b"

    def test_missing_path(self):
        with pytest.raises(ValidationError):
            ApplyPatchArgs(old_text="a", new_text="b")

    def test_missing_old_text(self):
        with pytest.raises(ValidationError):
            ApplyPatchArgs(relative_path="f.txt", new_text="b")

    def test_missing_new_text(self):
        with pytest.raises(ValidationError):
            ApplyPatchArgs(relative_path="f.txt", old_text="a")

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            ApplyPatchArgs(relative_path="f.txt", old_text="a", new_text="b", extra="x")


class TestInspectGitDiffArgs:
    def test_valid_defaults(self):
        args = InspectGitDiffArgs()
        assert args.relative_path is None
        assert args.staged is False
        assert args.max_chars == 20000

    def test_valid_explicit(self):
        args = InspectGitDiffArgs(relative_path="src/main.py", staged=True, max_chars=5000)
        assert args.relative_path == "src/main.py"
        assert args.staged is True
        assert args.max_chars == 5000

    def test_max_chars_zero_rejected(self):
        with pytest.raises(ValidationError):
            InspectGitDiffArgs(max_chars=0)

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            InspectGitDiffArgs(staged=True, unknown="x")


class TestInspectGitLogArgs:
    def test_valid_defaults(self):
        args = InspectGitLogArgs()
        assert args.max_entries == 10
        assert args.relative_path is None

    def test_valid_explicit(self):
        args = InspectGitLogArgs(max_entries=5, relative_path="README.md")
        assert args.max_entries == 5
        assert args.relative_path == "README.md"

    def test_max_entries_zero_rejected(self):
        with pytest.raises(ValidationError):
            InspectGitLogArgs(max_entries=0)

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            InspectGitLogArgs(max_entries=5, unknown="x")
