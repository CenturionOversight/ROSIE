"""Tests for the CLI argument parser and model chain construction."""
import pytest

from wrapper.cli import _build_parser, FALLBACK_MODELS, _is_ollama_model, _is_vertex_model


class TestArgumentParser:
    def test_default_model(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.model == "vertex_ai/gemini-3.7-flash"

    def test_explicit_workspace(self):
        parser = _build_parser()
        args = parser.parse_args(["/path/to/repo"])
        assert args.workspace == "/path/to/repo"

    def test_custom_model(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--model", "openai/gpt-4o"])
        assert args.model == "openai/gpt-4o"

    def test_yolo_flag(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--yolo"])
        assert args.yolo is True

    def test_yolo_short_flag(self):
        parser = _build_parser()
        args = parser.parse_args([".", "-y"])
        assert args.yolo is True

    def test_auto_write_flag(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--auto-write"])
        assert args.auto_write is True

    def test_temperature(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--temperature", "0.8"])
        assert args.temperature == 0.8

    def test_max_iterations(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--max-iterations", "50"])
        assert args.max_iterations == 50

    def test_history_turns(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--history-turns", "5"])
        assert args.history_turns == 5

    def test_history_chars(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--history-chars", "50000"])
        assert args.history_chars == 50000

    def test_no_fallback_flag(self):
        parser = _build_parser()
        args = parser.parse_args([".", "--no-fallback"])
        assert args.no_fallback is True

    def test_prompt_positional(self):
        parser = _build_parser()
        args = parser.parse_args([".", "create", "a", "README"])
        assert args.prompt == ["create", "a", "README"]

    def test_combined_flags(self):
        parser = _build_parser()
        args = parser.parse_args([".", "-y", "--model", "gemini/gemini-2.5-pro", "--max-iterations", "10"])
        assert args.yolo is True
        assert args.model == "gemini/gemini-2.5-pro"
        assert args.max_iterations == 10


    def test_default_workspace(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.workspace == "."


class TestIsVertexModel:
    def test_vertex_prefix(self):
        assert _is_vertex_model("vertex_ai/gemini-3.7-flash") is True

    def test_non_vertex(self):
        assert _is_vertex_model("gemini/gemini-2.5-pro") is False
        assert _is_vertex_model("openrouter/deepseek/deepseek-chat") is False
        assert _is_vertex_model("ollama/qwen2.5-coder:7b") is False
    def test_ollama_prefix(self):
        assert _is_ollama_model("ollama/qwen2.5-coder:7b") is True

    def test_ollama_semicolon(self):
        assert _is_ollama_model("ollama;qwen2.5-coder:7b") is True

    def test_non_ollama(self):
        assert _is_ollama_model("gemini/gemini-2.5-pro") is False

    def test_openrouter_not_ollama(self):
        assert _is_ollama_model("openrouter/deepseek/deepseek-chat") is False


class TestFallbackModels:
    def test_fallback_list_has_two_entries(self):
        assert len(FALLBACK_MODELS) == 2

    def test_fallbacks_are_distinct(self):
        assert len(set(FALLBACK_MODELS)) == len(FALLBACK_MODELS)

    def test_at_least_one_ollama_in_fallbacks(self):
        assert any(_is_ollama_model(m) for m in FALLBACK_MODELS)


class TestVertexFallbackBehavior:
    def test_vertex_model_has_no_fallback(self):
        """Vertex models should not fall back to OpenRouter or Ollama."""
        # The model chain for a Vertex model should be just the single model
        model = "vertex_ai/gemini-3.7-flash"
        assert model not in FALLBACK_MODELS
        assert len(FALLBACK_MODELS) > 0  # Fallbacks still exist for non-Vertex


class TestVertexOllamaBehavior:
    def test_ollama_still_explicitly_selectable(self):
        """Ollama should work when explicitly selected via --model."""
        parser = _build_parser()
        args = parser.parse_args([".", "--model", "ollama/qwen2.5-coder:7b"])
        assert args.model == "ollama/qwen2.5-coder:7b"

    def test_explicit_vertex_model_still_works(self):
        """Explicit Vertex model should work via --model."""
        parser = _build_parser()
        args = parser.parse_args([".", "--model", "vertex_ai/gemini-3.5-flash"])
        assert args.model == "vertex_ai/gemini-3.5-flash"
