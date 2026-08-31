from __future__ import annotations

import os
from pathlib import Path

import pytest

from wrapper.tools import move_path, set_policy, set_workspace_root


def _make_dangling_symlink(path: Path, target: str) -> None:
    try:
        path.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable in this environment: {exc}")


def test_move_path_allows_dangling_symlink_source(tmp_path: Path) -> None:
    set_workspace_root(tmp_path)
    set_policy(None)  # type: ignore[arg-type]

    src = tmp_path / "dangling-link"
    dst = tmp_path / "moved-link"
    _make_dangling_symlink(src, "missing-target")

    result = move_path("dangling-link", "moved-link")

    assert result.startswith("Successfully moved")
    assert not src.exists() and not src.is_symlink()
    assert dst.is_symlink()
    assert os.readlink(dst) == "missing-target"


def test_move_path_refuses_dangling_symlink_destination(tmp_path: Path) -> None:
    set_workspace_root(tmp_path)
    set_policy(None)  # type: ignore[arg-type]

    src = tmp_path / "source.txt"
    src.write_text("keep me", encoding="utf-8")
    dst = tmp_path / "dangling-destination"
    _make_dangling_symlink(dst, "missing-target")

    result = move_path("source.txt", "dangling-destination")

    assert "already exists" in result
    assert src.read_text(encoding="utf-8") == "keep me"
    assert dst.is_symlink()
    assert os.readlink(dst) == "missing-target"
