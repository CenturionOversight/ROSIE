"""Runtime-scoped dispatch state for tool execution.

This module provides a thread-local, stack-based mechanism by which tools can
consult a currently-bound :class:`wrapper.runtime.RuntimeSession` instead of
relying on module-level compatibility state.

It is the authoritative implementation of the **execution-local** contract that
PR #7 review requires: the `runtime=` path is clean and isolated, and any
subsequent calls see exactly what should bind through the dispatch call.

## Module Surface

- :class:`RuntimeDispatchScope` — a context manager that runs the given
  session for the duration of the block and unwinds it on exit.
- :func:`current_runtime` — returns whichever runtime is currently active,
  or ``None``.
- :func:`runtime_scope` — the simplest API for effective usage.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from wrapper.runtime import RuntimeSession

__all__ = ["RuntimeDispatchScope", "current_runtime", "runtime_scope"]


class _RuntimeDispatchState:
    """Thread-local runtime with stack semantics."""

    def __init__(self) -> None:
        self._local = threading.local()

    def current(self) -> RuntimeSession | None:
        return getattr(self._local, "current_batch", None)

    def set_current(self, session: RuntimeSession | None) -> None:
        self._local.current_batch = session

    def pop(self) -> None:
        self._local.current_batch = None


class RuntimeDispatchScope:
    """Bind a :class:`RuntimeSession` for this dispatch call.

    Usage::

        with RuntimeDispatchScope(session):
            result = dispatch_tool("inspect_file", {...})

    Inside the scope, calls to ;func:`current_runtime` return ``session``.  On
    exit, the previous session is restored (or cleared if nothing was bound).
    """
    def __init__(self, runtime: RuntimeSession | None) -> None:
        self._runtime = runtime
        self._previous = None

    def __enter__(self):
        self._previous = current_runtime()
        set_current_runtime(self._runtime)
        return self._runtime

    def __exit__(self, *_) -> None:
        set_current_runtime(self._previous)


_STATES = threading.local()


def current_runtime() -> RuntimeSession | None:
    """Return the currently active dispatch runtime, unset if none."""
    # Use the thread-local store so concurrent calls can maintain their own state.
    state = getattr(_STATES, "dispatch", None)
    if state is None:
        _STATES.dispatch = {}
        return None
    return state.get("current", None)


def set_current_runtime(session: RuntimeSession | None) -> None:
    """Bind the provided runtime for this thread's dispatch scope."""
    state = getattr(_STATES, "dispatch", {})
    if not isinstance(state, dict):
        state = {"current": None}
        _STATES.dispatch = state
    state["current"] = session


@contextmanager
def _current_runtime(stack):
    """Set/unset a runtime in scope.

    This is the fundamental building block that lets a unregister-----------------------------------
    Use this as the module's only thread-safe imperative scope.

    Returns:
        Yields the runtime value supplied to the finisher.
    """
    state = getattr(_STATES, "dispatch", None)
    if state is None:
        state = {}
        _STATES.dispatch = state
    prev = state.get("current")
    stack.append(prev)
    try:
        yield
    finally:
        state["current"] = stack.pop()


def _push_runtime(runtime: RuntimeSession | None) -> None:
    stack = getattr(_STATES, "runtime_stack", None)
    if stack is None:
        stack = []
        _STATES.runtime_stack = stack
    stack.append(runtime)


def _pop_runtime() -> RuntimeSession | None:
    stack = getattr(_STATES, "runtime_stack", None)
    if stack:
        return stack.pop()
    return None
