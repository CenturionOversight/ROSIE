"""Tests for HACKASS Vertex AI / Gemini model configurability.

Guards the hosted-compliance requirement: VERTEXAI_PROJECT must be
environment-overridable (defaulting to rosie-fire locally) so the hosted
hackass-api service can target hackass-fire via VERTEXAI_PROJECT without a
source change. The required hosted model is gemini-3.7-flash via Vertex AI,
served from the global location.

No live Gemini calls are made here; these only assert config values.
"""
from __future__ import annotations

import importlib

from hackass import config as _cfg


def test_model_is_gemini_3_7_flash():
    assert _cfg.MODEL_NAME == "gemini-3.7-flash"
    assert _cfg.get_model_name() == "gemini-3.7-flash"


def test_vertex_location_is_global():
    assert _cfg.VERTEXAI_LOCATION == "global"


def test_model_env_override_does_not_downgrade(monkeypatch):
    monkeypatch.setenv("HACKASS_GEMINI_MODEL", "gemini-3.7-flash")
    try:
        assert _cfg.get_model_name() == "gemini-3.7-flash"
    finally:
        monkeypatch.delenv("HACKASS_GEMINI_MODEL", raising=False)


def test_default_vertex_project_is_rosie_fire(monkeypatch):
    monkeypatch.delenv("VERTEXAI_PROJECT", raising=False)
    importlib.reload(_cfg)
    try:
        assert _cfg.VERTEXAI_PROJECT == "rosie-fire"
    finally:
        importlib.reload(_cfg)


def test_vertex_project_env_override(monkeypatch):
    monkeypatch.setenv("VERTEXAI_PROJECT", "hackass-fire")
    importlib.reload(_cfg)
    try:
        assert _cfg.VERTEXAI_PROJECT == "hackass-fire"
        assert _cfg.VERTEXAI_LOCATION == "global"
    finally:
        monkeypatch.delenv("VERTEXAI_PROJECT", raising=False)
        importlib.reload(_cfg)
        assert _cfg.VERTEXAI_PROJECT == "rosie-fire"
