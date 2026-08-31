"""CLI entry point for HACKASS Google ADK execution path.

Usage::

    python -m hackass.run /path/to/workspace "inspect this repo"

Set GEMINI_API_KEY for API key auth, or rely on Google Application Default
Credentials for Vertex AI auth.
"""
from __future__ import annotations

import argparse
import sys

from hackass.agent import run_hackass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hackass",
        description="HACKASS: Google ADK + Gemini execution path for ROSIE.",
    )
    parser.add_argument(
        "workspace",
        help="Target workspace directory.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="User prompt (joins remaining args).",
    )
    parser.add_argument(
        "-m", "--model",
        default=None,
        help="Gemini model override (default: gemini-3.7-flash).",
    )
    parser.add_argument(
        "--ask",
        action="store_true",
        help="Use ask-mode approval policy instead of auto-approve (yolo).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gemini API key (or set GEMINI_API_KEY env var).",
    )
    args = parser.parse_args(argv)

    prompt = " ".join(args.prompt) if args.prompt else ""
    if not prompt:
        print("Error: prompt is required.", file=sys.stderr)
        return 1

    import os
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")

    try:
        result = run_hackass(
            workspace=args.workspace,
            prompt=prompt,
            model_name=args.model,
            yolo=not args.ask,
            api_key=api_key,
        )
        print(result)
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
