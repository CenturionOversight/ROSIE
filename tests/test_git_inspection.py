"""Tests for the native read-only Git inspection tools."""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from wrapper.tools import (
    PathTraversalError,
    inspect_git_diff,
    inspect_git_log,
    inspect_git_status,
    set_workspace_root,
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    set_workspace_root(root)
    monkeypatch.setattr("wrapper.tools._workspace_root", root)
    return root


class _Proc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestInspectGitDiff:
    def test_unstaged_diff(self, workspace):
        (workspace / "f.txt").write_text("changed line\n")
        proc = _Proc(0, stdout="diff --git a/f.txt b/f.txt\n@@ -1 +1 @@\n-old\n+new\n")
        with patch("wrapper.tools.subprocess.run", return_value=proc) as m:
            result = inspect_git_diff()
        assert "diff --git" in result
        argv = m.call_args.args[0]
        assert argv[0] == "git"
        assert argv[1] == "diff"
        assert "--cached" not in argv

    def test_staged_diff(self, workspace):
        proc = _Proc(0, stdout="diff --git a/f.txt b/f.txt\n@@ -1 +1 @@\n-old\n+new\n")
        with patch("wrapper.tools.subprocess.run", return_value=proc) as m:
            result = inspect_git_diff(staged=True)
        assert "diff --git" in result
        argv = m.call_args.args[0]
        assert "--cached" in argv

    def test_path_filtered_diff(self, workspace):
        proc = _Proc(0, stdout="diff --git a/src f src\n")
        with patch("wrapper.tools.subprocess.run", return_value=proc) as m:
            result = inspect_git_diff(relative_path="src/main.py")
        assert "diff --git" in result
        argv = m.call_args.args[0]
        assert "--" in argv
        assert "src/main.py" in argv

    def test_path_traversal_rejected(self, workspace):
        with pytest.raises(PathTraversalError):
            inspect_git_diff(relative_path="../../etc/passwd")

    def test_empty_diff_clean_message(self, workspace):
        proc = _Proc(0, stdout="")
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff()
        assert "No changes" in result

    def test_truncation_marked(self, workspace):
        proc = _Proc(0, stdout="x" * 100)
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff(max_chars=50)
        assert len(result) <= 50
        assert "truncated" in result.lower()

    def test_git_error_surfaced(self, workspace):
        proc = _Proc(1, stderr="fatal: not a git repository")
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff()
        assert "Error" in result or "failed" in result

    def test_not_repo_failure(self, workspace):
        with patch("wrapper.tools.subprocess.run", side_effect=FileNotFoundError()):
            result = inspect_git_diff()
        assert "git" in result.lower()


class TestInspectGitLog:
    def test_recent_log(self, workspace):
        proc = _Proc(0, stdout="abc1234 message one\nffff22 message two\n")
        with patch("wrapper.tools.subprocess.run", return_value=proc) as m:
            result = inspect_git_log(max_entries=2)
        assert "message one" in result
        argv = m.call_args.args[0]
        assert argv[0] == "git"
        assert argv[1] == "log"
        assert "--oneline" in argv
        assert argv[argv.index("-n") + 1] == "2"

    def test_path_filtered_log(self, workspace):
        proc = _Proc(0, stdout="abc1234 message\n")
        with patch("wrapper.tools.subprocess.run", return_value=proc) as m:
            result = inspect_git_log(relative_path="README.md")
        assert "message" in result
        argv = m.call_args.args[0]
        assert "--" in argv
        assert "README.md" in argv

    def test_path_traversal_rejected(self, workspace):
        with pytest.raises(PathTraversalError):
            inspect_git_log(relative_path="../../etc/passwd")

    def test_not_repo_failure(self, workspace):
        with patch("wrapper.tools.subprocess.run", side_effect=FileNotFoundError()):
            result = inspect_git_log()
        assert "git" in result.lower()

    def test_no_commits(self, workspace):
        proc = _Proc(0, stdout="")
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_log()
        assert "No commits" in result


# ------------------------------------------------------------------
# TARGET 5 â€” Bounded git diff tests
# ------------------------------------------------------------------

class TestBoundedGitDiff:
    def test_large_diff_bounded_by_max_chars(self, workspace):
        proc = _Proc(0, stdout="x" * 5000)
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff(max_chars=100)
        assert len(result) <= 100

    def test_marker_visible_when_space_permits(self, workspace):
        proc = _Proc(0, stdout="x" * 5000)
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff(max_chars=100)
        assert "truncated at 100 characters" in result

    def test_max_chars_1_no_overrun(self, workspace):
        proc = _Proc(0, stdout="x" * 5000)
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff(max_chars=1)
        assert len(result) <= 1

    def test_max_chars_2_no_overrun(self, workspace):
        proc = _Proc(0, stdout="x" * 5000)
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff(max_chars=2)
        assert len(result) <= 2

    def test_max_chars_5_no_overrun(self, workspace):
        proc = _Proc(0, stdout="x" * 5000)
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff(max_chars=5)
        assert len(result) <= 5

    def test_small_diff_unchanged(self, workspace):
        small_diff = "diff --git a/f.txt b/f.txt\n"
        proc = _Proc(0, stdout=small_diff)
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff(max_chars=20000)
        assert result == small_diff

    def test_clean_workspace_message(self, workspace):
        proc = _Proc(0, stdout="")
        with patch("wrapper.tools.subprocess.run", return_value=proc):
            result = inspect_git_diff()
        assert "No changes" in result