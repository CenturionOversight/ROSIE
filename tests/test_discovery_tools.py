"""Tests for list_directory and search_workspace discovery tools."""
import os
import sys
from pathlib import Path

import pytest

from wrapper.tools import (
    ListDirectoryArgs,
    SearchWorkspaceArgs,
    _resolve_safe_path,
    list_directory,
    search_workspace,
    set_workspace_root,
    PathTraversalError,
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    set_workspace_root(root)
    monkeypatch.setattr("wrapper.tools._workspace_root", root)
    # Build a small fixture tree.
    (root / "file_a.txt").write_text("alpha content\n")
    (root / "file_b.py").write_text("print('hello')\n")
    (root / "subdir").mkdir()
    (root / "subdir" / "nested.md").write_text("# Nested\n")
    (root / "readme.md").write_text("alpha\n")
    return root


class TestListDirectory:
    def test_top_level_listing(self, workspace):
        result = list_directory(".")
        entries = result.splitlines()
        assert "file_a.txt" in entries
        assert "file_b.py" in entries
        assert "subdir/" in entries
        assert "readme.md" in entries

    def test_subdirectory_listing(self, workspace):
        result = list_directory("subdir")
        entries = result.splitlines()
        assert "subdir/nested.md" in entries

    def test_directories_have_trailing_slash(self, workspace):
        result = list_directory(".")
        assert "subdir/" in result
        assert "file_a.txt" in result
        # file_a.txt should not end with /
        for line in result.splitlines():
            if line.endswith("file_a.txt"):
                assert not line.endswith("/")

    def test_recursive_listing(self, workspace):
        result = list_directory(".", recursive=True)
        entries = result.splitlines()
        assert "file_a.txt" in entries
        assert "subdir/" in entries
        assert "subdir/nested.md" in entries
        assert "readme.md" in entries

    def test_recursive_includes_all_depths(self, workspace):
        (workspace / "deep").mkdir()
        (workspace / "deep" / "level2").mkdir()
        (workspace / "deep" / "level2" / "leaf.txt").write_text("leaf\n")
        result = list_directory(".", recursive=True)
        assert "deep/" in result
        assert "deep/level2/" in result
        assert "deep/level2/leaf.txt" in result

    def test_max_entries_enforced(self, workspace):
        for i in range(20):
            (workspace / f"many_{i}.txt").write_text("x\n")
        result = list_directory(".", recursive=False, max_entries=5)
        entries = result.splitlines()
        assert len(entries) == 5

    def test_max_entries_recursive(self, workspace):
        for i in range(20):
            (workspace / f"many_{i}.txt").write_text("x\n")
        result = list_directory(".", recursive=True, max_entries=5)
        entries = result.splitlines()
        assert len(entries) == 5

    def test_path_traversal_rejected(self, workspace):
        with pytest.raises(PathTraversalError):
            list_directory("../")
        with pytest.raises(PathTraversalError):
            list_directory("../../etc/passwd")

    def test_nonexistent_path(self, workspace):
        with pytest.raises(FileNotFoundError):
            list_directory("does_not_exist")

    def test_empty_directory(self, workspace, tmp_path):
        empty = workspace / "empty_dir"
        empty.mkdir()
        result = list_directory("empty_dir")
        assert result == "(empty)"


class TestListDirectoryIgnoredDirs:
    def test_git_dir_skipped_non_recursive(self, workspace):
        (workspace / ".git").mkdir()
        (workspace / ".git" / "config").write_text("git\n")
        result = list_directory(".")
        assert ".git/" not in result
        assert ".git" not in result

    def test_git_dir_skipped_recursive(self, workspace):
        (workspace / ".git").mkdir()
        (workspace / ".git" / "config").write_text("git\n")
        result = list_directory(".", recursive=True)
        assert ".git/" not in result
        assert ".git/config" not in result

    def test_node_modules_skipped(self, workspace):
        (workspace / "node_modules").mkdir()
        (workspace / "node_modules" / "pkg.js").write_text("// js\n")
        result = list_directory(".", recursive=True)
        assert "node_modules/" not in result
        assert "node_modules/pkg.js" not in result

    def test_pycache_skipped(self, workspace):
        (workspace / "__pycache__").mkdir()
        (workspace / "__pycache__" / "mod.cpython").write_text("x\n")
        result = list_directory(".", recursive=True)
        assert "__pycache__/" not in result

    def test_pytest_cache_skipped(self, workspace):
        (workspace / ".pytest_cache").mkdir()
        result = list_directory(".", recursive=True)
        assert ".pytest_cache" not in result


class TestSearchWorkspace:
    def test_content_search(self, workspace):
        result = search_workspace("alpha")
        lines = result.splitlines()
        # file_a.txt and readme.md both contain "alpha"
        paths_found = set()
        for line in lines:
            if ":" in line and "/" not in line.split(":")[0]:
                # content hit: path:line:text
                pass
            paths_found.add(line.split(":")[0] if ":" in line else line)
        assert any("file_a.txt" in p for p in paths_found)
        assert any("readme.md" in p for p in paths_found)

    def test_filename_search(self, workspace):
        result = search_workspace("file_a")
        assert "file_a.txt" in result

    def test_filename_match_returns_path(self, workspace):
        result = search_workspace("file_b")
        assert "file_b.py" in result

    def test_case_insensitive_search(self, workspace):
        result = search_workspace("ALPHA")
        lines = result.splitlines()
        # Should still find content containing "alpha"
        joined = "\n".join(lines)
        assert "file_a.txt" in joined

    def test_path_name_match(self, workspace):
        result = search_workspace("nested")
        assert "subdir/nested.md" in result

    def test_no_results(self, workspace):
        result = search_workspace("zzz_nonexistent_string")
        assert "No results" in result

    def test_max_results_enforced(self, workspace, tmp_path):
        for i in range(60):
            (workspace / f"file_{i}.txt").write_text(f"unique_marker_{i}\n")
        result = search_workspace("unique_marker", max_results=5)
        lines = result.splitlines()
        assert len(lines) == 5

    def test_binary_skipped(self, workspace):
        (workspace / "binary.dat").write_bytes(b"\x00\x01\x02\xff\xfe")
        # Should not crash, should not find "alpha" in binary
        result = search_workspace("alpha")
        # binary.dat should not appear
        assert "binary.dat" not in result

    def test_large_file_skipped(self, workspace):
        big = workspace / "bigfile.txt"
        big.write_text("alpha " * 200000)  # ~1MB+
        result = search_workspace("alpha")
        assert "bigfile.txt" not in result


class TestSearchWorkspaceIgnoredDirs:
    def test_search_skips_git(self, workspace):
        (workspace / ".git").mkdir()
        (workspace / ".git" / "commit_msg").write_text("alpha\n")
        result = search_workspace("alpha")
        assert ".git/" not in result
        assert ".git" not in result

    def test_search_skips_node_modules(self, workspace):
        (workspace / "node_modules").mkdir()
        (workspace / "node_modules" / "index.js").write_text("alpha\n")
        result = search_workspace("alpha")
        assert "node_modules/" not in result


class TestSearchWorkspacePathSafety:
    def test_path_traversal_rejected(self, workspace):
        with pytest.raises(PathTraversalError):
            search_workspace("alpha", "../../../")


class TestSearchWorkspaceScanBudget:
    def test_match_beyond_previous_candidate_boundary_is_found(self, workspace):
        """A match after max_results*4 files must still be found with max_files."""
        # The old behavior only examined max_results*4 candidates. With
        # max_results=1 that was 4 files, so a match in the 5th file would
        # have been silently missed. The scan budget finds it.
        for i in range(10):
            (workspace / f"bulk_{i}.txt").write_text(f"needle_{i}\n")
        result = search_workspace("needle_7", max_results=1, max_files=100)
        assert "bulk_7.txt" in result

    def test_search_stops_at_max_results(self, workspace):
        for i in range(60):
            (workspace / f"file_{i}.txt").write_text(f"unique_marker_{i}\n")
        result = search_workspace("unique_marker", max_results=5, max_files=100)
        # 5 matches, possibly plus no truncation notice (space exhausted).
        lines = [l for l in result.splitlines() if not l.startswith("(")]
        assert len(lines) == 5

    def test_search_stops_at_max_files(self, workspace):
        for i in range(20):
            (workspace / f"f{i}.txt").write_text("marker\n")
        # max_files=5 limits how many files are examined
        result = search_workspace("marker", max_files=5, max_results=50)
        assert "search truncated after 5 files" in result

    def test_truncation_notice_present_when_budget_exhausted(self, workspace):
        for i in range(10):
            (workspace / f"f{i}.txt").write_text("marker\n")
        result = search_workspace("marker", max_files=3, max_results=50)
        assert "search truncated after 3 files" in result

    def test_exhaustive_search_has_no_false_truncation(self, workspace):
        for i in range(5):
            (workspace / f"f{i}.txt").write_text("marker\n")
        result = search_workspace("marker", max_files=100, max_results=50)
        assert "truncated after" not in result

    def test_path_name_hit_does_not_suppress_content_hits(self, workspace, tmp_path):
        """A path matching the query must still be content-searched."""
        # File whose name AND content both match.
        (workspace / "needle_box.txt").write_text("needle is inside\n", encoding="utf-8")
        result = search_workspace("needle", max_files=100)
        lines = result.splitlines()
        # Path hit: "needle_box.txt" (bare path)
        assert any(l == "needle_box.txt" for l in lines)
        # Content hit from the same file: "needle_box.txt:1:needle is inside"
        assert any(l.startswith("needle_box.txt:") for l in lines)
