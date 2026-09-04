"""Python-based agentic CLI wrapper for LLMs.

Bridges LLM APIs (via LiteLLM) and a local repository workspace.  Grants
the model direct read, write, search, and shell execution capabilities
with configurable human-in-the-loop approval policies and git diff
previews.

Quick start::

    python -m wrapper.cli /path/to/repo "create a README"
    python -m wrapper.cli --model gemini/gemini-2.5-pro --yolo

Modules:
    policy         — Approval state machine (ask / auto-write / yolo).
    tools          — Local execution handlers + OpenAI-format tool schemas.
    context        — Deterministic conversation-history compaction.
    system_prompt  — The ROSIE operating system prompt.
    cli            — REPL engine built on LiteLLM.
    ratter_core    — In-process RATTER operational record (ingress, sessions,
                     timeline, integrity).
    scratch        — Persistent `$SCRATCH` workspace (structured JSON pads
                     and append-only JSONL pads).
"""

from wrapper.policy import ApprovalPolicy, ExecutionPolicy
from wrapper.system_prompt import ROSIE_SYSTEM_PROMPT
from wrapper.tools import (
    TOOL_MODELS,
    TOOL_REGISTRY,
    TOOL_SCHEMAS,
    apply_patch,
    delete_path,
    dispatch_tool,
    inspect_file,
    inspect_git_diff,
    inspect_git_log,
    inspect_git_status,
    list_directory,
    move_path,
    preview_write_file,
    run_shell,
    search_workspace,
    set_policy,
    set_workspace_root,
    write_file,
)

__all__ = [
    "ROSIE_SYSTEM_PROMPT",
    "TOOL_MODELS",
    "TOOL_REGISTRY",
    "TOOL_SCHEMAS",
    "ApprovalPolicy",
    "ExecutionPolicy",
    "apply_patch",
    "delete_path",
    "dispatch_tool",
    "inspect_file",
    "inspect_git_diff",
    "inspect_git_log",
    "inspect_git_status",
    "list_directory",
    "move_path",
    "preview_write_file",
    "run_shell",
    "search_workspace",
    "set_policy",
    "set_workspace_root",
    "write_file",
]

__version__ = "2.0.0"
