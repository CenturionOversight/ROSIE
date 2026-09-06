"""RuntimeSession: explicit runtime ownership of execution state.

This module defines the canonical ownership boundary for ROSIE runtime
state: a :class:`RuntimeSession` instance owns its workspace root, approval
policy, and shell executor.

Traditional module-global state in :mod:`wrapper.tools` is kept live for
backward compatibility, but the *default* `RuntimeSession` is the
authoritative store.  A second :class:`RuntimeSession` constructed
independently will not disturb the default one; dispatch should always be
scoped to a session to prevent cross-RuntimeSession contamination.

Nothing here refers to HACKASS, ARCHESTRATOR, or any other product name.
"""
from __future__ import annotations

import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from wrapper.policy import ApprovalPolicy

__all__ = ["RuntimeSession", "get_default_session"]


def _check_open(session: RuntimeSession) -> None:
    if session._closed:
        raise RuntimeError(
            f"{type(session).__name__} was closed; re-open or construct a new one."
        )


class RuntimeSession:
    """Runtime-scoped execution state for one ROSIE context.

    Owns:

    - ``workspace_root`` — the only directory this runtime may touch through
      the bounded file tools;
    - ``policy`` — the :class:`wrapper.policy.ApprovalPolicy` governing
      ``write``/``shell`` mutation;
    - ``shell_executor`` — the callable executed when ``run_shell`` is
      dispatched (``None`` means the default subprocess executor).

    Dependencies are taken explicitly through constructor arguments or
    through the ``set_*`` methods; nothing reads from module-global state
    outside of ``wrapper.tools``.
    """

    def __init__(
        self,
        workspace: str | Path | None = None,
        policy: ApprovalPolicy | None = None,
        shell_executor: Any = None,
    ) -> None:
        self._workspace_root = Path(workspace).resolve() if workspace is not None else None
        self._policy = policy
        self._shell_executor = shell_executor
        self._closed = False
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_closed(self) -> bool:
        """True after :meth:`close` has run."""
        return self._closed

    def close(self) -> bool:
        """Release owned resources (idempotent).  Returns ``True`` when a
        non-NULL executor was actually closed."""
        if self._closed:
            return False
        self._closed = True
        executor = self._shell_executor
        self._shell_executor = None
        if executor is not None:
            close = getattr(executor, "close", None)
            if callable(close):
                with suppress(Exception):
                    close()
        return True

    # ------------------------------------------------------------------
    # Workspace ownership
    # ------------------------------------------------------------------

    @property
    def workspace_root(self) -> Path:
        """The resolved workspace root.  Raises when not configured."""
        _check_open(self)
        if self._workspace_root is None:
            raise RuntimeError(
                "Workspace root has not been set; call set_workspace_root() first."
            )
        return self._workspace_root

    def has_workspace(self) -> bool:
        """True when a workspace root has been set and not closed."""
        return not self._closed and self._workspace_root is not None

    def set_workspace_root(self, path: str | Path) -> None:
        """Configure the workspace root for this runtime."""
        _check_open(self)
        self._workspace_root = Path(path).resolve()

    # ------------------------------------------------------------------
    # Approval policy ownership
    # ------------------------------------------------------------------

    @property
    def policy(self) -> ApprovalPolicy | None:
        _check_open(self)
        return self._policy

    def set_policy(self, policy: ApprovalPolicy) -> None:
        _check_open(self)
        self._policy = policy

    def has_policy(self) -> bool:
        return not self._closed and self._policy is not None

    # ------------------------------------------------------------------
    # Shell executor ownership
    # ------------------------------------------------------------------

    @property
    def shell_executor(self) -> Any:
        """The current shell executor, or ``None`` (default subprocess).

        Read-only after close — it is acceptable for an observer to see
        the executor once a runtime has been torn down; mutation endpoints
        (:meth:`set_shell_executor`) are the boundary that rejects.
        """
        return self._shell_executor

    def set_shell_executor(self, executor: Any) -> None:
        _check_open(self)
        self._shell_executor = executor

    def has_shell_executor(self) -> bool:
        return not self._closed and self._shell_executor is not None


# ----------------------------------------------------------------------
# Default session
# ----------------------------------------------------------------------

_default_lock = threading.Lock()
_default_session: RuntimeSession | None = None


def get_default_session() -> RuntimeSession:
    """Return the process-wide default :class:`RuntimeSession`.

    The default session is the one reached by legacy module-level setters
    in ``wrapper.tools`` (``set_workspace_root`` / ``set_policy`` / ...).
    """
    global _default_session
    if _default_session is None:
        with _default_lock:
            if _default_session is None:
                _default_session = RuntimeSession()
    return _default_session


def _set_default_session(session: RuntimeSession) -> None:
    """Replace the default session (tests / advanced bootstrapping only)."""
    global _default_session
    _default_session = session
