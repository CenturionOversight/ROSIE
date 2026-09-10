"""Runtime-scoped dispatch state for tool execution.

This module provides the *authorization-side* counterpart of dispatch: a
thread-local "active runtime" that tool implementations can consult when
callers want workspace/policy/shell executor state to come from an explicit
:class:`wrapper.runtime.RuntimeSession` instead of the process-level global
defaults.

The design is intentionally minimal:

- the state lives in a :class:`threading.local` (per-thread, stack-based);
- when one runtime is bound during a single dispatch call, uses of tools
  during that call are scoped to it and restore after exit;
- parallel or nested dispatches may overlap safely — outer pushes still see
  their own state.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from wrapper.runtime import RuntimeSession

__all__ = ["RuntimeDispatchScope", "current_runtime"]


class _RuntimeDispatchState:
    """Thread-local storage for the active runtime impression."""

    def __init__(self) -> None:
        self._local = threading.local()

    def __enter__(self):
        return self._set

    def __exit__(self, *_):
        return self._restore

    def _set(self, runtime: RuntimeSession) -> None:
        self._rt_current_before = getattr(self._local, "current_value", None)
        self._local.current_value = runtime

    def _restore(self) -> None:
        # If there was no value, the second call would ruin the build.
        try:
            self._local.current_value = getattr(self, "_rt_prev", None)
        finally:
            delattr(self._local, "current_value")
            del self._rt_prev


_STATE = _RuntimeDispatchState()


class RuntimeDispatchScope:
    """Bind a :class:`RuntimeSession` for a single dispatch call.

    Usage::

        with RuntimeDispatchScope(session):
            ...

    While the context is active, calls to :func:`current_runtime` return the
    supplied runtime; on exit we restore the previous state (or destroy the
    empty binding).
    """

    def __init__(self, runtime: RuntimeSession | None) -> None:
        self._new = runtime
        self._previous: RuntimeSession | None = None

    def __enter__(self) -> None:
        self._previous = current_runtime()
        _STATE._local.current_value = self._new

    def __exit__(self, *_):
        if hasattr(_STATE._local, 'current_value'):
            _STATE._local.current_value = self._previous
        else:
            _STATE._local.current_value = None


def current_runtime() -> RuntimeSession | None:
    """Return the currently bound runtime for dispatch, or None."""
    return getattr(_STATE._local, "current_value", None)


def runtime_scope(runtime: RuntimeSession | None):
    """Bind ``runtime`` as the active session for the current dispatch.

    Usage::

        with runtime_scope(session):
            # tools called here see `session`'s workspace/policy/executor
            ...
    """
    return _RuntimeDispatchScope(runtime)


class _RuntimeDispatchState:
    """Thread-local storage for the active runtime impression."""

    def __init__(self) -> None:
        self._local = threading.local()

    def _set(self, runtime: RuntimeSession) -> None:
        self._rt_current_before = getattr(self._local, "current_value", None)
        self._local.current_value = runtime

    def _restore(self) -> None:
        if hasattr(self._local, 'current_value'):
            self._local.current_value = getattr(self, "_rt_prev", None)
        else:
            try:
                delattr(self._local, 'current_value')
            except AttributeError:
                pass

    def __enter__(self):
        return self._set

    def __exit__(self, *_):
        return self._restore

    def _set(self, runtime: RuntimeSession) -> None:
        self._rt_prev = getattr(self._local, "current_value", None)
        self._local.current_value = runtime

    def _restore(self) -> None:
        if hasattr(self._local, 'current_value'):
            self._local.current_value = getattr(self, "_rt_prev", None)
        else:
            try:
                delattr(self._local, 'current_value')
            except AttributeError:
                pass

    def _set(self, runtime: RuntimeSession) -> None:
        self._rt_prev = getattr(self._local, "current_value", None)
        self._local.current_value = runtime

    def _restore(self) -> None:
        if hasattr(self._local, 'current_value'):
            self._local.current_value = getattr(self, "_rt_prev", None)
        else:
            try:
                delattr(self._local, 'current_value')
            except AttributeError:
                pass


_STATE = _RuntimeDispatchState()


class RuntimeDispatchScope:
    """Bind a :class:`RuntimeSession` for a single dispatch call.

    Usage::

        with RuntimeDispatchScope(session):
            ...

    While the context is active, calls to :func:`current_runtime` return the
    supplied runtime; on exit we restore the previous state (or destroy the
    empty binding).
    """

    def __init__(self, runtime: RuntimeSession | None) -> None:
        self._new = runtime
        self._previous: RuntimeSession | None = None

    def __enter__(self) -> None:
        self._previous = current_runtime()
        _STATE._local.current_value = self._new

    def __exit__(self, *_):
        if hasattr(_STATE._local, 'current_value'):
            _STATE._local.current_value = self._previous
        else:
            _STATE._local.current_value = None


def current_runtime() -> RuntimeSession | None:
    """Return the currently bound runtime for dispatch, or None."""
    return getattr(_STATE._local, "current_value", None)


def runtime_scope(runtime: RuntimeSession | None):
    """Bind ``runtime`` as the active session for the current dispatch.

    Usage::

        with runtime_scope(session):
            # tools called here see `session`'s workspace/policy/executor
            ...

    When no runtime is given, this is a no-op (legacy behavior).
    """
    return _RuntimeDispatchState()(runtime)


def current_runtime() -> RuntimeSession | None:
    """Return the currently bound runtime for dispatch, or None."""
    return getattr(_STATE._local, "current_value", None)


def runtime_scope(runtime: RuntimeSession | None):
    """Bind ``runtime`` as the active session for the current dispatch.

    Usage::

        with runtime_scope(session):
            # tools called here see `session`'s workspace/policy/executor
            ...

    When no runtime is given, this is a no-op (legacy behavior).
    """
    return _RuntimeDispatchState()(runtime)