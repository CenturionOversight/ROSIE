"""One-command runner for the real Amazon-backed M1 execution.

Assembles the real Strands agent from separately-owned parts:

- workspace ownership: ``RuntimeSession(workspace=...)`` (this module);
- ROSIE tool exposure: ``wrapper.strands_bridge`` (no model logic);
- Amazon model wiring: ``BedrockModel`` (this module, isolated so provider
  swaps never touch ROSIE tool integration);
- agent loop and tool selection: Strands.

Running this module performs a REAL Bedrock request.  It is allowed to fail
at AWS authentication until credentials are available; that failure is
truthful and expected pre-credentials.  No Gemini/OpenRouter/mock fallback
exists here by design.
"""
from __future__ import annotations

import sys
from pathlib import Path

from wrapper.runtime import RuntimeSession
from wrapper.strands_bridge import create_rosie_tools

__all__ = ["DEFAULT_WORKSPACE", "M1_PROMPT", "main"]

DEFAULT_WORKSPACE = Path(r"D:\ROSIE")

M1_PROMPT = (
    "Inspect the Git status of this workspace and tell me whether it is "
    "clean or has changes."
)


def main(argv: list[str] | None = None) -> int:
    """Run the real M1 agent turn against the selected workspace."""
    argv = list(sys.argv[1:] if argv is None else argv)

    workspace = Path(argv[0]).resolve() if argv else DEFAULT_WORKSPACE
    if not workspace.is_dir():
        print(f"ERROR: workspace does not exist: {workspace}")
        return 2

    # 1. Workspace ownership — explicit RuntimeSession, no global state.
    session = RuntimeSession(workspace=workspace)

    # 2. ROSIE tools via the adapter.
    rosie_tools = create_rosie_tools(session)

    # 3. Real Amazon-backed model (isolated provider construction).
    from strands.models import BedrockModel

    model = BedrockModel(
        model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    )

    # 4. Real Strands agent.
    from strands import Agent

    agent = Agent(
        model=model,
        tools=rosie_tools,
        system_prompt=(
            "You are ROSIE's workspace assistant. Use the provided ROSIE "
            "tool to inspect the workspace. Be concise and factual."
        ),
    )

    # 5–7. Submit the prompt; Strands selects the tool and answers.
    result = agent(M1_PROMPT)
    print("--- final response ---")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
