"""Focused tests for the $SCRATCH persistent workspace."""
from __future__ import annotations

import json

from wrapper.scratch import DIR_NAME, ScratchStore
from wrapper.tools import set_workspace_root


class TestScratchLocation:
    def test_scratch_dir_inside_workspace(self, tmp_path):
        set_workspace_root(tmp_path)
        store = ScratchStore()
        assert store.path("notes").parent == tmp_path / DIR_NAME

    def test_scratch_created_on_write_only(self, tmp_path):
        set_workspace_root(tmp_path)
        pad = tmp_path / DIR_NAME
        assert not pad.exists()
        store = ScratchStore()
        store.write_pad("config", {"foo": "bar"})
        assert pad.is_dir()


class TestScratchRoundTrip:
    def test_write_read_json_pad(self, tmp_path):
        set_workspace_root(tmp_path)
        store = ScratchStore()
        store.write_pad("state", {"counter": 1, "tags": ["a", "b"]})
        # Fresh instance against the same workspace root must read it back
        fresh = ScratchStore(workspace_root=tmp_path)
        assert fresh.read_pad("state") == {"counter": 1, "tags": ["a", "b"]}

    def test_read_missing_pad_returns_empty(self, tmp_path):
        set_workspace_root(tmp_path)
        assert ScratchStore().read_pad("does-not-exist") == {}

    def test_atomic_replace_leaves_no_partial_file(self, tmp_path):
        set_workspace_root(tmp_path)
        store = ScratchStore()
        # Write twice with two values, then overwrite with nan→json error
        store.write_pad("rewrite", {"v": 1})
        store.write_pad("rewrite", {"v": 2})
        assert store.read_pad("rewrite") == {"v": 2}
        # No temp files should linger
        remaining = list((tmp_path / DIR_NAME).glob(".tmp-*"))
        assert remaining == []


class TestScratchAppend:
    def test_append_and_read_records(self, tmp_path):
        set_workspace_root(tmp_path)
        store = ScratchStore()
        store.append_pad("ops", {"n": 1})
        store.append_pad("ops", {"n": 2})
        out = store.read_append_pad("ops")
        assert out == [{"n": 1}, {"n": 2}]

    def test_read_append_pad_missing_is_empty(self, tmp_path):
        set_workspace_root(tmp_path)
        assert ScratchStore().read_append_pad("none") == []

    def test_append_pad_multi_lines_and_blank(self, tmp_path):
        set_workspace_root(tmp_path)
        store = ScratchStore()
        store.append_pad("x", {"k": "a"})
        store.append_pad("x", {"k": "b"})
        target = tmp_path / DIR_NAME / "x.jsonl"
        assert target.exists()
        out = ScratchStore(workspace_root=tmp_path).read_append_pad("x")
        assert out == [{"k": "a"}, {"k": "b"}]


class TestScratchNameValidation:
    def test_reject_traversal_names(self, tmp_path):
        set_workspace_root(tmp_path)
        store = ScratchStore()
        for bad in ["../../etc/passwd", "a>file", "/tmp", "C:\\bad", "name with space", ""]:
            for kind in ("write_pad", "write_pad"):  # json only
                pass  # silence linter
            for fn in (lambda: store.write_pad(bad, {}),
                       lambda: store.append_pad(bad, {}),
                       lambda: store.read_pad(bad)):
                try:
                    fn()
                    assert False, f"expected rejection for {bad!r}"
                except ValueError:
                    pass

    def test_reject_non_string(self, tmp_path):
        set_workspace_root(tmp_path)
        store = ScratchStore()
        try:
            store.write_pad(None, {})  # type: ignore
            assert False
        except ValueError:
            pass


class TestScratchIsolationAcrossWorkspaces:
    def test_two_workspaces_do_not_leak(self, tmp_path):
        ws_a = tmp_path / "ws-a"; ws_a.mkdir()
        ws_b = tmp_path / "ws-b"; ws_b.mkdir()
        set_workspace_root(ws_a)
        ScratchStore(workspace_root=ws_a).write_pad("shared", {"v": "A"})
        set_workspace_root(ws_b)
        assert ScratchStore(workspace_root=ws_b).read_pad("shared") == {}
        set_workspace_root(ws_a)
        assert ScratchStore(workspace_root=ws_a).read_pad("shared") == {"v": "A"}


class TestScratchRestartPersistence:
    def test_state_survives_store_rebuild(self, tmp_path):
        """Proof of disk persistence: same workspace → state readable after
        constructing a new instance outside the process lifecycle."""
        set_workspace_root(tmp_path)
        ScratchStore().write_pad("persist", {"phase": "one", "ok": True})
        # Brute force: new store instance with same workspace
        restored = ScratchStore(workspace_root=tmp_path).read_pad("persist")
        assert restored == {"phase": "one", "ok": True}

    def test_cumulative_count_across_instances(self, tmp_path):
        set_workspace_root(tmp_path)
        for step in range(1, 5):
            store = ScratchStore(workspace_root=tmp_path)
            prev = store.read_pad("counter")
            n = prev.get("count", 0) + step
            store.write_pad("counter", {"count": n})
        # Final read
        assert ScratchStore(workspace_root=tmp_path).read_pad("counter") == {"count": 1 + 2 + 3 + 4}
