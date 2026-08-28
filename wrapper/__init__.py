"""Python-based agentic CLI wrapper for LLMs.

Bridges LLM APIs (via LiteLLM) and a local repository workspace.  Grants
the model direct read, write, search, and shell execution capabilities
with configurable human-in-the-loop approval policies and git diff
previews.

Quick start::

    python -m wrapper.cli /path/to/repo "create a README"
    python -m wrapper.cli --model gemini/gemini-2.5-pro --yolo

Modules:
    policy  — Approval state machine (ask / auto-write / yolo).
    tools   — Local execution handlers + OpenAI-format tool schemas.
    cli     — REPL engine built on LiteLLM.
"""

from wrapper.policy import ApprovalPolicy, ExecutionPolicy
from wrapper.tools import (
    TOOL_MODELS,
    TOOL_REGISTRY,
    TOOL_SCHEMAS,
    dispatch_tool,
    inspect_file,
    inspect_git_status,
    preview_write_file,
    run_shell,
    set_policy,
    set_workspace_root,
    write_file,
)

__all__ = [
    "ApprovalPolicy",
    "ExecutionPolicy",
    "TOOL_MODELS",
    "TOOL_REGISTRY",
    "TOOL_SCHEMAS",
    "dispatch_tool",
    "inspect_file",
    "inspect_git_status",
    "preview_write_file",
    "run_shell",
    "set_policy",
    "set_workspace_root",
    "write_file",
]

__version__ = "2.0.0"
