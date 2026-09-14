"""One-command live proof: Strands → Bedrock Nova Micro → ROSIE ``write_file``.

M3 companion to :mod:`wrapper.strands_runner` (the M1/M2 read-only proof).
Assembles the same separately-owned parts — ``RuntimeSession`` workspace
ownership, ``wrapper.strands_bridge`` tool exposure, isolated Bedrock model
wiring — but issues one deterministic natural-language WRITE instruction so
the proof ends with ROSIE creating a real file on the local disk.

Default workspace is ``D:\\ROSIE_STRANDS_TEST`` (the established Strands test
boundary) so the proof never mutates the ROSIE source tree.  The session uses
ROSIE's documented non-interactive write policy (``auto-write``): file writes
are auto-approved while shell commands would still require approval — and no
shell tool is exposed to the agent anyway.
"""
from __future__ import annotations

import sys
from pathlib import Path

from wrapper.policy import ApprovalPolicy
from wrapper.runtime import RuntimeSession
from wrapper.strands_bridge import create_rosie_tools

__all__ = ["DEFAULT_WORKSPACE", "M3_PROMPT", "PROOF_RELATIVE_PATH", "main"]

DEFAULT_WORKSPACE = Path(r"D:\ROSIE_STRANDS_TEST")

PROOF_RELATIVE_PATH = "m3_rosie_write_proof.txt"

M3_PROMPT = (
    f"Create a file named {PROOF_RELATIVE_PATH} in this workspace "
    "containing exactly ROSIE_LOCAL_WRITE_PROVEN."
)


def main(argv: list[str] | None = None) -> int:
    """Run the real M3 agent turn against the selected workspace."""
    argv = list(sys.argv[1:] if argv is None else argv)

    workspace = Path(argv[0]).resolve() if argv else DEFAULT_WORKSPACE
    if not workspace.is_dir():
        print(f"ERROR: workspace does not exist: {workspace}")
        return 2

    # 1. Workspace ownership — explicit RuntimeSession, no global state.
    policy = ApprovalPolicy()
    policy.update_from_flags(auto_write=True)
    session = RuntimeSession(workspace=workspace, policy=policy)

    # 2. Existing ROSIE tools via the adapter.
    rosie_tools = create_rosie_tools(session)

    # 3. Real Amazon-backed model (isolated provider construction).
    from strands.models import BedrockModel

    model = BedrockModel(
        model_id="us.amazon.nova-micro-v1:0",
    )

    # 4. Real Strands agent.
    from strands import Agent

    agent = Agent(
        model=model,
        tools=rosie_tools,
        system_prompt=(
            "You are ROSIE's workspace assistant. Use the provided ROSIE "
            "tools to inspect and modify the workspace. Be concise and factual."
        ),
    )

    # 5–7. Submit the prompt; Strands selects rosie_write_file and answers.
    result = agent(M3_PROMPT)
    print("--- final response ---")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
