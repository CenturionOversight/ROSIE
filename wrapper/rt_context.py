"""Per-turn runtime context for task-level telemetry correlation.

ROSIE assigns a unique ``task_id`` to every agent turn (see
:func:`wrapper.cli._run_turn`).  That id ties all of a turn's shell commands,
PEEP sessions, and RATTER telemetry events together, so a downstream observer
can correlate a single user request with every machine action it caused.

This module stores the *current* turn's ``task_id`` in a
:class:`contextvars.ContextVar`.  Using a ContextVar (rather than a plain
module-global) keeps the value properly scoped to the current execution
context and makes it safe to set and reliably restore even across exceptions
or nested operations.  The CLI sets a token at the start of a turn and always
resets it in a ``finally`` block, so the value reverts to its previous state
(normally ``None``) once the turn is done — there is no persistent task state.

The value is intentionally **not** a model-visible tool argument; it is
telemetry plumbing only.  The PEEP shell executor reads the current
``task_id`` when it enqueues events for RATTER, so the value is captured on the
execution thread before any background worker consumes it.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

__all__ = [
    "get_current_task_id",
    "reset_current_task_id",
    "set_current_task_id",
]

_current_task_id: ContextVar[str | None] = ContextVar("rosie_current_task_id", default=None)


def set_current_task_id(task_id: str) -> Token:
    """Record the *current* turn's ``task_id`` and return its reset token.

    The returned :class:`contextvars.Token` must be passed back to
    :func:`reset_current_task_id` (typically from a ``finally`` block) so the
    context reverts to its previous value once the turn is finished.

    Args:
        task_id: The unique task identifier for the active turn.

    Returns:
        A context token needed to restore the previous value.
    """
    return _current_task_id.set(task_id)


def reset_current_task_id(token: Token) -> None:
    """Restore the previous turn's ``task_id`` after a turn finishes.

    Clearing the context must always happen (also on error paths), which is why
    callers wrap turn bodies in ``try/finally``.  This never raises.
    """
    try:
        _current_task_id.reset(token)
    except (RuntimeError, ValueError, TypeError):
        # Reset can raise RuntimeError when a token is reused out of order. The
        # CLI always resets with the fresh token in a finally, so this is purely
        # defensive — an out-of-order/stale reset must never break the turn.
        pass


def get_current_task_id() -> str | None:
    """Return the current turn's ``task_id``, or ``None`` if not set."""
    return _current_task_id.get()
