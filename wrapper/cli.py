"""Command-line REPL engine for the agentic CLI wrapper.

Uses :mod:`litellm` as an API abstraction layer, so the same wrapper
works with Gemini, Claude, GPT-4o, DeepSeek, or local Ollama models —
the only thing that changes is the ``--model`` flag.

Usage::

    python -m wrapper.cli                                  # defaults: . workspace, gemini-2.5-pro
    python -m wrapper.cli /path/to/repo                    # explicit workspace
    python -m wrapper.cli /path/to/repo "build the project"  # one-shot prompt
    python -m wrapper.cli --model gemini/gemini-2.5-pro --yolo

Approval policies can be set at startup with ``-y/--yolo`` or
``--auto-write``, or toggled live during the session by selecting
``[a]lways`` at an approval prompt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import litellm

import litellm.exceptions as litellm_errors

from wrapper.policy import ApprovalPolicy, ExecutionPolicy
from wrapper.tools import (
    TOOL_SCHEMAS,
    get_workspace_root,
    set_policy,
    set_shell_executor,
    set_workspace_root,
)

__all__ = ["main"]


# ---------------------------------------------------------------------------
# Fallback model chain
# ---------------------------------------------------------------------------
# When the primary model fails (auth error, insufficient credits, rate limit),
# try each model in this list in order until one succeeds.
FALLBACK_MODELS: list[str] = [
    "openrouter/deepseek/deepseek-chat",
    "ollama/qwen2.5-coder:7b",
]


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wrapper",
        description=(
            "Python-based agentic CLI wrapper granting LLMs direct read, "
            "write, search, and shell execution access over a local "
            "workspace, with configurable approval policies."
        ),
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Target workspace directory (default: current directory).",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="User prompt. If omitted, reads from stdin (interactive REPL "
        "when stdin is a TTY).",
    )
    parser.add_argument(
        "-m", "--model",
        default="ollama/qwen2.5-coder:7b",
        help="LLM model to use (default: ollama/qwen2.5-coder:7b).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature (default: 0.2).",
    )
    parser.add_argument(
        "-y", "--yolo",
        action="store_true",
        help="Auto-approve all file writes and shell commands.",
    )
    parser.add_argument(
        "--auto-write",
        action="store_true",
        help="Auto-approve file writes; prompt for shell commands.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum tool-calling iterations per turn (default: 20).",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable automatic fallback to alternative models on failure.",
    )
    return parser


# ---------------------------------------------------------------------------
# LiteLLM call wrapper
# ---------------------------------------------------------------------------

def _completion(
    models: list[str],
    messages: list[dict[str, Any]],
    temperature: float,
) -> Any:
    """Call ``litellm.completion`` with automatic model fallback.

    Iterates through *models* in order; the first one that succeeds is used.
    Errors that trigger a fallback: authentication failures, payment required
    (insufficient credits), rate limits, service unavailable, connection errors
    (e.g. Ollama server not running), and model-not-found.
    """
    fallback_error_types = (
        litellm_errors.AuthenticationError,
        litellm_errors.RateLimitError,
        litellm_errors.ServiceUnavailableError,
        litellm_errors.APIConnectionError,
        litellm_errors.NotFoundError,
        litellm_errors.BadGatewayError,
        litellm_errors.InternalServerError,
    )

    for i, model in enumerate(models):
        try:
            return litellm.completion(
                model=model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                temperature=temperature,
            )
        except fallback_error_types as exc:
            if i == len(models) - 1:
                raise
            print(
                f"[wrapper] Model '{model}' failed ({exc}), "
                f"trying fallback models...",
                file=sys.stderr,
            )
        except litellm_errors.APIError as exc:
            if getattr(exc, "status_code", None) in (401, 402, 429, 503):
                if i == len(models) - 1:
                    raise
                print(
                    f"[wrapper] Model '{model}' failed (HTTP {exc.status_code}), "
                    f"trying fallback models...",
                    file=sys.stderr,
                )
            else:
                raise


# ---------------------------------------------------------------------------
# Tool-call resolution loop (per user turn)
# ---------------------------------------------------------------------------

def _resolve_tool_calls(
    models: list[str],
    messages: list[dict[str, Any]],
    temperature: float,
    max_iterations: int,
) -> str:
    """Send messages to the model and resolve any tool calls in a loop.

    Args:
        model: LiteLLM model string.
        messages: Conversation history (mutated in place).
        temperature: Sampling temperature.
        max_iterations: Safety cap on tool-calling iterations.

    Returns:
        The model's final text response.
    """
    from wrapper.tools import dispatch_tool

    final_text = ""

    for _ in range(max_iterations):
        response = _completion(models, messages, temperature)
        message = response.choices[0].message

        # Check for tool calls.
        tool_calls = message.tool_calls
        if tool_calls:
            # Append the assistant's message (with tool calls) to history.
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }
            tc_list = []
            for tc in tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                tc_list.append(tc_dict)
            assistant_msg["tool_calls"] = tc_list
            messages.append(assistant_msg)

            # Execute each tool call and build tool-response messages.
            for tc in tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}

                print(
                    f"[tool] {fn_name}("
                    f"{', '.join(f'{k}={v!r}' for k, v in fn_args.items())}"
                    f")"
                )

                result = dispatch_tool(fn_name, fn_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        # No tool calls → the model produced a final text answer.
        final_text = message.content or "(no text response from model)"
        break
    else:
        final_text = (
            f"ERROR: Reached maximum iterations ({max_iterations}) "
            "without a final response. The task may require a more "
            "specific prompt or a tool error is preventing progress."
        )

    return final_text


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --- Workspace ---
    workspace_path = Path(args.workspace).resolve()
    if not workspace_path.is_dir():
        print(
            f"Error: workspace directory does not exist: {workspace_path}",
            file=sys.stderr,
        )
        return 1

    set_workspace_root(workspace_path)
    root = get_workspace_root()

    # Configure PEEP-backed shell executor for local execution (if available).
    # This does not affect HACKASS/Cloud Run, which imports wrapper.tools
    # without this configuration and uses the default subprocess executor.
    _configure_peep_executor(root)

    # --- API key check ---
    # LiteLLM reads API keys from environment variables automatically.
    api_key_vars = (
        "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY", "GROK_API_KEY", "XAI_API_KEY",
        "OPENROUTER_API_KEY",
    )
    
    # Build the model chain (primary + fallbacks unless --no-fallback).
    if args.no_fallback:
        model_chain: list[str] = [args.model]
    else:
        model_chain = [args.model] + [
            m for m in FALLBACK_MODELS if m not in (args.model,)
        ]
    
    has_key = any(os.environ.get(k) for k in api_key_vars)
    chain_has_ollama = any(_is_ollama_model(m) for m in model_chain)
    if not has_key and not chain_has_ollama:
        print(
            "Error: No API key found in environment variables.\n"
            "  Set one of: GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, "
            "DEEPSEEK_API_KEY, OPENROUTER_API_KEY\n"
            "  (Ollama models like 'ollama/...' do not require an API key.)",
            file=sys.stderr,
        )
        return 1

    # --- Approval policy ---
    policy = ApprovalPolicy()
    policy.update_from_flags(yolo=args.yolo, auto_write=args.auto_write)
    set_policy(policy)

    print(
        f"[wrapper] workspace={root}  model={args.model}  "
        f"fallbacks={model_chain[1:] if len(model_chain) > 1 else 'none'}  "
        f"policy={policy.mode_name}"
    )

    # --- Build initial messages ---
    messages: list[dict[str, Any]] = []

    # --- Determine prompt source ---
    if args.prompt:
        prompt = " ".join(args.prompt)
        _run_turn(args, messages, prompt, policy, model_chain)
        return 0

    # No prompt argument → interactive REPL.
    if not sys.stdin.isatty():
        # Piped input (non-interactive).
        prompt = sys.stdin.read().strip()
        if not prompt:
            print("Error: empty prompt.", file=sys.stderr)
            return 1
        _run_turn(args, messages, prompt, policy, model_chain)
        return 0

    # Full interactive REPL over the current turn.
    print("Entering interactive REPL. Type 'exit' or 'quit' to leave.",
          file=sys.stderr)
    while True:
        try:
            prompt = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt.lower() in ("exit", "quit", "q"):
            break
        if not prompt:
            continue
        _run_turn(args, messages, prompt, policy, model_chain)

    return 0


def _run_turn(
    args: argparse.Namespace,
    messages: list[dict[str, Any]],
    prompt: str,
    policy: ApprovalPolicy,
    model_chain: list[str],
) -> None:
    """Execute a single agent turn: append user message, resolve tools, print."""
    messages.append({"role": "user", "content": prompt})
    result = _resolve_tool_calls(
        models=model_chain,
        messages=messages,
        temperature=args.temperature,
        max_iterations=args.max_iterations,
    )
    print(result)
    print()  # blank line for readability


def _is_ollama_model(model: str) -> bool:
    """Return True if the model string targets a local Ollama endpoint."""
    return model.startswith("ollama/") or model.startswith("ollama;")


def _configure_peep_executor(root: Path) -> None:
    """Configure PEEP-backed shell execution for local CLI use.

    Lazily imports PEEP and the local adapter so that environments without
    PEEP installed (including Cloud Run) continue to use the default
    subprocess executor.
    """
    try:
        from wrapper.peep_shell import PeepShellExecutor
    except ImportError:
        return

    try:
        set_shell_executor(PeepShellExecutor(cwd=str(root)))
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
