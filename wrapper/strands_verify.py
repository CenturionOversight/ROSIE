"""Strands-backed local verification of a delivered workspace (M5).

One reusable ROSIE entry point: bind a :class:`~wrapper.runtime.RuntimeSession`
to the *delivered* workspace, run ONE real Amazon Strands agent turn
(Bedrock / Nova Micro), let the model select the exposed ROSIE capabilities,
and return a bounded, truthful result dictionary.

Ownership boundaries:

- The caller (the ROSIE local bridge) owns when verification runs; this
  module owns the agent turn. The delivered artifact is never modified
  here — the model is instructed to execute, not rewrite, and the only
  bridged mutating capability carries ROSIE's real approval policy.
- No mock or fallback provider: Bedrock unavailability is a truthful
  FAILED result, never a synthetic success.
- The result reports real stdout/stderr/exit code parsed from the ROSIE
  shell tool result blocks, plus the tool-selection evidence from the
  Strands event-loop metrics. Nothing is invented.

This module is offline-testable: pass ``agent_factory`` to substitute a
fake agent (no Amazon call). Live runs use the default real factory.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Callable

from wrapper.runtime import RuntimeSession
from wrapper.policy import ApprovalPolicy, ExecutionPolicy
from wrapper.strands_bridge import create_rosie_tools

__all__ = [
    "DEFAULT_MODEL_ID",
    "DEFAULT_PROOF_FILENAME",
    "VERIFY_SYSTEM_PROMPT_TEMPLATE",
    "VERIFY_PROMPT_TEMPLATE",
    "run_strands_verification",
]

DEFAULT_MODEL_ID = "us.amazon.nova-micro-v1:0"
DEFAULT_PROOF_FILENAME = "m5_hackass_proof.py"
DEFAULT_TIMEOUT_S = 180.0
_MAX_EVIDENCE_CHARS = 2000

VERIFY_SYSTEM_PROMPT_TEMPLATE = (
    "You are ROSIE's local build-verification agent. The workspace contains "
    "a freshly delivered build. Your only job: locate the delivered "
    "verification program '{filename}' within the workspace (it may sit in "
    "a subdirectory such as dist/), execute it with the workspace Python "
    "interpreter using the rosie_run_shell tool, and report the real "
    "stdout and exit code. Do NOT create, modify, or delete any files. "
    "If you cannot find the program, say so plainly."
)

VERIFY_PROMPT_TEMPLATE = (
    "Locate the delivered verification program '{filename}' in this "
    "workspace, execute it, and return its real stdout and exit code."
)


def _clip(text: str, limit: int = _MAX_EVIDENCE_CHARS) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[clipped {len(text) - limit} chars]"


def _default_agent_factory(session: RuntimeSession, model_id: str,
                           region: str | None) -> Any:
    """Real Amazon-backed agent construction (isolated provider wiring)."""
    from strands import Agent
    from strands.models import BedrockModel

    model = BedrockModel(model_id=model_id, region_name=region)
    return Agent(
        model=model,
        tools=create_rosie_tools(session),
        system_prompt=VERIFY_SYSTEM_PROMPT_TEMPLATE.format(
            filename=DEFAULT_PROOF_FILENAME),
    )


def _tool_results_from_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Extract toolResult blocks from the agent transcript."""
    blocks: list[dict[str, Any]] = []
    for message in messages or []:
        data = message if isinstance(message, dict) else getattr(
            message, "model_dump", lambda: {})()
        for content in (data or {}).get("content") or []:
            if isinstance(content, dict) and "toolResult" in content:
                blocks.append(content["toolResult"] or {})
    return blocks


def _parse_shell_block(text: str) -> dict[str, Any]:
    """Parse the canonical ROSIE shell-result block into real evidence."""
    parsed: dict[str, Any] = {
        "command": "", "stdout": "", "stderr": "",
        "exit_code": None, "timed_out": False,
    }
    if not isinstance(text, str) or not text:
        return parsed
    lines = text.splitlines()
    for line in lines:
        if line.startswith("$ "):
            parsed["command"] = line[2:].strip()
            break
    def _section(start: str, end: str) -> str:
        try:
            head = lines.index(start) + 1
        except ValueError:
            return ""
        tail = len(lines)
        if end in lines:
            tail = lines.index(end, head)
        return "\n".join(lines[head:tail]).strip()
    parsed["stdout"] = _section("STDOUT:", "STDERR:")
    parsed["stderr"] = _section("STDERR:", "EXIT_CODE:")
    match = re.search(r"EXIT_CODE:\s*(-?\d+)", text)
    if match:
        parsed["exit_code"] = int(match.group(1))
    parsed["timed_out"] = bool(re.search(r"TIMED_OUT:\s*true", text))
    return parsed


def _selected_tools(metrics: Any) -> list[dict[str, Any]]:
    """Tool-selection evidence from the Strands event-loop metrics."""
    try:
        summary = metrics.get_summary()
    except Exception:
        return []
    selected: list[dict[str, Any]] = []
    for name, usage in (summary.get("tool_usage") or {}).items():
        stats = (usage or {}).get("execution_stats") or {}
        selected.append({
            "name": str((usage or {}).get("tool_info", {}).get("name", name)),
            "input": (usage or {}).get("tool_info", {}).get("input_params"),
            "call_count": int(stats.get("call_count") or 0),
            "error_count": int(stats.get("error_count") or 0),
        })
    return selected


def _failed(stage: str, detail: str, **extra: Any) -> dict[str, Any]:
    result = {
        "status": "FAILED",
        "stage": stage,
        "detail": _clip(detail),
        "model_id": extra.pop("model_id", ""),
        "selected_tools": extra.pop("selected_tools", []),
        "stdout": extra.pop("stdout", ""),
        "stderr": extra.pop("stderr", ""),
        "exit_code": extra.pop("exit_code", None),
        "stop_reason": extra.pop("stop_reason", ""),
    }
    result.update(extra)
    return result


def run_strands_verification(
    workspace: str | Path,
    *,
    policy_name: str = "auto-write",
    expected_stdout: str = "HACKASS_STRANDS_ROSIE_PROVEN",
    proof_filename: str = DEFAULT_PROOF_FILENAME,
    model_id: str = DEFAULT_MODEL_ID,
    region: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    agent_factory: Callable[..., Any] | None = None,
    shell_executor: Any = None,
) -> dict[str, Any]:
    """Run one Strands/Nova verification turn against *workspace*.

    ``shell_executor`` is a test seam only (ROSIE's established
    ``RuntimeSession(shell_executor=...)`` pattern); live callers never
    pass it, so the session's default executor runs and the real approval
    policy governs every shell command.

    Returns a bounded dictionary (never raises): ``status`` PASSED only
    when the selected ROSIE shell execution really produced *expected_stdout*
    with exit code 0. Any failure is truthful and names its stage.
    """
    factory = agent_factory or _default_agent_factory
    workspace_path = Path(workspace).resolve()
    if not workspace_path.is_dir():
        return _failed("runtime", f"workspace does not exist: {workspace_path}")

    session = RuntimeSession(
        workspace=workspace_path,
        policy=ApprovalPolicy(ExecutionPolicy(policy_name)),
        shell_executor=shell_executor,
    )
    cancel = threading.Event()
    watchdog: threading.Timer | None = None
    try:
        try:
            agent = factory(session, model_id, region)
        except Exception as exc:
            return _failed("agent_build",
                           f"{type(exc).__name__}: {exc}",
                           model_id=model_id)
        if watchdog is None and timeout_s and timeout_s > 0:
            watchdog = threading.Timer(timeout_s, cancel.set)
            watchdog.daemon = True
            watchdog.start()
        try:
            result = agent(
                VERIFY_PROMPT_TEMPLATE.format(filename=proof_filename),
                cancel_signal=cancel,
            )
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            if cancel.is_set():
                detail = f"verification timed out after {timeout_s:.0f}s"
            return _failed("model_invocation", detail, model_id=model_id)

        selected = _selected_tools(getattr(result, "metrics", None))
        stop_reason = str(getattr(result, "stop_reason", "") or "")
        # The AgentResult carries only the final message; the full
        # transcript (with toolResult blocks) lives on the agent.
        transcript = (getattr(agent, "messages", None)
                      or getattr(result, "messages", None) or [])
        tool_results = _tool_results_from_messages(transcript)

        if not any(t["name"].startswith("rosie_") for t in selected):
            return _failed(
                "tool_selection",
                "agent selected no ROSIE capability",
                model_id=model_id, selected_tools=selected,
                stop_reason=stop_reason)

        shell_blocks = []
        for block in tool_results:
            for content in block.get("content") or []:
                text = content.get("text", "") if isinstance(content, dict) else ""
                if "EXIT_CODE:" in text:
                    shell_blocks.append(_parse_shell_block(text))
        if not shell_blocks:
            return _failed(
                "execution",
                "agent ran no ROSIE shell command",
                model_id=model_id, selected_tools=selected,
                stop_reason=stop_reason)

        # The decisive execution is the last shell result.
        executed = shell_blocks[-1]
        stdout = _clip(executed["stdout"])
        stderr = _clip(executed["stderr"])
        exit_code = executed["exit_code"]
        passed = (expected_stdout in (executed["stdout"] or "")
                  and exit_code == 0 and not executed["timed_out"])
        detail = (
            f"executed: {executed['command']}"
            if passed else
            f"expected '{expected_stdout}' with exit code 0; got "
            f"exit {exit_code}, stdout: {_clip(executed['stdout'], 300)!r}"
            + (f"; stderr: {_clip(executed['stderr'], 300)!r}" if stderr else "")
            + ("; TIMED_OUT" if executed["timed_out"] else ""))
        return {
            "status": "PASSED" if passed else "FAILED",
            "stage": "execution",
            "detail": detail,
            "model_id": model_id,
            "selected_tools": selected,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "stop_reason": stop_reason,
        }
    finally:
        if watchdog is not None:
            watchdog.cancel()
        try:
            session.close()
        except Exception:
            pass
