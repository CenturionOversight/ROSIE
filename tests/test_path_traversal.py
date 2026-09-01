"""Tests for path traversal protection and path resolution."""
import sys

import pytest

from wrapper.tools import PathTraversalError, _resolve_safe_path, set_workspace_root


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Set up a temporary workspace root."""
    root = tmp_path.resolve()
    set_workspace_root(root)
    monkeypatch.setattr("wrapper.tools._workspace_root", root)
    return root


class TestPathTraversal:
    def test_safe_path_relative_file(self, workspace):
        result = _resolve_safe_path(workspace, "subdir/file.txt")
        assert result == (workspace / "subdir" / "file.txt").resolve()

    def test_safe_path_current_dir(self, workspace):
        result = _resolve_safe_path(workspace, ".")
        assert result == workspace

    def test_safe_path_absolute_within_root(self, workspace):
        inner = workspace / "subdir" / "file.txt"
        inner.parent.mkdir(parents=True, exist_ok=True)
        inner.touch()
        result = _resolve_safe_path(workspace, str(inner))
        assert result == inner.resolve()

    def test_traversal_dotdot_blocked(self, workspace):
        with pytest.raises(PathTraversalError):
            _resolve_safe_path(workspace, "..")

    def test_traversal_deep_dotdot_blocked(self, workspace):
        with pytest.raises(PathTraversalError):
            _resolve_safe_path(workspace, "../../etc/passwd")

    def test_traversal_encoded_dotdot_blocked(self, workspace):
        with pytest.raises(PathTraversalError):
            _resolve_safe_path(workspace, "subdir/../../../etc/passwd")

    def test_traversal_absolute_outside_blocked(self, workspace):
        with pytest.raises(PathTraversalError):
            _resolve_safe_path(workspace, "/etc/passwd")

    @pytest.mark.skipif(sys.platform == "win32", reason="Symlinks require admin on Windows")
    def test_traversal_symlink_escape_blocked(self, workspace, tmp_path):
        link_dir = workspace / "link"
        outside = tmp_path.parent / "outside"
        outside.mkdir(exist_ok=True)
        if link_dir.exists() or link_dir.is_symlink():
            link_dir.unlink()
        link_dir.symlink_to(outside, target_is_directory=True)
        with pytest.raises(PathTraversalError):
            _resolve_safe_path(workspace, "link/escape.txt")

    def test_no_follow_final_parent_ref_blocked(self, workspace):
        from wrapper.tools import _resolve_safe_path_no_follow
        with pytest.raises(PathTraversalError):
            _resolve_safe_path_no_follow(workspace, "sub/..")
        with pytest.raises(PathTraversalError):
            _resolve_safe_path_no_follow(workspace, "..")


class TestParentRefMutationGuards:
    """delete_path/move_path must never act on a final '..' component: the
    OS would resolve it against the real parent directory, bypassing the
    lexical root guard (regression: delete_path('sub/..') deleted the whole
    workspace; delete_path('..') deleted the workspace's parent)."""

    @pytest.fixture(autouse=True)
    def _yolo(self, workspace, monkeypatch):
        from wrapper.policy import ApprovalPolicy, ExecutionPolicy
        from wrapper.tools import set_policy
        set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))

    def test_delete_path_parent_ref_keeps_workspace(self, workspace):
        from wrapper.tools import delete_path
        (workspace / "sub").mkdir()
        (workspace / "precious.txt").write_text("KEEP", encoding="utf-8")
        with pytest.raises(PathTraversalError):
            delete_path("sub/..", recursive=True)
        assert (workspace / "precious.txt").exists()
        assert (workspace / "sub").exists()

    def test_delete_path_dotdot_cannot_escape_workspace(self, workspace, tmp_path):
        from wrapper.tools import delete_path
        sentinel = tmp_path / "outside.txt"
        sentinel.write_text("O", encoding="utf-8")
        with pytest.raises(PathTraversalError):
            delete_path("..", recursive=True)
        assert sentinel.exists()
        assert workspace.exists()

    def test_interior_parent_ref_still_resolves(self, workspace):
        from wrapper.tools import delete_path
        (workspace / "a" / "b").mkdir(parents=True)
        target = workspace / "a" / "f.txt"
        target.write_text("x", encoding="utf-8")
        result = delete_path("a/b/../f.txt")
        assert "Successfully deleted" in result
        assert not target.exists()

