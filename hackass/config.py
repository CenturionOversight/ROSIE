"""Gemini model configuration for HACKASS.

Uses Gemini 3.5+ via Vertex AI on the ``rosie-fire`` Google Cloud project.

The model identifier is centralized here so it can be verified from
repository evidence without grepping through implementation code.

Credentials come from Google Application Default Credentials (ADC).
Run ``gcloud auth application-default login --project=rosie-fire`` to
set them up locally. Do not hard-code credentials in tracked files.
"""
from __future__ import annotations

import os

#: The Gemini model used by HACKASS.
#: Gemini 3.5+ via Vertex AI (satisfies the 2026 hackathon requirement).
MODEL_NAME: str = "gemini-3.5-flash"

#: Vertex AI region used for Gemini access.
#: Note: gemini-3.5-flash is available in asia-northeast1 (Vertex AI),
#: not in us-central1. Cloud Run deployment remains in us-central1.
VERTEXAI_LOCATION: str = "asia-northeast1"

#: Google Cloud project for Vertex AI.
VERTEXAI_PROJECT: str = "rosie-fire"

#: Environment variable that can override the model name.
_MODEL_ENV_VAR = "HACKASS_GEMINI_MODEL"


def get_model_name() -> str:
    """Return the Gemini model name, allowing an environment override.

    Returns:
        The model identifier to pass to ADK (``gemini-3.5-flash``
        by default, or the value of ``HACKASS_GEMINI_MODEL`` if set).
    """
    return os.environ.get(_MODEL_ENV_VAR, MODEL_NAME)
