# Tools

ROSIE is the local-machine bridge/runtime. This document describes the current **local action surface** it exposes to an attached or standalone reasoning system.

The current runtime exposes ten model-callable local tools. Tool arguments are validated with Pydantic before execution.

These tools do not make ROSIE the HACKASS user interface or the ARCHESTRATOR engineering engine. They are the machine-side capabilities through which authorized work can reach a workspace.

## `list_directory`

Lists the contents of a directory within the workspace.

Arguments:

```text
relative_path: string, default "."
recursive: boolean, default false
max_entries: integer >= 1, default 200
```

Behavior:

- resolves the requested path against the workspace root;
- rejects traversal outside the workspace;
- returns sorted workspace-relative paths;
- appends `/` to directories;
- supports recursive listing when `recursive=true`;
- stops cleanly at `max_entries`.

## `search_workspace`

Searches file names and UTF-8 text contents for a case-insensitive substring.

Arguments:

```text
query: string
relative_path: string, default "."
max_results: integer >= 1, default 50
max_files: integer >= 1, default 5000
```

Behavior:

- searches relative file paths and text contents;
- content hits return `path:line:text`;
- path-name hits return the relative path and do not suppress content hits from the same file;
- resolves the sub-directory against the workspace root;
- rejects traversal outside the workspace;
- skips binary files, files larger than 1 MiB, and ignored directories (`.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`);
- scans in deterministic sorted order;
- stops when `max_results` matches are found, the subtree is exhausted, or `max_files` files have been examined;
- marks truncation explicitly when the file budget is exhausted.

## `inspect_file`

Reads a UTF-8 text file inside the configured workspace and returns numbered lines.

Arguments:

```text
relative_path: string
start_line: integer >= 1, default 1
line_count: integer >= 1, default 100
```

Behavior:

- resolves the requested path against the workspace root;
- rejects traversal outside the workspace;
- returns numbered text lines;
- reports binary files when UTF-8 decoding fails;
- does not modify disk.

## `preview_write_file`

Produces a unified diff between the current file and proposed content.

Arguments:

```text
relative_path: string
content: string
```

Behavior:

- resolves the path against the workspace root;
- rejects traversal outside the workspace;
- treats a missing file as empty content;
- does not write to disk;
- returns a unified diff or a no-change message.

## `write_file`

Creates or overwrites a UTF-8 text file inside the workspace.

Arguments:

```text
relative_path: string
content: string
```

Behavior:

1. validates the path;
2. generates and prints a diff preview;
3. requests approval according to the current execution policy;
4. creates missing parent directories;
5. writes the full supplied content as UTF-8.

Approval behavior is documented in [APPROVAL_MODES.md](APPROVAL_MODES.md).

## `apply_patch`

Applies a small targeted edit to an existing UTF-8 text file without regenerating the whole file.

Arguments:

```text
relative_path: string
old_text: string
new_text: string
```

Behavior:

1. validates the path against the workspace root;
2. requires the file to already exist and be UTF-8 text;
3. requires `old_text` to occur exactly once;
4. uses exact string matching only;
5. generates and displays a unified diff before mutating;
6. requests approval using the same policy as `write_file`;
7. leaves the file unchanged if approval is denied; and
8. replaces only the exact matched text.

## `inspect_git_status`

Runs:

```bash
git status --short
```

inside the workspace root.

It is read-only from ROSIE's local-action perspective and does not require approval.

## `inspect_git_diff`

Shows a diff in the workspace root. Read-only; no approval required.

Arguments:

```text
relative_path: string, optional
staged: boolean, default false
max_chars: integer >= 1, default 20000
```

Behavior:

- uses a direct subprocess argument list;
- runs inside the workspace root;
- supports unstaged and staged diffs;
- validates an optional path before filtering;
- returns stdout;
- surfaces Git errors;
- truncates oversized output explicitly.

## `inspect_git_log`

Shows recent commit history in the workspace root. Read-only; no approval required.

Arguments:

```text
max_entries: integer >= 1, default 10
relative_path: string, optional
```

Behavior:

- uses a direct subprocess argument list;
- runs inside the workspace root;
- returns compact recent history;
- validates optional path filters;
- surfaces Git or non-repository errors;
- never mutates the repository.

## `run_shell`

Executes an arbitrary shell command with the workspace root as the current working directory.

Arguments:

```text
command: string
timeout: optional integer >= 1
```

Default timeout: 30 seconds.

The result includes the command, stdout, stderr, and exit code.

Non-zero exit codes are returned as tool output rather than automatically converted into success.

`run_shell` requires approval except in `yolo` mode.

Important: the workspace directory is the command's starting directory, not a security sandbox. Shell commands can access other paths allowed by the operating system. See [SECURITY.md](SECURITY.md).

## Tool registration

ROSIE defines three related structures in `wrapper/tools.py`:

```text
TOOL_MODELS
TOOL_REGISTRY
TOOL_SCHEMAS
```

`TOOL_MODELS` maps names to Pydantic argument models.

`TOOL_REGISTRY` maps names to executable Python functions.

`TOOL_SCHEMAS` is generated from those definitions for model tool calling.

`dispatch_tool(name, args)` is the central local execution entry point. It rejects unknown tools, validates arguments, and invokes the registered function.

## Architectural use

In standalone mode, a local model can call these tools directly through the ROSIE loop.

In the complete product architecture, higher-level work can arrive from HACKASS through ARCHESTRATOR and be translated into these local capabilities by ROSIE.

The durable boundary is:

```text
ARCHESTRATOR-managed authorized work
  ↓
ROSIE local action surface
  ↓
local machine
```
