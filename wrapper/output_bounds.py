"""Shared output-bounding for local shell execution results.

Long command/program output can overwhelm a model's context and pollute
per-turn history.  This module provides the single, testable formatter used by
both the PEEP and the subprocess shell executors.  It enforces a **total**
result budget: :data:`DEFAULT_MAX_OUTPUT_CHARS` is the maximum length of the
complete formatted block (command line + headers + both stream payloads +
exit code + any timeout marker), not a per-stream limit.

When the raw output exceeds the budget, the payload budget is split between
stdout and stderr based on their sizes, with a guaranteed minimum share for
each non-empty stream, so neither stream is hidden and stderr stays visible.
Each truncated stream keeps its head and tail with an explicit truncation
marker that reports the original size.  Every structural field (``$ command``,
``STDOUT:``, ``STDERR:``, ``EXIT_CODE:``, ``TIMED_OUT:`` and any timeout error
line) always survives truncation.
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
# Guaranteed minimum share of the payload budget for a non-empty stream, so a
# smaller stream is never starved out entirely by a larger one.
_MIN_PAYLOAD_SHARE = 0.15
_EMPTY_PLACEHOLDER = "(empty)"
_PLACEHOLDER_LEN = len(_EMPTY_PLACEHOLDER)


def _build_marker(original_len: int) -> str:
    """Build the truncation marker, reporting the original payload length."""
    if original_len <= 0:
        return TRUNCATION_MARKER
    return (
        f"...(output truncated; original {original_len} chars; "
        f"showing head and tail)..."
    )


def box_output(
    text: str,
    max_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> str:
    """Bound *text* to at most *max_chars*, keeping head and tail.

    When *text* is at or below *max_chars* it is returned unchanged.  When
    it exceeds the bound, the head (``max_chars * _HEAD_RATIO``) and the
    tail (``max_chars * _TAIL_RATIO``) are retained, separated by an
    explicit truncation marker that reports the original size, so the reader
    keeps both the beginning and the end of the output and is told that
    something was dropped.  The returned string never exceeds *max_chars*.

    Args:
        text: The raw output payload (e.g. accumulated STDOUT or STDERR).
        max_chars: Upper bound on the returned length.  Must be positive; a
            value below a small floor is clamped so a head and tail can both
            be shown.

    Returns:
        The bounded payload, or *text* unchanged when it already fits.
    """
    if max_chars <= 0:
        max_chars = DEFAULT_MAX_OUTPUT_CHARS

    if len(text) <= max_chars:
        return text

    marker = _build_marker(len(text))

    # Reserve the marker plus the two newlines that surround it.
    floor = len(marker) + 4
    if max_chars < floor:
        max_chars = floor

    avail = max_chars - 2 - len(marker)
    head_len = int(avail * _HEAD_RATIO)
    tail_len = avail - head_len
    if tail_len < 1:
        tail_len = 1
        head_len = avail - tail_len
        if head_len < 1:
            head_len = 1
    tail_len = min(tail_len, avail - head_len)
    if tail_len < 1:
        tail_len = 1

    head = text[:head_len]
    tail = text[-tail_len:]
    return f"{head}\n{marker}\n{tail}"


def _allocate_payload_budget(
    available: int,
    stdout_len: int,
    stderr_len: int,
) -> tuple[int, int]:
    """Split *available* payload budget between stdout and stderr.

    Allocation is proportional to stream size with a guaranteed minimum share
    for each non-empty stream, so a smaller stream retains visible content and
    stderr is never hidden by a much larger stdout.
    """
    if available <= 0:
        return (1 if stdout_len > 0 else 0), (1 if stderr_len > 0 else 0)

    if stdout_len > 0 and stderr_len <= 0:
        return available, 0
    if stderr_len > 0 and stdout_len <= 0:
        return 0, available

    min_share = max(1, int(available * _MIN_PAYLOAD_SHARE))

    total = stdout_len + stderr_len
    out_budget = int(available * (stdout_len / total))
    err_budget = available - out_budget

    # Redistribute so each non-empty stream gets at least min_share.
    if err_budget < min_share:
        deficit = min_share - err_budget
        if out_budget - deficit >= 1:
            out_budget -= deficit
            err_budget += deficit
    if out_budget < min_share:
        deficit = min_share - out_budget
        if err_budget - deficit >= 1:
            err_budget -= deficit
            out_budget += deficit

    # Final safety: never go negative.
    if out_budget < 1:
        out_budget = 1
    if err_budget < 1:
        err_budget = 1
    return out_budget, err_budget


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
    inferred from the numeric exit code alone.

    *max_chars* is a **total** budget: the complete returned block never
    exceeds it (apart from an unavoidable tiny tolerance only in the
    pathological case where the structural text alone is larger than
    *max_chars*).  The payload budget left after reserving the structural text
    is shared between stdout and stderr with a guaranteed minimum share for
    each non-empty stream; oversized payloads are truncated head-and-tail with
    an explicit marker reporting their original size.  Every structural field
    always survives.
    """
    if max_chars <= 0:
        max_chars = DEFAULT_MAX_OUTPUT_CHARS

    code = exit_code if exit_code is not None else -1

    timeout_line = ""
    if timed_out:
        timeout_line = (
            f"\nERROR: Command timed out after {int(timeout_seconds)} seconds."
        )

    prefix = f"$ {command}\nSTDOUT:\n"
    middle = "\nSTDERR:\n"
    suffix = (
        f"\nEXIT_CODE: {code}\nTIMED_OUT: {'true' if timed_out else 'false'}"
        f"{timeout_line}"
    )

    stdout_nonempty = bool(stdout)
    stderr_nonempty = bool(stderr)

    # Fixed structural length: headers, command line, exit/timeout lines, plus
    # "(empty)" placeholders for any empty stream.
    fixed = len(prefix) + len(middle) + len(suffix)
    if not stdout_nonempty:
        fixed += _PLACEHOLDER_LEN
    if not stderr_nonempty:
        fixed += _PLACEHOLDER_LEN

    needed = fixed + (len(stdout) if stdout_nonempty else 0) + (
        len(stderr) if stderr_nonempty else 0
    )

    if needed <= max_chars:
        return _assemble(
            prefix, stdout, stdout_nonempty, middle, stderr, stderr_nonempty, suffix
        )

    # Need to truncate.  The structural text must survive, so the payload
    # budget is what is left after reserving it.
    available = max_chars - fixed

    if available <= 0:
        # Pathological: the structural text alone exceeds the budget.  Return
        # the smallest possible representation (empty payloads) rather than
        # dropping the structural fields.  This is the documented unavoidable
        # tolerance.
        return _assemble(prefix, "", False, middle, "", False, suffix)

    out_budget, err_budget = _allocate_payload_budget(
        available,
        len(stdout) if stdout_nonempty else 0,
        len(stderr) if stderr_nonempty else 0,
    )

    bounded_stdout = stdout if not stdout_nonempty else box_output(stdout, out_budget)
    bounded_stderr = stderr if not stderr_nonempty else box_output(stderr, err_budget)

    return _assemble(
        prefix, bounded_stdout, stdout_nonempty, middle, bounded_stderr,
        stderr_nonempty, suffix,
    )


def _assemble(
    prefix: str,
    stdout_payload: str,
    stdout_nonempty: bool,
    middle: str,
    stderr_payload: str,
    stderr_nonempty: bool,
    suffix: str,
) -> str:
    """Assemble the final block from the pre-computed parts."""
    out_text = stdout_payload if stdout_nonempty else _EMPTY_PLACEHOLDER
    err_text = stderr_payload if stderr_nonempty else _EMPTY_PLACEHOLDER
    return f"{prefix}{out_text}{middle}{err_text}{suffix}".strip()
