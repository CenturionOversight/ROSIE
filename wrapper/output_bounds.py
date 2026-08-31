"""Shared output-bounding for local shell execution results.

Long command/program output can overwhelm a model's context and pollute
per-turn history.  This module provides a single, testable helper that
truncates oversized output while preserving a useful head, a useful tail,
and an explicit truncation marker so a bounded result is never silently
presented as complete.

The bound applies to the *payload* sections (STDOUT / STDERR) of a shell
result.  The structural lines (``$ command``, ``STDOUT:``, ``STDERR:``,
``EXIT_CODE:``, and any ``TIMED_OUT`` marker) are preserved by the callers
in :mod:`wrapper.peep_shell` and :mod:`wrapper.tools` so a bounded result
still exposes every contract field the model relies on.
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_MAX_OUTPUT_CHARS",
    "TRUNCATION_MARKER",
    "box_output",
    "format_shell_result",
]


DEFAULT_MAX_OUTPUT_CHARS = 50_000
TRUNCATION_MARKER = "...(output truncated; showing head and tail)..."
_HEAD_RATIO = 0.6
_TAIL_RATIO = 0.4


def box_output(
    text: str,
    max_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> str:
    """Bound *text* to roughly *max_chars*, keeping head and tail.

    When *text* is at or below *max_chars* it is returned unchanged.  When
    it exceeds the bound, the head (``max_chars * _HEAD_RATIO``) and the
    tail (``max_chars * _TAIL_RATIO``) are retained, separated by an
    explicit truncation marker, so the reader keeps both the beginning and
    the end of the output and is told that something was dropped.

    Args:
        text: The raw output payload (e.g. accumulated STDOUT or STDERR).
        max_chars: Upper bound on the returned length.  Must be positive; a
            value below a small floor is clamped to a sensible minimum so a
            head and tail can both be shown.

    Returns:
        The bounded payload, or *text* unchanged when it already fits.
    """
    if max_chars <= 0:
        max_chars = DEFAULT_MAX_OUTPUT_CHARS

    if len(text) <= max_chars:
        return text

    floor = len(TRUNCATION_MARKER) + 8
    if max_chars < floor:
        max_chars = floor

    # Reserve 2 chars for the newlines that join head/marker/tail so the
    # returned string never exceeds max_chars.
    avail = max_chars - 2
    head_len = int(avail * _HEAD_RATIO)
    tail_len = avail - head_len - len(TRUNCATION_MARKER)
    if tail_len < 1:
        tail_len = 1
        head_len = avail - tail_len - len(TRUNCATION_MARKER)
        if head_len < 1:
            head_len = 1
    tail_len = min(tail_len, avail - head_len - len(TRUNCATION_MARKER))
    if tail_len < 1:
        tail_len = 1

    head = text[:head_len]
    tail = text[-tail_len:]
    return f"{head}\n{TRUNCATION_MARKER}\n{tail}"


def format_shell_result(
    command: str,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None,
    timed_out: bool = False,
    timeout_seconds: int | float = 30,
    max_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> str:
    """Build the shared, bounded shell-executor result block.

    Produces the single canonical result shape returned by both the PEEP and
    the subprocess shell executors:

    .. code-block:: text

        $ <command>
        STDOUT:
        <stdout or (empty)>
        STDERR:
        <stderr or (empty)>
        EXIT_CODE: <code>
        TIMED_OUT: true|false

    When *timed_out* is ``True`` an explicit
    ``ERROR: Command timed out after <timeout_seconds> seconds.`` notice is
    appended and *exit_code* is reported as ``-1`` so the timeout is never
    inferred from the numeric exit code alone.  Long STDOUT and STDERR
    payloads are bounded with :func:`box_output` while every structural
    marker is preserved.
    """
    bounded_stdout = box_output(stdout, max_chars=max_chars)
    bounded_stderr = box_output(stderr, max_chars=max_chars)

    parts = [f"$ {command}"]
    parts.append(
        f"STDOUT:\n{bounded_stdout}" if bounded_stdout else "STDOUT:\n(empty)"
    )
    parts.append(
        f"STDERR:\n{bounded_stderr}" if bounded_stderr else "STDERR:\n(empty)"
    )
    parts.append(f"EXIT_CODE: {exit_code if exit_code is not None else -1}")
    parts.append(f"TIMED_OUT: {'true' if timed_out else 'false'}")
    if timed_out:
        parts.append(
            f"ERROR: Command timed out after {int(timeout_seconds)} seconds."
        )
    return "\n".join(parts).strip()
