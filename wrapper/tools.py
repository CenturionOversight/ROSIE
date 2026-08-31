"""Local execution handlers and OpenAI-format tool schemas.

Defines seven core tools — list_directory, search_workspace, inspect_file,
preview_write_file, write_file, inspect_git_status, and run_shell — backed
by :mod:`pathlib`, :mod:`subprocess`, :mod:`difflib`, and :mod:`re`.

All file-system operations are constrained to a workspace root set via
:func:`set_workspace_root`.  The :func:`_resolve_safe_path` helper
enforces that user-supplied paths never escape that root.

Pydantic models (:data:`TOOL_MODELS`) validate the argument dictionaries
returned by the model before they are forwarded to the underlying Python
functions.

Approval policies from :mod:`wrapper.policy` are honoured inside
:func:`write_file` and :func:`run_shell` — file writes and shell commands
are blocked until the user grants approval (or the policy auto-approves).
"""

from __future__ import annotations

import difflib
import subprocess
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from wrapper.policy import ApprovalPolicy

__all__ = [
    "PathTraversalError",
    "set_workspace_root",
    "get_workspace_root",
    "set_policy",
    "set_shell_executor",
    "list_directory",
    "search_workspace",
    "inspect_file",
    "preview_write_file",
    "write_file",
    "inspect_git_status",
    "run_shell",
    "TOOL_MODELS",
    "TOOL_REGISTRY",
    "TOOL_SCHEMAS",
    "dispatch_tool",
]


# ---------------------------------------------------------------------------
# Workspace root & policy management
# ---------------------------------------------------------------------------

_workspace_root: Optional[Path] = None
_policy: Optional[ApprovalPolicy] = None
_shell_executor: Any = None


def set_shell_executor(executor: Any) -> None:
    """Set a custom shell executor for :func:`run_shell`.

    The executor must be a callable accepting (command: str, timeout: int)
    and returning a formatted result string. If not set, the default
    :mod:`subprocess`-based executor is used.
    """
    global _shell_executor
    _shell_executor = executor


def _default_shell_executor(command: str, timeout: int) -> str:
    """Default shell executor using subprocess.run (unchanged from original)."""
    root = get_workspace_root()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result_parts = [f"$ {command}"]
        stdout = proc.stdout.rstrip()
        stderr = proc.stderr.rstrip()
        result_parts.append(
            f"STDOUT:\n{stdout}" if stdout else "STDOUT:\n(empty)"
        )
        result_parts.append(
            f"STDERR:\n{stderr}" if stderr else "STDERR:\n(empty)"
        )
        result_parts.append(f"EXIT_CODE: {proc.returncode}")
        return "\n".join(result_parts).strip()
    except subprocess.TimeoutExpired:
        return (
            f"$ {command}\n"
            f"ERROR: Command timed out after {timeout} seconds."
        )


def set_workspace_root(path: str | Path) -> None:
    """Set the workspace root directory for all tool operations."""
    global _workspace_root
    _workspace_root = Path(path).resolve()


def get_workspace_root() -> Path:
    """Return the currently configured workspace root.

    Raises:
        RuntimeError: If :func:`set_workspace_root` has not been called.
    """
    if _workspace_root is None:
        raise RuntimeError(
            "Workspace root has not been set. Call set_workspace_root() first."
        )
    return _workspace_root


def set_policy(policy: ApprovalPolicy) -> None:
    """Inject an :class:`~wrapper.policy.ApprovalPolicy` instance.

    :func:`write_file` and :func:`run_shell` consult this policy before
    mutating state or executing commands.
    """
    global _policy
    _policy = policy


# ---------------------------------------------------------------------------
# Path-safety helper
# ---------------------------------------------------------------------------

class PathTraversalError(Exception):
    """Raised when a user-supplied path resolves outside the workspace root."""


def _resolve_safe_path(workspace_root: Path, user_path: str) -> Path:
    """Resolve *user_path* within *workspace_root*, rejecting traversal.

    The user path is joined to the workspace root and the result is
    canonicalised with :meth:`Path.resolve`.  If the canonical path is
    not a descendant of *workspace_root* a :class:`PathTraversalError`
    is raised.

    Args:
        workspace_root: Already-resolved absolute workspace directory.
        user_path: User-supplied relative path (or ``"."``).

    Returns:
        The fully-resolved, safe :class:`~pathlib.Path`.

    Raises:
        PathTraversalError: When the resolved path escapes the workspace.
    """
    root = workspace_root.resolve()
    target = (root / user_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise PathTraversalError(
            f"Path traversal blocked: '{user_path}' resolves to "
            f"'{target}', which is outside the workspace root '{root}'."
        )
    return target


# ---------------------------------------------------------------------------
# Pydantic argument-validation models
# ---------------------------------------------------------------------------

class InspectFileArgs(BaseModel):
    """Arguments for :func:`inspect_file`."""

    relative_path: str = Field(..., description="Path to the file relative to the workspace root.")
    start_line: int = Field(default=1, ge=1, description="First line to read (1-indexed; default 1).")
    line_count: int = Field(default=100, ge=1, description="Maximum number of lines to read (default 100).")

    model_config = {"extra": "forbid"}


class PreviewWriteFileArgs(BaseModel):
    """Arguments for :func:`preview_write_file`."""

    relative_path: str = Field(..., description="Path to the file relative to the workspace root.")
    content: str = Field(..., description="Proposed file content for comparison.")

    model_config = {"extra": "forbid"}


class WriteFileArgs(BaseModel):
    """Arguments for :func:`write_file`."""

    relative_path: str = Field(..., description="Path to the file relative to the workspace root.")
    content: str = Field(..., description="Full text content to write to the file.")

    model_config = {"extra": "forbid"}


class RunShellArgs(BaseModel):
    """Arguments for :func:`run_shell`."""

    command: str = Field(..., description="Shell command to execute.")
    timeout: Optional[int] = Field(default=None, ge=1, description="Optional timeout in seconds.")

    model_config = {"extra": "forbid"}


class ListDirectoryArgs(BaseModel):
    """Arguments for :func:`list_directory`."""

    relative_path: str = Field(
        default=".",
        description="Path to list relative to the workspace root (default: current directory).",
    )
    recursive: bool = Field(
        default=False,
        description="If true, recursively list all descendants.",
    )
    max_entries: int = Field(
        default=200,
        ge=1,
        description="Maximum number of entries to return (default 200).",
    )

    model_config = {"extra": "forbid"}


class SearchWorkspaceArgs(BaseModel):
    """Arguments for :func:`search_workspace`."""

    query: str = Field(..., description="Case-insensitive substring to search for in file paths and text content.")
    relative_path: str = Field(
        default=".",
        description="Subdirectory to search within, relative to the workspace root (default: entire workspace).",
    )
    max_results: int = Field(
        default=50,
        ge=1,
        description="Maximum number of results to return (default 50).",
    )

    model_config = {"extra": "forbid"}


#: Mapping of tool name → pydantic model (or ``None`` for no-arg tools).
TOOL_MODELS: dict[str, Optional[type[BaseModel]]] = {
    "list_directory": ListDirectoryArgs,
    "search_workspace": SearchWorkspaceArgs,
    "inspect_file": InspectFileArgs,
    "preview_write_file": PreviewWriteFileArgs,
    "write_file": WriteFileArgs,
    "inspect_git_status": None,
    "run_shell": RunShellArgs,
}


# ---------------------------------------------------------------------------
# Core tool functions
# ---------------------------------------------------------------------------

_IGNORED_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
})
_MAX_FILE_SCAN_BYTES = 1024 * 1024  # 1 MiB


def _iter_workspace_files(
    root: Path, relative_path: str, max_results: int
) -> list[Path]:
    """Yield workspace files under *relative_path*, skipping ignored dirs.

    Returns at most *max_results* paths.
    """
    start = _resolve_safe_path(root, relative_path)
    if not start.exists():
        return []
    if start.is_file():
        return [start]
    collected: list[Path] = []
    for entry in sorted(start.rglob("*")):
        if len(collected) >= max_results:
            break
        parts = entry.relative_to(root).parts
        if any(part in _IGNORED_DIRS for part in parts):
            continue
        if entry.is_file():
            collected.append(entry)
    return collected


def list_directory(relative_path: str = ".", recursive: bool = False, max_entries: int = 200) -> str:
    """Lists the contents of a directory within the workspace.

    The path is validated to ensure it stays within the workspace root.
    Directories have a trailing ``/`` appended.  Results are sorted.

    Args:
        relative_path: Path relative to the workspace root (default ``"."``).
        recursive: If ``True``, recursively list all descendants.
        max_entries: Maximum number of entries to return.

    Returns:
        A newline-separated list of workspace-relative paths.

    Raises:
        PathTraversalError: If the path escapes the workspace root.
    """
    root = get_workspace_root()
    resolved = _resolve_safe_path(root, relative_path)

    if not resolved.exists():
        raise FileNotFoundError(f"Path not found: {relative_path}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Not a directory: {relative_path}")

    entries: list[str] = []

    if recursive:
        for entry in sorted(resolved.rglob("*")):
            if len(entries) >= max_entries:
                break
            parts = entry.relative_to(root).parts
            if any(part in _IGNORED_DIRS for part in parts):
                continue
            rel = entry.relative_to(root).as_posix()
            if entry.is_dir():
                entries.append(rel + "/")
            else:
                entries.append(rel)
    else:
        for entry in sorted(resolved.iterdir()):
            if len(entries) >= max_entries:
                break
            parts = entry.relative_to(root).parts
            if any(part in _IGNORED_DIRS for part in parts):
                continue
            rel = entry.relative_to(root).as_posix()
            if entry.is_dir():
                entries.append(rel + "/")
            else:
                entries.append(rel)

    if not entries:
        return "(empty)"
    return "\n".join(entries)


def search_workspace(query: str, relative_path: str = ".", max_results: int = 50) -> str:
    """Searches the workspace for a case-insensitive substring.

    Searches both file names and UTF-8 text contents.  Binary files, files
    larger than 1 MiB, and ignored directories (``.git``, ``node_modules``,
    ``__pycache__``, etc.) are skipped.

    Args:
        query: Case-insensitive substring to search for.
        relative_path: Subdirectory to limit the search to (default entire workspace).
        max_results: Maximum number of results to return.

    Returns:
        A newline-separated list of matches.  Content matches are formatted as
        ``path:line:text``.  Path-name matches show the relative path.

    Raises:
        PathTraversalError: If *relative_path* escapes the workspace root.
    """
    root = get_workspace_root()
    start = _resolve_safe_path(root, relative_path)

    if not start.exists():
        return f"Path not found: {relative_path}"

    if start.is_file():
        files = [start]
    else:
        files = _iter_workspace_files(root, relative_path, max_results * 4)

    query_lower = query.lower()
    results: list[str] = []

    for fpath in files:
        if len(results) >= max_results:
            break

        rel = fpath.relative_to(root).as_posix()

        # Check file name first (path-name hit).
        if query_lower in rel.lower():
            results.append(rel)
            if len(results) >= max_results:
                break
            continue

        # Content search.
        if len(results) >= max_results:
            break
        try:
            raw = fpath.read_bytes()
        except (OSError, PermissionError):
            continue
        if len(raw) > _MAX_FILE_SCAN_BYTES:
            continue
        try:
            text = raw.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if query_lower in line.lower():
                results.append(f"{rel}:{lineno}:{line}")
                if len(results) >= max_results:
                    break

    if not results:
        return f"No results found for '{query}'."
    return "\n".join(results)


def inspect_file(relative_path: str, start_line: int = 1, line_count: int = 100) -> str:
    """Reads a file from the workspace and returns its content with line numbers.

    The path is validated to ensure it stays within the workspace root.

    Args:
        relative_path: Path to the file relative to the workspace root.
        start_line: The first line number to read (1-indexed; default 1).
        line_count: Maximum number of lines to read (default 100).

    Returns:
        The file content prefixed with line numbers, e.g. ``1: line content``.

    Raises:
        PathTraversalError: If the path escapes the workspace root.
        FileNotFoundError: If the file does not exist.
    """
    root = get_workspace_root()
    resolved = _resolve_safe_path(root, relative_path)

    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: File '{relative_path}' appears to be binary and cannot be displayed as text."

    lines = text.splitlines()

    if start_line < 1:
        start_line = 1

    total = len(lines)
    if start_line > total:
        return f"File has {total} line(s). start_line {start_line} is out of range."

    start_idx = start_line - 1
    end_idx = min(start_idx + line_count, total)

    numbered = [
        f"{i + 1}: {lines[i]}" for i in range(start_idx, end_idx)
    ]
    if end_idx < total:
        numbered.append(f"... ({total - end_idx} more line(s))")
    return "\n".join(numbered)


def preview_write_file(relative_path: str, content: str) -> str:
    """Generates a unified diff between the current file and proposed content.

    Does **not** modify disk — it is a read-only preview used to show
    the user what will change before :func:`write_file` commits.

    Args:
        relative_path: Path to the file relative to the workspace root.
        content: The proposed new content.

    Returns:
        A unified-diff string, or a "no changes" message.

    Raises:
        PathTraversalError: If the path escapes the workspace root.
    """
    root = get_workspace_root()
    resolved = _resolve_safe_path(root, relative_path)

    try:
        current = resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = ""
    except UnicodeDecodeError:
        return f"Error: File '{relative_path}' appears to be binary."

    diff_iter = difflib.unified_diff(
        current.splitlines(keepends=True),
        content.splitlines(keepends=True),
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
        n=3,
    )
    diff_text = "".join(diff_iter)
    if not diff_text:
        return f"No changes — the proposed content is identical to the current file."
    return diff_text


def write_file(relative_path: str, content: str) -> str:
    """Writes content to a file, respecting the execution policy.

    A :func:`preview_write_file` diff is generated and displayed.
    In ``ask`` mode the user is prompted for confirmation before
    the write proceeds.  In ``auto-write`` and ``yolo`` modes the
    write is auto-approved.  If denied, the file is **not** modified.

    Args:
        relative_path: Path to the file relative to the workspace root.
        content: The full text content to write.

    Returns:
        A status message.  If denied, an explanatory error string is
        returned so the model can self-correct.

    Raises:
        PathTraversalError: If the path escapes the workspace root.
    """
    root = get_workspace_root()
    resolved = _resolve_safe_path(root, relative_path)

    # Generate and display the diff.
    diff = preview_write_file(relative_path, content)
    print(f"\n[diff preview for {relative_path}]\n{diff}\n{'=' * 60}")

    # Enforce approval policy.
    if _policy is not None:
        approved = _policy.request_approval(
            "write",
            f"Write {len(content.splitlines())} line(s) to '{relative_path}'",
            details=diff,
        )
        if not approved:
            return (
                f"DENIED: Write to '{relative_path}' was rejected. "
                f"File not modified."
            )

    # Persist to disk.
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")

    line_count = len(content.splitlines())
    return f"Successfully wrote {line_count} line(s) to '{relative_path}'."


def inspect_git_status() -> str:
    """Runs ``git status --short`` in the workspace root.

    Returns:
        The raw ``git status --short`` output, or an error message if
        git is unavailable or the directory is not a repository.
    """
    root = get_workspace_root()

    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "Error: 'git' is not installed or not on PATH."
    except subprocess.TimeoutExpired:
        return "Error: git status timed out after 30 seconds."

    if proc.returncode != 0:
        err = proc.stderr.strip()
        if err:
            return f"git status failed: {err}"
        return "Error: git status returned a non-zero exit code."

    output = proc.stdout.strip()
    if not output:
        return "Working tree is clean - no changes to report."
    return output


def run_shell(command: str, timeout: Optional[int] = 30) -> str:
    """Executes a shell command within the workspace directory.

    The approval policy is consulted first: in ``ask`` mode the user
    must confirm; in ``auto-write`` mode the user is still prompted;
    in ``yolo`` mode the command runs immediately.

    After approval, the command is delegated to the configured shell
    executor (see :func:`set_shell_executor`). If no executor is set,
    the default :mod:`subprocess`-based executor is used.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A formatted block with ``$ command``, ``STDOUT:``, ``STDERR:``,
        and ``EXIT_CODE:`` sections.  stderr is never suppressed.
    """
    # Enforce approval policy for shell commands.
    if _policy is not None:
        approved = _policy.request_approval(
            "shell",
            f"Execute shell command: {command}",
            details=f"(timeout: {timeout}s)",
        )
        if not approved:
            return f"DENIED: Shell command '{command}' was rejected by user."

    executor = _shell_executor if _shell_executor is not None else _default_shell_executor
    effective_timeout = timeout if timeout is not None else 30

    try:
        return executor(command, effective_timeout)
    except subprocess.TimeoutExpired:
        return (
            f"$ {command}\n"
            f"ERROR: Command timed out after {effective_timeout} seconds."
        )


# ---------------------------------------------------------------------------
# Tool registry, schemas, and dispatch
# ---------------------------------------------------------------------------

#: Mapping of tool name → executable Python function.
TOOL_REGISTRY: dict[str, Any] = {
    "list_directory": list_directory,
    "search_workspace": search_workspace,
    "inspect_file": inspect_file,
    "preview_write_file": preview_write_file,
    "write_file": write_file,
    "inspect_git_status": inspect_git_status,
    "run_shell": run_shell,
}


def _build_parameter_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Generate an OpenAI-compatible JSON schema from a pydantic model."""
    schema = model_cls.model_json_schema()
    # Remove the auto-generated title; keep type, properties, required.
    schema.pop("title", None)
    return schema


def _build_tool_schema(name: str, func: Any, model_cls: Optional[type[BaseModel]]) -> dict[str, Any]:
    """Build an OpenAI-format tool definition dictionary."""
    description = (func.__doc__ or "").strip()
    if model_cls is not None:
        parameters = _build_parameter_schema(model_cls)
    else:
        parameters = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


#: List of OpenAI-format tool schemas for ``litellm.completion(tools=...)``.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    _build_tool_schema(name, TOOL_REGISTRY[name], TOOL_MODELS[name])
    for name in TOOL_REGISTRY
]


def dispatch_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a tool call with pydantic validation and policy enforcement.

    Args:
        name: The tool (function) name to invoke.
        args: Raw argument dictionary from the model.

    Returns:
        The tool's textual result, or an ``ERROR: …`` string.
    """
    if name not in TOOL_REGISTRY:
        return f"ERROR: Unknown tool '{name}'."

    func = TOOL_REGISTRY[name]
    model_cls = TOOL_MODELS.get(name)

    # Validate arguments with pydantic.
    if model_cls is not None:
        try:
            validated = model_cls(**args)
            call_args = validated.model_dump()
        except Exception as exc:
            return f"ERROR: Argument validation failed for '{name}': {exc}"
    else:
        call_args = args if args else {}

    try:
        result = func(**call_args)
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        return str(result)
    except PathTraversalError as exc:
        return f"ERROR (path violation): {exc}"
    except Exception as exc:
        return f"ERROR ({type(exc).__name__}): {exc}"
