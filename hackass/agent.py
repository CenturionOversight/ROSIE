"""HACKASS ADK agent factory and execution entry point.

Creates a Google ADK ``LlmAgent`` configured with the Gemini 3.5+
model and the ARCHESTRATOR tool bridge. Provides a synchronous
``run_hackass()`` entry point for executing a single prompt through
the Google execution path.

Usage::

    from hackass import run_hackass

    result = run_hackass(
        workspace="/path/to/repo",
        prompt="Inspect the repository and explain its architecture.",
    )
    print(result)
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from google.genai import client as genai_client_mod

from hackass.bridge import create_architect_tools
from hackass.config import get_model_name, VERTEXAI_PROJECT, VERTEXAI_LOCATION
from wrapper.tools import set_workspace_root, set_policy
from wrapper.policy import ApprovalPolicy, ExecutionPolicy

__all__ = ["run_hackass", "create_agent"]


INSTRUCTION = """You are ROSIE (HACKASS edition), a coding agent that can inspect files,
preview and write file changes, inspect Git status, and run shell commands in a
workspace. You use Google ADK with Gemini 3.5+ via Vertex AI. The workspace root
and approval policy are managed by the surrounding ARCHESTRATOR execution layer.

When you request a tool action, the ARCHESTRATOR tool layer executes it.
File writes and shell commands will be auto-approved in this environment."""


def _create_gemini_llm(model_name: str):
    """Create a Gemini LLM instance configured for Vertex AI.

    Uses Application Default Credentials (ADC) for Vertex AI authentication.
    Falls back to Gemini API key if GOOGLE_API_KEY is set.
    """
    from google.adk.models.google_llm import Gemini

    if os.environ.get("GOOGLE_API_KEY"):
        return Gemini(model=model_name)

    genai_client = genai_client_mod.Client(
        vertexai=True,
        location=VERTEXAI_LOCATION,
        project=VERTEXAI_PROJECT,
    )
    return Gemini(model=model_name, client=genai_client)


def create_agent(
    workspace: str | Path,
    model_name: Optional[str] = None,
    yolo: bool = True,
) -> LlmAgent:
    """Create an ADK LlmAgent wired to the ARCHESTRATOR tool bridge.

    Args:
        workspace: The workspace directory for tool operations.
        model_name: Optional override for the Gemini model. Defaults
            to the value from ``hackass.config.get_model_name()``.
        yolo: If True (default), auto-approve all tool actions. If False,
            uses the ask policy.

    Returns:
        A configured ``LlmAgent`` instance.
    """
    workspace_path = Path(workspace).resolve()

    set_workspace_root(workspace_path)

    policy = ApprovalPolicy()
    policy.update_from_flags(yolo=yolo, auto_write=False)
    set_policy(policy)

    model = model_name or get_model_name()
    llm = _create_gemini_llm(model)

    agent = LlmAgent(
        name="rosie_hackass",
        model=llm,
        instruction=INSTRUCTION,
        tools=create_architect_tools(),
    )

    return agent


def run_hackass(
    workspace: str | Path,
    prompt: str,
    model_name: Optional[str] = None,
    yolo: bool = True,
    api_key: Optional[str] = None,
) -> str:
    """Execute a prompt through the HACKASS Google ADK + Gemini path.

    This is the hackathon-created execution entry point. It:

    1. Configures the ARCHESTRATOR workspace and approval policy;
    2. Creates an ADK agent with Gemini 3.5+ via Vertex AI;
    3. Runs the agent synchronously and collects the final response.

    Args:
        workspace: Workspace directory for tool operations.
        prompt: The user's request to execute.
        model_name: Optional model override. Defaults to Gemini 3.5+.
        yolo: Auto-approve all tool actions (default True).
        api_key: Optional Gemini API key. If not provided, falls back
            to Application Default Credentials (Vertex AI).

    Returns:
        The agent's final text response.
    """
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key

    agent = create_agent(
        workspace=workspace,
        model_name=model_name,
        yolo=yolo,
    )

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    runner = Runner(
        agent=agent,
        app_name="rosie-hackass",
        session_service=session_service,
        artifact_service=artifact_service,
        auto_create_session=True,
    )

    session = session_service.create_session_sync(
        app_name="rosie-hackass",
        user_id="user",
    )

    response = asyncio.run(
        _run_async(runner, session, prompt)
    )

    return response


async def _run_async(runner: Runner, session, prompt: str) -> str:
    """Run the agent asynchronously and return the final text response."""
    final_response = ""

    content = types.Content(role="user", parts=[types.Part(text=prompt)])

    for event in runner.run(
        user_id="user",
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response() and event.content:
            parts = event.content.parts
            if parts:
                final_response = parts[0].text or ""
            break

    return final_response
