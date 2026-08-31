"""HACKASS — Google ADK + Gemini integration for ROSIE.

This package is hackathon-created code that integrates Google ADK (the
approved Google Agent Framework) and Gemini 3.5+ into ROSIE's execution path.

It bridges the Google execution path to the pre-existing ARCHESTRATOR
tool/execution layer (the ``wrapper`` package) through a narrow adapter.

Google-specific concerns are confined to this package. The ``wrapper``
package (ARCHESTRATOR core) remains unchanged.
"""
from hackass.agent import run_hackass
from hackass.bridge import create_architect_tools
from hackass.config import MODEL_NAME

__all__ = [
    "MODEL_NAME",
    "create_architect_tools",
    "run_hackass",
]
