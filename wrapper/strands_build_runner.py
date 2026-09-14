"""One-command live proof: Strands → Bedrock Nova Micro → ROSIE write + run.

M4 companion to :mod:`wrapper.strands_runner` (M1/M2 read-only proof) and
:mod:`wrapper.strands_write_runner` (M3 write proof).  Issues one
natural-language build-and-run request so the proof demonstrates the real
local construction loop: ROSIE writes a Python file to disk, then ROSIE
executes that file, and the real stdout flows back through Strands into the
final response.

Default workspace is ``D:\\ROSIE_STRANDS_TEST`` (the established Strands test
boundary).  Policy is ROSIE's documented ``auto-write``: file writes are
auto-approved while shell commands still reach the interactive approval
boundary — deliberately not ``yolo``, so the shell gate is exercised, not
bypassed (answer ``y`` at the prompt during the live run).
"""
from __future__ import annotations

import sys
from pathlib import Path

from wrapper.policy import ApprovalPolicy
from wrapper.runtime import RuntimeSession
from wrapper.strands_bridge import create_rosie_tools

__all__ = ["DEFAULT_WORKSPACE", "M4_PROMPT", "PROOF_RELATIVE_PATH", "main"]

DEFAULT_WORKSPACE = Path(r"D:\ROSIE_STRANDS_TEST")

PROOF_RELATIVE_PATH = "m4_build_proof.py"

PROOF_SOURCE = 'print("ROSIE_BUILD_LOOP_PROVEN")'

M4_PROMPT = (
    f"Create a Python file named {PROOF_RELATIVE_PATH} whose entire content "
    f"is exactly this one line: {PROOF_SOURCE}  Then run that file and tell "
    "me the result."
)


def main(argv: list[str] | None = None) -> int:
    """Run the real M4 build-loop agent turn against the selected workspace."""
    argv = list(sys.argv[1:] if argv is None else argv)

    workspace = Path(argv[0]).resolve() if argv else DEFAULT_WORKSPACE
    if not workspace.is_dir():
        print(f"ERROR: workspace does not exist: {workspace}")
        return 2

    # 1. Workspace ownership — explicit RuntimeSession, no global state.
    #    auto-write: writes auto-approve; shell commands still prompt.
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
            "tools to inspect, modify, and run things in the workspace: "
            "write files with rosie_write_file and execute commands with "
            "rosie_run_shell (the command runs with its working directory "
            "at the workspace root; plain 'python' is on PATH). Report "
            "exactly what the tools return. Be concise and factual."
        ),
    )

    # 5–7. Submit the prompt; Strands decides which ROSIE tools to use.
    result = agent(M4_PROMPT)
    print("--- final response ---")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
