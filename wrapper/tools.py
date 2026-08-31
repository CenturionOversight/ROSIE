"""Local execution handlers and OpenAI-format tool schemas.

Defines twelve core tools — list_directory, search_workspace, inspect_file,
preview_write_file, write_file, apply_patch, move_path, delete_path,
inspect_git_status, inspect_git_diff, inspect_git_log, and run_shell — backed
by :mod:`pathlib`, :mod:`subprocess`, :mod:`difflib`, :mod:`shutil`, and
:mod:`re`.

All file-system operations are constrained to a workspace root set via
:func:`set_workspace_root`.  The :func:`_resolve_safe_path` helper
enforces that user-supplied paths never escape that root.

Pydantic models (:data:`TOOL_MODELS`) validate the argument dictionaries
returned by the model before they are forwarded to the underlying Python
functions.

Approval policies from :mod:`wrapper.policy` are honoured inside
:func:`write_file`, :func:`apply_patch`, and :func:`run_shell` — file writes,
targeted patches, and shell commands are blocked until the user grants
approval (or the policy auto-approves).
"""

from __future__ import annotations

import difflib
import shutil
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
    "apply_patch",
    "inspect_git_status",
    "inspect_git_diff",
    "inspect_git_log",
    "run_shell",
    "move_path",
    "delete_path",
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
    """Default shell executor using subprocess.run.

    Uses the shared :func:`wrapper.output_bounds.format_shell_result` shape so
    the result is bounded and carries an explicit ``TIMED_OUT`` marker.
    """
    from wrapper.output_bounds import format_shell_result

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
        return format_shell_result(
            command,
            stdout=proc.stdout.rstrip(),
            stderr=proc.stderr.rstrip(),
            exit_code=proc.returncode,
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        return format_shell_result(
            command,
            stdout="",
            stderr="",
            exit_code=-1,
            timed_out=True,
            timeout_seconds=timeout,
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


class MovePathArgs(BaseModel):
    """Arguments for :func:`move_path`."""

    source_path: str = Field(
        ...,
        description="Path of the file or directory to move, relative to the workspace root.",
    )
    destination_path: str = Field(
        ...,
        description="Destination path relative to the workspace root. Must not already exist.",
    )

    model_config = {"extra": "forbid"}


class DeletePathArgs(BaseModel):
    """Arguments for :func:`delete_path`."""

    relative_path: str = Field(
        ...,
        description="Path of the file or directory to delete, relative to the workspace root.",
    )
    recursive: bool = Field(
        default=False,
        description="If true and the path is a directory, delete it recursively.",
    )

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
    max_files: int = Field(
        default=5000,
        ge=1,
        description="Maximum number of files to examine before truncating the search (default 5000).",
    )

    model_config = {"extra": "forbid"}


class ApplyPatchArgs(BaseModel):
    """Arguments for :func:`apply_patch`."""

    relative_path: str = Field(
        ...,
        description="Path to the file to edit, relative to the workspace root.",
    )
    old_text: str = Field(
        ...,
        description="The exact text to replace. Must occur exactly once in the file.",
    )
    new_text: str = Field(
        ...,
        description="The replacement text.",
    )

    model_config = {"extra": "forbid"}


class InspectGitDiffArgs(BaseModel):
    """Arguments for :func:`inspect_git_diff`."""

    relative_path: str | None = Field(
        default=None,
        description="Optional path to restrict the diff to, relative to the workspace root.",
    )
    staged: bool = Field(
        default=False,
        description="If true, show the staged diff (git diff --cached) instead of the unstaged diff.",
    )
    max_chars: int = Field(
        default=20000,
        ge=1,
        description="Maximum number of output characters to return (default 20000).",
    )

    model_config = {"extra": "forbid"}


class InspectGitLogArgs(BaseModel):
    """Arguments for :func:`inspect_git_log`."""

    max_entries: int = Field(
        default=10,
        ge=1,
        description="Maximum number of commits to return (default 10).",
    )
    relative_path: str | None = Field(
        default=None,
        description="Optional path to restrict the log to, relative to the workspace root.",
    )

    model_config = {"extra": "forbid"}


#: Mapping of tool name → pydantic model (or ``None`` for no-arg tools).
TOOL_MODELS: dict[str, Optional[type[BaseModel]]] = {
    "list_directory": ListDirectoryArgs,
    "search_workspace": SearchWorkspaceArgs,
    "inspect_file": InspectFileArgs,
    "preview_write_file": PreviewWriteFileArgs,
    "write_file": WriteFileArgs,
    "apply_patch": ApplyPatchArgs,
    "inspect_git_status": None,
    "inspect_git_diff": InspectGitDiffArgs,
    "inspect_git_log": InspectGitLogArgs,
    "run_shell": RunShellArgs,
    "move_path": MovePathArgs,
    "delete_path": DeletePathArgs,
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
    root: Path, relative_path: str, max_files: int
) -> tuple[list[Path], bool]:
    """Collect workspace files under *relative_path*, skipping ignored dirs.

    Scans at most *max_files* files. Returns ``(files, truncated)`` where
    *truncated* is ``True`` when the scan stopped because the budget was
    exhausted before the subtree was fully covered.
    """
    start = _resolve_safe_path(root, relative_path)
    if not start.exists():
        return [], False
    if start.is_file():
        return [start], False
    collected: list[Path] = []
    truncated = False
    for entry in sorted(start.rglob("*")):
        if len(collected) >= max_files:
            truncated = True
            break
        parts = entry.relative_to(root).parts
        if any(part in _IGNORED_DIRS for part in parts):
            continue
        if entry.is_file():
            collected.append(entry)
    return collected, truncated


def search_workspace(
    query: str,
    relative_path: str = ".",
    max_results: int = 50,
    max_files: int = 5000,
) -> str:
    """Searches the workspace for a case-insensitive substring.

    Searches both file names and UTF-8 text contents.  Binary files, files
    larger than 1 MiB, and ignored directories (``.git``, ``node_modules``,
    ``__pycache__``, etc.) are skipped.

    Scanning is budget-bounded: files are examined in deterministic
    (sorted) order until ``max_results`` matches are found, the subtree is
    exhausted, or ``max_files`` files have been examined.  If the file
    budget is exhausted before the subtree is fully covered, a trailing
    ``(search truncated after N files; increase max_files to continue)``
    notice is appended so a partial result is never silently presented as
    exhaustive.

    A file whose PATH matches the query is still content-searched — a
    path-name hit does not suppress content hits from the same file.

    Args:
        query: Case-insensitive substring to search for.
        relative_path: Subdirectory to limit the search to (default entire workspace).
        max_results: Maximum number of results to return.
        max_files: Maximum number of files to examine before truncating.

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
        files, truncated = [start], False
    else:
        files, truncated = _iter_workspace_files(root, relative_path, max_files)

    query_lower = query.lower()
    results: list[str] = []

    for fpath in files:
        if len(results) >= max_results:
            break

        rel = fpath.relative_to(root).as_posix()

        # Path-name hit. Do NOT skip content search — a path match still
        # allows the same file's text to contribute content hits.
        path_hit = query_lower in rel.lower()
        if path_hit:
            results.append(rel)

        # Content search (always examined, even on a path-name hit).
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

    if truncated:
        results.append(
            f"(search truncated after {max_files} files; increase max_files to continue)"
        )

    if not results:
        return f"No results found for '{query}'."
    return "\n".join(results)


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


def apply_patch(relative_path: str, old_text: str, new_text: str) -> str:
    """Apply a small targeted edit to an existing UTF-8 text file.

    ``old_text`` must occur EXACTLY ONCE in the file.  If it matches zero
    times (error, no modification) or more than once (ambiguity error, no
    modification), the file is left untouched.  No fuzzy matching and no
    line-position guessing is performed.

    A unified diff is generated and displayed before the edit.  The same
    approval policy as :func:`write_file` is used; if denied, the file is
    not modified.

    Args:
        relative_path: Path to the file relative to the workspace root.
        old_text: The exact text to replace.
        new_text: The replacement text.

    Returns:
        A concise success or error message.

    Raises:
        PathTraversalError: If the path escapes the workspace root.
    """
    root = get_workspace_root()
    resolved = _resolve_safe_path(root, relative_path)

    if not resolved.is_file():
        return f"ERROR: File '{relative_path}' does not exist."

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"ERROR: File '{relative_path}' appears to be binary and cannot be patched as text."

    count = text.count(old_text)
    if count == 0:
        return (
            f"ERROR: old_text not found in '{relative_path}'. "
            f"File not modified."
        )
    if count > 1:
        return (
            f"ERROR: old_text matches {count} locations in '{relative_path}'. "
            f"Provide a larger/more-specific old_text so it occurs exactly once. "
            f"File not modified."
        )

    new_content = text.replace(old_text, new_text, 1)

    # Generate and display the unified diff.
    diff = preview_write_file(relative_path, new_content)
    print(f"\n[diff preview for {relative_path}]\n{diff}\n{'=' * 60}")

    # Enforce the same approval policy as write_file.
    if _policy is not None:
        approved = _policy.request_approval(
            "write",
            f"Apply patch to '{relative_path}'",
            details=diff,
        )
        if not approved:
            return (
                f"DENIED: Patch to '{relative_path}' was rejected. "
                f"File not modified."
            )

    resolved.write_text(new_content, encoding="utf-8")
    return f"Successfully patched '{relative_path}'."


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


def _run_git(
    argv: list[str], root: Path, timeout: int = 30
) -> str:
    """Run a read-only ``git`` subprocess with a direct argument list.

    Args:
        argv: git arguments (excluding the leading ``git``).
        root: Working directory in which to run git.

    Returns:
        The formatted result, or an ``Error: ...`` message for non-zero
        exits, missing git, or timeouts.
    """
    try:
        proc = subprocess.run(
            ["git", *argv],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return "Error: 'git' is not installed or not on PATH."
    except subprocess.TimeoutExpired:
        return f"Error: git {' '.join(argv[0:2])} timed out after {timeout} seconds."

    if proc.returncode != 0:
        err = proc.stderr.strip()
        if err:
            return f"git {' '.join(argv[0:2])} failed: {err}"
        return f"Error: git {' '.join(argv[0:2])} returned a non-zero exit code."

    return proc.stdout


def inspect_git_diff(
    relative_path: str | None = None,
    staged: bool = False,
    max_chars: int = 20000,
) -> str:
    """Runs a read-only ``git diff`` in the workspace root.

    Without a ``relative_path`` and with ``staged=False`` this is
    ``git diff`` (unstaged). With ``staged=True`` it is ``git diff --cached``.
    When ``relative_path`` is supplied and stays inside the workspace, the
    diff is restricted to that path using ``--``.

    Args:
        relative_path: Optional file/directory to restrict the diff to.
        staged: If True, show the staged diff instead of the unstaged diff.
        max_chars: Maximum number of output characters to return.

    Returns:
        The diff output, a clean no-diff message when empty, or an error
        message.  Truncation is marked explicitly.

    Raises:
        PathTraversalError: If *relative_path* escapes the workspace root.
    """
    root = get_workspace_root()

    argv: list[str] = ["diff"]
    if staged:
        argv.append("--cached")

    if relative_path is not None:
        resolved = _resolve_safe_path(root, relative_path)
        rel = resolved.relative_to(root).as_posix()
        argv.extend(["--", rel])

    output = _run_git(argv, root)
    if output.startswith("Error"):
        return output

    if not output.strip():
        return "No changes to report."

    if len(output) > max_chars:
        output = output[:max_chars]
        output += f"\n...(diff truncated at {max_chars} characters; increase max_chars to see more)"

    return output


def inspect_git_log(
    max_entries: int = 10,
    relative_path: str | None = None,
) -> str:
    """Runs a read-only ``git log`` in the workspace root.

    Uses ``git log --oneline --decorate -n <N>``.  When ``relative_path`` is
    supplied and stays inside the workspace, Git path filtering is applied
    after ``--``.

    Args:
        max_entries: Maximum number of commits to return.
        relative_path: Optional file/directory to restrict the log to.

    Returns:
        The commit history, or an error message.  No mutation occurs.

    Raises:
        PathTraversalError: If *relative_path* escapes the workspace root.
    """
    root = get_workspace_root()

    argv: list[str] = ["log", "--oneline", "--decorate", "-n", str(max_entries)]

    if relative_path is not None:
        resolved = _resolve_safe_path(root, relative_path)
        rel = resolved.relative_to(root).as_posix()
        argv.extend(["--", rel])

    output = _run_git(argv, root)
    if output.startswith("Error"):
        return output

    if not output.strip():
        return "No commits to report."

    return output.rstrip()


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
        result = executor(command, effective_timeout)
        if isinstance(result, str) and result:
            return result
        return str(result)
    except subprocess.TimeoutExpired:
        from wrapper.output_bounds import format_shell_result

        return format_shell_result(
            command,
            stdout="",
            stderr="",
            exit_code=-1,
            timed_out=True,
            timeout_seconds=effective_timeout,
        )


def move_path(source_path: str, destination_path: str) -> str:
    """Move (rename) a file or directory within the workspace.

    The source and destination are both resolved against the workspace root
    and traversal outside it is rejected.  The destination must not already
    exist — this tool never overwrites an existing path.  The move is
    performed with :func:`shutil.move` (no shell is involved).  It is a
    mutation and therefore gated by the same ``write`` approval policy as
    :func:`write_file`.

    Args:
        source_path: Path of the file or directory to move, relative to the
            workspace root.
        destination_path: Destination path relative to the workspace root.
            Must not already exist (including as a non-empty directory).

    Returns:
        A status message, or an error / ``DENIED`` string if the move could
        not proceed.

    Raises:
        PathTraversalError: If either path escapes the workspace root.
    """
    root = get_workspace_root()
    src = _resolve_safe_path(root, source_path)
    dst = _resolve_safe_path(root, destination_path)

    if not src.exists():
        return f"ERROR: Source path '{source_path}' does not exist."
    if dst.exists():
        return (
            f"ERROR: Destination '{destination_path}' already exists. "
            f"move_path never overwrites; choose a different destination."
        )

    if _policy is not None:
        approved = _policy.request_approval(
            "write",
            f"Move '{source_path}' to '{destination_path}'",
            details=f"Rename (filesystem) '{src}' -> '{dst}'",
        )
        if not approved:
            return (
                f"DENIED: Move of '{source_path}' was rejected. "
                f"Nothing was moved."
            )

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"Successfully moved '{source_path}' to '{destination_path}'."


def delete_path(relative_path: str, recursive: bool = False) -> str:
    """Delete a file or directory within the workspace.

    The path is resolved against the workspace root and traversal outside it
    is rejected.  Deleting the workspace root itself (``"."`` or a path that
    resolves to the root) is forbidden.  Files are deleted directly; a
    directory requires ``recursive=True`` and is deleted with
    :func:`shutil.rmtree`.  No shell is involved.  The deletion is a mutation
    and is gated by the same ``write`` approval policy as :func:`write_file`.

    Args:
        relative_path: Path of the file or directory to delete, relative to
            the workspace root.
        recursive: If true and the path is a directory, delete it recursively.

    Returns:
        A status message, or an error / ``DENIED`` string.

    Raises:
        PathTraversalError: If the path escapes the workspace root.
    """
    root = get_workspace_root()
    resolved = _resolve_safe_path(root, relative_path)

    if resolved == root:
        return "ERROR: Refusing to delete the workspace root."

    if not resolved.exists():
        return f"ERROR: Path '{relative_path}' does not exist."

    is_dir = resolved.is_dir()
    if is_dir and not recursive:
        return (
            f"ERROR: '{relative_path}' is a directory. Pass recursive=true "
            f"to delete it and its contents."
        )

    if _policy is not None:
        target_desc = (
            f"directory '{relative_path}' (recursive)"
            if is_dir
            else f"file '{relative_path}'"
        )
        approved = _policy.request_approval(
            "write",
            f"Delete {target_desc}",
            details=f"Filesystem delete of '{resolved}'",
        )
        if not approved:
            return (
                f"DENIED: Delete of '{relative_path}' was rejected. "
                f"Nothing was deleted."
            )

    try:
        if is_dir:
            shutil.rmtree(str(resolved))
        else:
            resolved.unlink()
    except OSError as exc:
        return f"ERROR: Failed to delete '{relative_path}': {exc}"

    return f"Successfully deleted '{relative_path}'."


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
    "apply_patch": apply_patch,
    "inspect_git_status": inspect_git_status,
    "inspect_git_diff": inspect_git_diff,
    "inspect_git_log": inspect_git_log,
    "run_shell": run_shell,
    "move_path": move_path,
    "delete_path": delete_path,
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
