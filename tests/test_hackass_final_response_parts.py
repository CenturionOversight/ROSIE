"""Focused regression test for multipart HACKASS final responses."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from hackass.agent import _run_async


class _FinalEvent:
    def __init__(self) -> None:
        self.content = SimpleNamespace(
            parts=[
                SimpleNamespace(text="first "),
                SimpleNamespace(text=None),
                SimpleNamespace(text="second"),
            ]
        )

    def is_final_response(self) -> bool:
        return True


class _Runner:
    def run(self, **kwargs):
        return [_FinalEvent()]


def test_run_async_preserves_all_text_parts():
    session = SimpleNamespace(id="session-1")
    result = asyncio.run(_run_async(_Runner(), session, "hello"))
    assert result == "first second"
