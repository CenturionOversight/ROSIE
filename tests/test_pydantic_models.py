"""Tests for pydantic argument validation models."""
import pytest
from pydantic import ValidationError

from wrapper.tools import (
    InspectFileArgs,
    PreviewWriteFileArgs,
    RunShellArgs,
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
