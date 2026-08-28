"""Tests for path traversal protection and path resolution."""
import sys
from pathlib import Path

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
