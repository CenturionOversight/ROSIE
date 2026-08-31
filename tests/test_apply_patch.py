"""Tests for the apply_patch targeted-edit tool."""
from pathlib import Path
from unittest.mock import patch

import pytest

from wrapper.policy import ApprovalPolicy, ExecutionPolicy
from wrapper.tools import (
    PathTraversalError,
    apply_patch,
    inspect_file,
    set_policy,
    set_workspace_root,
    write_file,
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    set_workspace_root(root)
    monkeypatch.setattr("wrapper.tools._workspace_root", root)
    return root


@pytest.fixture
def yolo_policy(monkeypatch):
    policy = ApprovalPolicy(ExecutionPolicy.YOLO)
    set_policy(policy)
    monkeypatch.setattr("wrapper.tools._policy", policy)
    return policy


@pytest.fixture
def ask_policy(monkeypatch):
    policy = ApprovalPolicy(ExecutionPolicy.ASK)
    set_policy(policy)
    monkeypatch.setattr("wrapper.tools._policy", policy)
    return policy


class TestApplyPatch:
    def test_successful_unique_replacement(self, workspace, yolo_policy):
        (workspace / "f.txt").write_text("hello\nfoo\nworld\n", encoding="utf-8")
        result = apply_patch("f.txt", "foo", "bar")
        assert "Successfully patched" in result
        assert "bar" in (workspace / "f.txt").read_text()
        assert "foo" not in (workspace / "f.txt").read_text()

    def test_only_exact_match_replaced(self, workspace, yolo_policy):
        (workspace / "f.txt").write_text("aaa foo bbb\nccc foo ddd\n", encoding="utf-8")
        result = apply_patch("f.txt", "aaa foo bbb", "changed")
        assert "Successfully patched" in result
        content = (workspace / "f.txt").read_text()
        assert "changed" in content
        assert "ccc foo ddd" in content  # the other occurrence untouched

    def test_zero_match_rejected_no_modification(self, workspace, yolo_policy):
        (workspace / "f.txt").write_text("hello world\n", encoding="utf-8")
        result = apply_patch("f.txt", "does-not-exist", "x")
        assert "not found" in result.lower()
        assert "not modified" in result.lower()
        assert (workspace / "f.txt").read_text() == "hello world\n"

    def test_multiple_match_ambiguity_rejected(self, workspace, yolo_policy):
        (workspace / "f.txt").write_text("foo\nbar\nfoo\n", encoding="utf-8")
        result = apply_patch("f.txt", "foo", "x")
        assert "matches 2 locations" in result.lower() or "ambigu" in result.lower()
        assert "not modified" in result.lower()
        assert (workspace / "f.txt").read_text() == "foo\nbar\nfoo\n"

    def test_path_traversal_rejected(self, workspace, yolo_policy):
        with pytest.raises(PathTraversalError):
            apply_patch("../outside.txt", "a", "b")

    def test_binary_file_rejected(self, workspace, yolo_policy):
        (workspace / "bin.dat").write_bytes(b"\x00\x01\x02\xff")
        result = apply_patch("bin.dat", "x", "y")
        assert "binary" in result.lower()
        assert (workspace / "bin.dat").read_bytes() == b"\x00\x01\x02\xff"

    def test_nonexistent_file_rejected(self, workspace, yolo_policy):
        result = apply_patch("missing.txt", "a", "b")
        assert "does not exist" in result.lower()

    def test_diff_generated(self, workspace, yolo_policy, capsys):
        (workspace / "f.txt").write_text("old line\n", encoding="utf-8")
        apply_patch("f.txt", "old line", "new line")
        captured = capsys.readouterr().out
        assert "diff preview" in captured or "Diff" in captured or "old line" in captured

    def test_approval_denied_leaves_file_unchanged(self, workspace, ask_policy, monkeypatch):
        (workspace / "f.txt").write_text("keep this\n", encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _: "n")
        result = apply_patch("f.txt", "keep this", "changed")
        assert "DENIED" in result
        assert "not modified" in result.lower()
        assert (workspace / "f.txt").read_text() == "keep this\n"

    def test_yolo_auto_approves(self, workspace, yolo_policy, capsys):
        (workspace / "f.txt").write_text("foo\n", encoding="utf-8")
        result = apply_patch("f.txt", "foo", "bar")
        assert "Successfully patched" in result
        assert "bar" in (workspace / "f.txt").read_text()

    def test_auto_write_approves_patch(self, workspace, monkeypatch):
        policy = ApprovalPolicy(ExecutionPolicy.AUTO_WRITE)
        set_policy(policy)
        monkeypatch.setattr("wrapper.tools._policy", policy)
        (workspace / "f.txt").write_text("foo\n", encoding="utf-8")
        result = apply_patch("f.txt", "foo", "bar")
        assert "Successfully patched" in result

    def test_approval_matches_write_file_behavior(self, workspace):
        # Same approval flow: write_file and apply_patch both gate on "write".
        assert ApprovalPolicy(ExecutionPolicy.ASK).is_auto_approved("write") is False
        assert ApprovalPolicy(ExecutionPolicy.AUTO_WRITE).is_auto_approved("write") is True
        assert ApprovalPolicy(ExecutionPolicy.YOLO).is_auto_approved("write") is True

    def test_parent_and_other_content_preserved(self, workspace, yolo_policy):
        (workspace / "f.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        apply_patch("f.txt", "two", "TWO")
        assert (workspace / "f.txt").read_text() == "one\nTWO\nthree\n"
