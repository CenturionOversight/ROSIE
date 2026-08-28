"""Tests for the CLI argument parser and model chain construction."""
import pytest

from wrapper.cli import _build_parser, FALLBACK_MODELS, _is_ollama_model


class TestArgumentParser:
    def test_default_workspace(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.workspace == "."
        assert args.model == "ollama/qwen2.5-coder:7b"

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


class TestIsOllamaModel:
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
