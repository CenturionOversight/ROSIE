"""M5 offline verification: Strands-backed local workspace verification.

OFFLINE / STUB MODEL — deterministic stub Strands model, real Agent loop,
real ROSIE dispatch boundary.  Proves the new seam only:

  - the verification adapter binds RuntimeSession to the DELIVERED workspace;
  - the agent selects the exposed ROSIE capability (real Strands event loop);
  - ROSIE's dispatch boundary executes and real stdout/exit code are parsed;
  - failures name their stage truthfully (no fabricated success);
  - a failing verification does not modify or erase delivered files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

strands = pytest.importorskip("strands")

from strands.agent import Agent  # noqa: E402
from strands.models.model import Model  # noqa: E402

from wrapper.strands_verify import (  # noqa: E402
    DEFAULT_PROOF_FILENAME,
    run_strands_verification,
)

TOOL_USE_ID = "m5-stub-tool-use-1"
PROOF_STDOUT = "HACKASS_STRANDS_ROSIE_PROVEN"


class _ShellStubModel(Model):
    """Turn 1: select rosie_run_shell on the delivered proof program.

    Turn 2: consume the real tool result and answer from it. The agent
    loop is the real Strands event loop; only the model is stubbed.
    """

    def __init__(self, command: str) -> None:
        super().__init__()
        if not hasattr(self, "config"):
            self.config = {}
        self.command = command
        self.stream_calls = 0

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("not exercised by the M5 offline test")

    async def stream(self, messages, tool_specs, system_prompt, **kwargs):
        self.stream_calls += 1
        has_tool_result = any(
            block.get("toolResult")
            for msg in messages
            for block in msg.get("content", [])
        )
        if self.stream_calls == 1:
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {
                        "toolUseId": TOOL_USE_ID,
                        "name": "rosie_run_shell",
                    }}
                }
            }
            yield {
                "contentBlockDelta": {"delta": {"toolUse": {
                    "input": json.dumps({"command": self.command})}}}
            }
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return
        tool_result = next(
            block["toolResult"]
            for msg in messages
            for block in msg.get("content", [])
            if block.get("toolResult")
        )
        text = ""
        for item in tool_result.get("content", []):
            if isinstance(item, dict) and "text" in item:
                text = item["text"]
                break
        yield {"messageStart": {"role": "assistant"}}
        yield {
            "contentBlockDelta": {"delta": {"text": f"result: {text[:120]}"}}
        }
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class _NoRosieStubModel(_ShellStubModel):
    """Turn 1 selects no tool and answers directly — wrong-behavior case."""

    async def stream(self, messages, tool_specs, system_prompt, **kwargs):
        self.stream_calls += 1
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": "all good, trust me"}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


def _factory(model: Model):
    """Factory whose session runs under ROSIE's own ``yolo_policy`` test
    convention (see tests/test_tools.py): the adapter seam under test is
    the execution boundary, not the approval state machine, which ROSIE
    tests separately. Live callers keep the real policy — auto-write
    prompts for shell at the local console, and that boundary is
    exercised by the live M5 product run, not by offline tests.
    """
    from wrapper.policy import ApprovalPolicy, ExecutionPolicy
    from wrapper.strands_bridge import create_rosie_tools

    def _make(session, model_id, region):
        session.set_policy(ApprovalPolicy(ExecutionPolicy.YOLO))
        return Agent(model=model, tools=create_rosie_tools(session))
    return _make


def _delivered_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "delivered"
    ws.mkdir()
    (ws / DEFAULT_PROOF_FILENAME).write_text(
        "print(\"HACKASS_STRANDS_ROSIE_PROVEN\")\n", encoding="utf-8")
    (ws / "artifact.txt").write_text("delivered bytes\n", encoding="utf-8")
    return ws


class TestStrandsVerifyAdapter:
    def test_pass_parses_real_stdout_and_exit(
            self, monkeypatch, tmp_path):
        ws = _delivered_workspace(tmp_path)
        model = _ShellStubModel(f'python {DEFAULT_PROOF_FILENAME}')
        result = run_strands_verification(
            ws, agent_factory=_factory(model), timeout_s=60)
        assert result["status"] == "PASSED"
        assert result["stage"] == "execution"
        assert PROOF_STDOUT in result["stdout"]
        assert result["exit_code"] == 0
        assert result["selected_tools"], "tool-selection evidence present"
        names = {t["name"] for t in result["selected_tools"]}
        assert "rosie_run_shell" in names
        assert result["model_id"] == "us.amazon.nova-micro-v1:0"

    def test_runtime_session_bound_to_delivered_workspace(
            self, monkeypatch, tmp_path):
        ws = _delivered_workspace(tmp_path)
        model = _ShellStubModel(f'python {DEFAULT_PROOF_FILENAME}')
        seen = {}

        def factory(session, model_id, region):
            seen["workspace"] = str(session.workspace_root)
            return Agent(model=model, tools=create_rosie_tools(session))

        run_strands_verification(ws, agent_factory=factory, timeout_s=60)
        assert seen["workspace"] == str(ws.resolve())

    def test_missing_workspace_fails_at_runtime_stage(self, tmp_path):
        result = run_strands_verification(
            tmp_path / "nope", agent_factory=lambda *a, **k: None)
        assert result["status"] == "FAILED"
        assert result["stage"] == "runtime"

    def test_no_rosie_tool_selected_fails_truthfully(
            self, monkeypatch, tmp_path):
        ws = _delivered_workspace(tmp_path)
        model = _NoRosieStubModel("ignored")
        result = run_strands_verification(
            ws, agent_factory=_factory(model), timeout_s=60)
        assert result["status"] == "FAILED"
        assert result["stage"] == "tool_selection"
        assert "no ROSIE capability" in result["detail"]

    def test_nonzero_exit_is_truthful_failure_not_success(
            self, monkeypatch, tmp_path):
        ws = _delivered_workspace(tmp_path)
        # A delivered program that exits 3: real subprocess, real exit code.
        (ws / DEFAULT_PROOF_FILENAME).write_text(
            "import sys\nprint('HACKASS_STRANDS_ROSIE_PROVEN')\nsys.exit(3)\n",
            encoding="utf-8")
        model = _ShellStubModel(f'python {DEFAULT_PROOF_FILENAME}')
        result = run_strands_verification(
            ws, agent_factory=_factory(model), timeout_s=60)
        assert result["status"] == "FAILED"
        assert result["exit_code"] == 3
        assert "exit 3" in result["detail"]

    def test_failed_verification_leaves_delivered_files_intact(
            self, monkeypatch, tmp_path):
        ws = _delivered_workspace(tmp_path)
        (ws / DEFAULT_PROOF_FILENAME).write_text(
            "import sys\nsys.exit(5)\n", encoding="utf-8")
        before = {
            p.name: p.read_bytes() for p in ws.iterdir() if p.is_file()}
        model = _ShellStubModel(f'python {DEFAULT_PROOF_FILENAME}')
        result = run_strands_verification(
            ws, agent_factory=_factory(model), timeout_s=60)
        assert result["status"] == "FAILED"
        after = {
            p.name: p.read_bytes() for p in ws.iterdir() if p.is_file()}
        assert before == after, "verification failure must not touch delivery"

    def test_agent_build_failure_names_stage(self, tmp_path):
        def boom(session, model_id, region):
            raise RuntimeError("bedrock down")

        result = run_strands_verification(
            _delivered_workspace(tmp_path), agent_factory=boom)
        assert result["status"] == "FAILED"
        assert result["stage"] == "agent_build"
        assert "bedrock down" in result["detail"]
