"""Per-turn runtime context for task-level telemetry correlation.

ROSIE assigns a unique ``task_id`` to every agent turn (see
:func:`wrapper.cli._run_turn`).  That id ties all of a turn's shell commands,
PEEP sessions, and RATTER telemetry events together, so a downstream observer
can correlate a single user request with every machine action it caused.

This module provides a lightweight process-global holder for the *current*
turn's ``task_id``.  Reads and writes happen on the single execution thread
(the CLI runs one turn, and within it one tool call, at a time), so a plain
module-level variable is sufficient — no locking or contextvars machinery is
needed.  The value is intentionally **not** a model-visible tool argument; it
is telemetry plumbing only.

The PEEP shell executor reads the current ``task_id`` when it enqueues events
for RATTER, so the value is captured on the execution thread before any
background worker consumes it.
"""

from __future__ import annotations

__all__ = [
    "set_current_task_id",
    "get_current_task_id",
]

_current_task_id: str | None = None


def set_current_task_id(task_id: str) -> None:
    """Set the current turn's ``task_id`` (telemetry only).

    Args:
        task_id: The unique task identifier for the active turn.  A falsy
            value clears the current task context.
    """
    global _current_task_id
    _current_task_id = task_id or None


def get_current_task_id() -> str | None:
    """Return the current turn's ``task_id``, or ``None`` if not set."""
    return _current_task_id
