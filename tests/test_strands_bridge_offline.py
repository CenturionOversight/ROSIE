"""M1B offline verification of the Strands → ROSIE execution seam.

OFFLINE / STUB MODEL — this test uses a deterministic stub Strands Model
instead of Amazon Bedrock.  It proves:

  - Strands agent loop integration (a real ``Agent`` runs the real event loop);
  - ROSIE tool registration with Strands;
  - Strands autonomously selecting the exposed ROSIE tool;
  - delegation into ``wrapper.tools.dispatch_tool(..., runtime=session)``;
  - ``RuntimeSession`` workspace ownership of the real read-only result.

It does NOT prove Bedrock authentication, Bedrock model invocation, AWS IAM
permissions, or live Amazon model behavior — those are covered separately by
``wrapper.aws_preflight`` and ``wrapper.strands_runner`` against real AWS.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

strands = pytest.importorskip("strands")

from strands.agent import Agent  # noqa: E402
from strands.models.model import Model  # noqa: E402

from wrapper.runtime import RuntimeSession  # noqa: E402
from wrapper.strands_bridge import create_rosie_tools, rosie_inspect_git_status  # noqa: E402

TOOL_USE_ID = "m1b-stub-tool-use-1"


class _StubToolUseModel(Model):
    """Deterministic OFFLINE model: turn 1 emits one toolUse, turn 2 answers
    from the toolResult.  The agent loop itself is real Strands."""

    def __init__(self) -> None:
        super().__init__()
        if not hasattr(self, "config"):
            self.config = {}
        self.stream_calls: list[dict[str, Any]] = []

    # --- Model ABC ------------------------------------------------------
    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("not exercised by the M1B offline test")

    async def stream(self, messages, tool_specs, system_prompt, **kwargs):
        self.stream_calls.append(
            {
                "tool_spec_names": [spec.get("name") for spec in (tool_specs or [])],
                "saw_tool_result": any(
                    block.get("toolResult")
                    for msg in messages
                    for block in msg.get("content", [])
                ),
            }
        )

        has_tool_result = self.stream_calls[-1]["saw_tool_result"]
        if not has_tool_result:
            # Turn 1: deterministically select the ROSIE tool.
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "start": {
                        "toolUse": {
                            "toolUseId": TOOL_USE_ID,
                            "name": "rosie_inspect_git_status",
                        }
                    }
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": "{}"}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            # Turn 2: consume the real tool result and answer from it.
            tool_result = next(
                block["toolResult"]
                for msg in messages
                for block in msg.get("content", [])
                if block.get("toolResult")
            )
            status = tool_result.get("status")
            text = ""
            for item in tool_result.get("content", []):
                if isinstance(item, dict) and "text" in item:
                    text = item["text"]
                    break
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockDelta": {
                    "delta": {
                        "text": (
                            "OFFLINE-STUB final answer | "
                            f"toolResult.status={status} | "
                            f"workspace_report={text}"
                        )
                    }
                }
            }
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}


@pytest.fixture
def session(tmp_path):
    """RuntimeSession owning an explicit temporary workspace."""
    root = tmp_path / "m1b_ws"
    root.mkdir()
    session = RuntimeSession(workspace=root)
    yield session
    session.close()


class _ProcStub:
    """Minimal subprocess.CompletedProcess stand-in (repo test convention)."""

    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


_GIT_STATUS_OUT = " M wrapper/tools.py\n?? tests/test_strands_bridge_offline.py\n"


@pytest.fixture
def git_status_stub():
    """Stub the external git binary; ROSIE's execution machinery stays real."""
    proc = _ProcStub(0, stdout=_GIT_STATUS_OUT)
    with patch("wrapper.tools.subprocess.run", return_value=proc) as mocked:
        yield mocked


def _dispatch_spy(monkeypatch, calls):
    """Intercept dispatch_tool at the wrapper.strands_bridge boundary."""
    from wrapper import strands_bridge

    real_dispatch = strands_bridge.dispatch_tool

    def spy(name, args, runtime=None, **kwargs):
        calls.append({"name": name, "args": args, "runtime": runtime})
        return real_dispatch(name, args, runtime=runtime, **kwargs)

    monkeypatch.setattr(strands_bridge, "dispatch_tool", spy)
    return spy


def test_bridge_imports_and_tool_shape(session, git_status_stub):
    """Focused checks 1–2: strands imports; adapter imports; tool shape."""
    from wrapper import strands_bridge  # noqa: F401

    tool = rosie_inspect_git_status(session)
    name = getattr(tool, "tool_name", None) or getattr(tool, "name", "")
    assert name == "rosie_inspect_git_status"
    spec = getattr(tool, "tool_spec", None) or {}
    assert spec.get("name") == "rosie_inspect_git_status"


def test_offline_agent_selects_rosie_tool(session, monkeypatch, git_status_stub):
    """Focused checks 3–6: offline agent loop selects the ROSIE tool, the
    call reaches dispatch_tool(..., runtime=session), and workspace
    ownership is the selected RuntimeSession."""
    workspace = session.workspace_root
    sentinel = workspace / "SENTINEL_ONLY.txt"
    sentinel.write_text("M1B offline marker\n", encoding="utf-8")

    dispatch_calls: list[dict[str, Any]] = []
    _dispatch_spy(monkeypatch, dispatch_calls)

    tools = create_rosie_tools(session)
    assert len(tools) == 1, "M1B must expose exactly one read-only ROSIE tool"

    stub = _StubToolUseModel()
    agent = Agent(
        model=stub,
        tools=tools,
        system_prompt="You are ROSIE's workspace assistant.",
        callback_handler=None,
    )
    result = agent(
        "Inspect the Git status of this workspace and tell me whether it is "
        "clean or has changes."
    )

    # Strands saw the ROSIE tool spec and chose it autonomously (one turn).
    assert stub.stream_calls[0]["tool_spec_names"] == ["rosie_inspect_git_status"]

    # The call reached wrapper.tools.dispatch_tool exactly once.
    assert len(dispatch_calls) == 1
    call = dispatch_calls[0]
    assert call["name"] == "inspect_git_status"
    assert call["args"] == {}

    # The expected RuntimeSession was passed as runtime owner.
    assert call["runtime"] is session
    assert session.has_workspace()
    assert call["runtime"].workspace_root == workspace

    # A real read-only ROSIE result reached the agent's final response.
    final_text = str(result)
    assert "OFFLINE-STUB final answer" in final_text
    assert "toolResult.status=success" in final_text
    assert f"workspace_report={_GIT_STATUS_OUT.strip()}" in final_text

    # Read-only proof: the sentinel file is byte-identical after the run.
    assert sentinel.read_text(encoding="utf-8") == "M1B offline marker\n"


def test_zero_arg_tool_input_is_valid_json(session, git_status_stub):
    """The stub streams '{}'; dispatch must accept zero-arg tool input."""
    from wrapper.tools import dispatch_tool

    out = dispatch_tool("inspect_git_status", {}, runtime=session)
    assert out == _GIT_STATUS_OUT.strip()


def test_non_repo_workspace_error_propagates(session):
    """Without the git stub, ROSIE's truthful not-a-repository error flows
    through dispatch and into the tool result unchanged."""
    from wrapper.tools import dispatch_tool

    out = dispatch_tool("inspect_git_status", {}, runtime=session)
    assert out.startswith("git status failed:")
    assert "not a git repository" in out
