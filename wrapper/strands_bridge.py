"""Strands → ROSIE tool bridge.

Exposes selected ROSIE tools to the Amazon Strands agent layer.  This module
is the Strands-side counterpart of ``hackass.bridge`` (the Google ADK bridge):
the adapters do no work of their own — every call forwards to the existing
ROSIE execution boundary ``wrapper.tools.dispatch_tool``.

Ownership boundaries:

- The caller constructs a :class:`~wrapper.runtime.RuntimeSession` and owns
  its lifecycle and workspace binding.  This module never touches the legacy
  module-global workspace state.
- Model/provider construction (Bedrock etc.) lives in
  :mod:`wrapper.strands_runner`, not here.  Swapping model providers must not
  require changing ROSIE tool integration.

M1B proved the read-only leg (``inspect_git_status``); M3 adds exactly one
mutating capability: ``write_file``.  Exposed ROSIE tools:

- ``rosie_inspect_git_status`` — read-only Git status of the workspace;
- ``rosie_write_file`` — UTF-8 text write inside the workspace boundary.

Deliberately not bridged: ``run_shell``, ``apply_patch``, ``move_path``,
``delete_path``.
"""
from __future__ import annotations

from typing import Any

from strands.tools.decorator import tool

from wrapper.runtime import RuntimeSession
from wrapper.tools import dispatch_tool

__all__ = ["create_rosie_tools", "rosie_inspect_git_status", "rosie_write_file"]


def rosie_inspect_git_status(session: RuntimeSession):
    """Create a Strands tool that inspects Git status via ROSIE.

    The returned callable is a Strands-decorated tool whose implementation
    delegates to ``wrapper.tools.dispatch_tool("inspect_git_status", ...)``
    with *session* as the runtime owner.  It runs no Git subprocess itself.

    Args:
        session: RuntimeSession owning the workspace to inspect.

    Returns:
        A Strands tool callable.
    """

    @tool(
        name="rosie_inspect_git_status",
        description=(
            "Run 'git status --short' in the ROSIE-managed workspace and "
            "return the raw output, or an error message.  Read-only."
        ),
    )
    def _rosie_inspect_git_status() -> str:
        """Delegate to the ROSIE dispatch boundary under the session."""
        return dispatch_tool(
            "inspect_git_status",
            {},
            runtime=session,
        )

    return _rosie_inspect_git_status


def rosie_write_file(session: RuntimeSession):
    """Create a Strands tool that writes a UTF-8 text file via ROSIE.

    The returned callable is a Strands-decorated tool whose implementation
    delegates to ``wrapper.tools.dispatch_tool("write_file", ...)`` with
    *session* as the runtime owner.  It performs no filesystem operation of
    its own — ROSIE owns path containment, parent-directory creation, and
    the approval policy.

    Args:
        session: RuntimeSession owning the target workspace.

    Returns:
        A Strands tool callable.
    """

    @tool(
        name="rosie_write_file",
        description=(
            "Write UTF-8 text to a file inside the ROSIE-managed workspace. "
            "The path is workspace-relative (e.g. 'notes/summary.txt'); "
            "escaping the workspace is blocked. Parent directories are "
            "created as needed."
        ),
    )
    def _rosie_write_file(relative_path: str, content: str) -> str:
        """Delegate to the ROSIE dispatch boundary under the session."""
        return dispatch_tool(
            "write_file",
            {"relative_path": relative_path, "content": content},
            runtime=session,
        )

    return _rosie_write_file


def create_rosie_tools(session: RuntimeSession) -> list[Any]:
    """Create the M1B ROSIE tool set for a Strands Agent.

    Args:
        session: RuntimeSession owning the selected workspace.

    Returns:
        List of Strands tool callables (read-only Git status + workspace-
        bounded text write).
    """
    return [
        rosie_inspect_git_status(session),
        rosie_write_file(session),
    ]
