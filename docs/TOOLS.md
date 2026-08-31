# Tools

ROSIE currently exposes seven model-callable tools. Tool arguments are validated with Pydantic before execution.

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
```

Behavior:

- searches relative file paths and text contents;
- content hits return `path:line:text`;
- path-name hits return the relative path;
- resolves the sub-directory against the workspace root;
- rejects traversal outside the workspace;
- skips binary files, files larger than 1 MiB, and ignored directories
  (`.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`);
- stops at `max_results`.

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

## `inspect_git_status`

Runs:

```bash
git status --short
```

inside the workspace root.

It is read-only from ROSIE's perspective and does not require approval.

Possible results include:

- clean working tree;
- raw short-status output;
- Git unavailable;
- non-repository/error response;
- timeout.

## `run_shell`

Executes an arbitrary shell command with the workspace root as the current working directory.

Arguments:

```text
command: string
timeout: optional integer >= 1
```

Default timeout: 30 seconds.

The result includes:

```text
$ <command>
STDOUT:
...
STDERR:
...
EXIT_CODE: <code>
```

Non-zero exit codes are returned to the model as tool output rather than raised automatically.

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

`dispatch_tool(name, args)` is the central execution entry point. It rejects unknown tools, validates arguments, and invokes the registered function.
