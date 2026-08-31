"""Deterministic conversation-history compaction for the standalone CLI.

This module provides :func:`compact_history`, which trims a list of
OpenAI-format message dicts between user turns — *without* calling an LLM
and *without* any external tokeniser.

Compaction policy
-----------------
1. Leading system messages are always preserved.
2. The currently executing conversation (the most recent user turn +
   everything appended after it) is never touched while its tool loop is
   active.  In practice this means: never compact, keep at least the latest
   completed turn, and keep the active turn intact.
3. Older completed turns are dropped first (newest-retained ordering).
4. Both a *turn count* limit and a *character* limit are enforced.  Whichever
   bites first wins, but at least the most recent completed turn is always
   retained even if it alone exceeds the limits.
"""
from __future__ import annotations

from typing import Any

__all__ = ["compact_history", "count_messages_chars"]

_SYSTEM_ROLES = frozenset({"system", "developer", "system2"})
_TURN_START_ROLES = frozenset({"user", "system", "developer", "system2"})


def count_messages_chars(messages: list[dict[str, Any]]) -> int:
    """Return the total character count of all string fields in *messages*."""
    total = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str):
                        total += len(text)
        # Count tool-call argument strings.
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            args = fn.get("arguments")
            if isinstance(args, str):
                total += len(args)
    return total


def _split_into_turns(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group messages into conversational turns.

    A turn starts at every ``user``, ``system``, ``developer`` message and
    includes all subsequent assistant / tool messages until the next turn
    marker.
    """
    turns: list[list[dict[str, Any]]] = []
    for msg in messages:
        role = msg.get("role", "")
        if role in _TURN_START_ROLES and turns:
            turns.append([])
        if not turns:
            turns.append([])
        turns[-1].append(msg)
    return turns


def compact_history(
    messages: list[dict[str, Any]],
    *,
    max_turns: int = 12,
    max_chars: int = 120_000,
) -> list[dict[str, Any]]:
    """Trim conversation history while preserving turn integrity.

    Args:
        messages: Full conversation history (OpenAI message dicts).
        max_turns: Maximum number of completed turns to retain.
        max_chars: Maximum total characters across retained messages.

    Returns:
        A new list of messages satisfying both limits.  If the full history
        already fits, it is returned unchanged.
    """
    if max_turns <= 0:
        max_turns = 1
    if max_chars <= 0:
        max_chars = 1

    # Fast path: nothing to do if history already fits within both limits.
    turns = _split_into_turns(messages)
    if len(turns) <= max_turns and count_messages_chars(messages) <= max_chars:
        return list(messages)

    # Separate leading system/developer turns (always preserved).
    system_turns: list[list[dict[str, Any]]] = []
    body_turns: list[list[dict[str, Any]]] = []
    for t in turns:
        if t and t[0].get("role") in _SYSTEM_ROLES and not body_turns:
            system_turns.append(t)
        else:
            body_turns.append(t)

    # Enforce turn count limit (drop oldest body turn first).
    while len(body_turns) > max_turns:
        body_turns.pop(0)

    # Enforce character limit among remaining body turns (drop oldest first).
    # Always retain at least the most recent completed turn.
    result: list[dict[str, Any]] = []
    for t in system_turns:
        result.extend(t)

    while body_turns:
        projected = result + [msg for t in body_turns for msg in t]
        if count_messages_chars(projected) <= max_chars:
            result.extend(msg for t in body_turns for msg in t)
            break
        if len(body_turns) <= 1:
            # Can't remove the last turn — always retain it.
            result.extend(body_turns[0])
            break
        body_turns.pop(0)

    return result
