"""ARCHESTRATOR tool bridge for Google ADK.

This module creates thin adapter functions that delegate to the
pre-existing ARCHESTRATOR tool dispatcher (``wrapper.tools.dispatch_tool``).

Each adapter function has type annotations so Google ADK can auto-generate
the JSON schema for the model. The functions themselves do no work — they
forward arguments to ``dispatch_tool`` and return its result.

This preserves the established provenance boundary:
  ARCHESTRATOR (wrapper/) owns the execution logic.
  HACKASS (this package) owns the Google ADK integration.
  The adapters are the seam between them.
"""
from __future__ import annotations

from wrapper.tools import dispatch_tool

__all__ = [
    "create_architect_tools",
    "inspect_file",
    "inspect_git_status",
    "preview_write_file",
    "run_shell",
    "write_file",
]


def inspect_file(relative_path: str, start_line: int = 1, line_count: int = 100) -> str:
    """Read a UTF-8 text file from the workspace with line numbers.

    Args:
        relative_path: Path relative to the workspace root.
        start_line: First line to read (1-indexed, default 1).
        line_count: Maximum lines to read (default 100).

    Returns:
        File content with line-number prefixes, or an error message.
    """
    return dispatch_tool(
        "inspect_file",
        {
            "relative_path": relative_path,
            "start_line": start_line,
            "line_count": line_count,
        },
    )


def preview_write_file(relative_path: str, content: str) -> str:
    """Generate a unified diff for a proposed file write without modifying disk.

    Args:
        relative_path: Path relative to the workspace root.
        content: Proposed file content.

    Returns:
        A unified-diff string, or a "no changes" message.
    """
    return dispatch_tool(
        "preview_write_file",
        {"relative_path": relative_path, "content": content},
    )


def write_file(relative_path: str, content: str) -> str:
    """Write content to a file in the workspace after policy approval.

    Args:
        relative_path: Path relative to the workspace root.
        content: Full text content to write.

    Returns:
        A status message from the ARCHESTRATOR tool layer.
    """
    return dispatch_tool(
        "write_file",
        {"relative_path": relative_path, "content": content},
    )


def inspect_git_status() -> str:
    """Run ``git status --short`` in the workspace root.

    Returns:
        The raw git status output, or an error message.
    """
    return dispatch_tool("inspect_git_status", {})


def run_shell(command: str, timeout: int | None = 30) -> str:
    """Execute a shell command in the workspace after policy approval.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        Formatted output with STDOUT, STDERR, and exit code.
    """
    return dispatch_tool(
        "run_shell",
        {"command": command, "timeout": timeout},
    )


def create_architect_tools():
    """Create Google ADK FunctionTool wrappers for all ARCHESTRATOR tools.

    Returns:
        A list of ``google.adk.tools.FunctionTool`` instances wrapping
        the five ARCHESTRATOR tool adapters.

    Raises:
        ImportError: If ``google.adk`` is not installed.
    """
    from google.adk.tools import FunctionTool

    return [
        FunctionTool(inspect_file),
        FunctionTool(preview_write_file),
        FunctionTool(write_file),
        FunctionTool(inspect_git_status),
        FunctionTool(run_shell),
    ]
