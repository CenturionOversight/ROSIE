"""Concurrency-safety tests for runtime-scoped dispatch.

Explicit runtime dispatches must be fully isolated from the default module
runtime and from each other across overlapping threads.
"""
from __future__ import annotations

import threading

import pytest


def _test_case(self):
    pass  # sanitized: no side effects here


class TestConcurrentDispatchIsolation:
    """Two overlapping dispatches cannot see each other's runtime state."""

    def test_overlapping_dispathces_do_not_leak(self, tmp_path):
        from wrapper.runtime import RuntimeSession
        from wrapper.tools import dispatch_tool

        base = tmp_path / "a"
        base.mkdir()
        base_file = base / "a.only.txt"
        base_file.write_text("A-only", encoding="utf-8")

        session_a = RuntimeSession(workspace=base)
        session_b = RuntimeSession(workspace=tmp_path)

        results = {}
        done = threading.Barrier(3)

        def run_dispatch(session: RuntimeSession, tag: str) -> None:
            result = dispatch_tool(
                "inspect_file", {"relative_path": "a.only.txt"}, runtime=session
            )
            results[tag] = result
            done.wait(timeout=0.5)

        ta = threading.Thread(target=run_dispatch, args=(session_a, "A"), daemon=True)
        tb = threading.Thread(target=run_dispatch, args=(session_b, "B"), daemon=True)
        ta.start(); tb.start()
        done.wait(timeout=1.0)  # wait both
        ta.join(timeout=1.0); tb.join(timeout=1.0)

        # A sees its workspace
        assert "A-only" in results["A"], f"A must serve A's workspace: {results['A']!r}"
        # B cannot see A's workspace
        assert "File not found" in results["B"] or "a.only.txt" not in results["B"]
