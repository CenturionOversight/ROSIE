"""Tests for the ROSIE operating system prompt seeding."""
from unittest.mock import MagicMock, patch

from wrapper.cli import main
from wrapper.context import compact_history
from wrapper.system_prompt import ROSIE_SYSTEM_PROMPT
from wrapper.tools import set_workspace_root


def _make_message(content=None, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    return msg


def _make_choice(message):
    choice = MagicMock()
    choice.message = message
    return choice


def _make_response(message):
    resp = MagicMock()
    resp.choices = [_make_choice(message)]
    return resp


class TestSystemPromptInOneShot:
    def test_one_shot_messages_begin_with_system_prompt(self, tmp_path, monkeypatch, capsys):
        root = tmp_path.resolve()
        set_workspace_root(root)
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        # Prevent real PEEP/LLM calls; capture the messages sent to completion.
        captured = {}

        def fake_completion(models, messages, temperature):
            captured["messages"] = list(messages)
            return _make_response(_make_message(content="ok"))

        with patch("wrapper.cli._configure_peep_executor", return_value="peep=attached"), \
             patch("wrapper.cli._completion", side_effect=fake_completion):
            rc = main([str(root), "do a thing"])

        assert rc == 0
        assert "messages" in captured
        first = captured["messages"][0]
        assert first["role"] == "system"
        assert first["content"] == ROSIE_SYSTEM_PROMPT

    def test_piped_input_begins_with_system_prompt(self, tmp_path, monkeypatch, capsys):
        root = tmp_path.resolve()
        set_workspace_root(root)
        monkeypatch.setattr("wrapper.tools._workspace_root", root)
        monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: False, read=lambda: "hello there"))

        captured = {}

        def fake_completion(models, messages, temperature):
            captured["messages"] = list(messages)
            return _make_response(_make_message(content="ok"))

        with patch("wrapper.cli._configure_peep_executor", return_value="peep=attached"), \
             patch("wrapper.cli._completion", side_effect=fake_completion):
            rc = main([str(root)])

        assert rc == 0
        assert captured["messages"][0]["role"] == "system"
        assert captured["messages"][0]["content"] == ROSIE_SYSTEM_PROMPT


class TestSystemPromptSurvival:
    def test_survives_compaction(self):
        messages = [
            {"role": "system", "content": ROSIE_SYSTEM_PROMPT},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]
        compacted = compact_history(messages, max_turns=1, max_chars=50)
        assert compacted[0]["role"] == "system"
        assert compacted[0]["content"] == ROSIE_SYSTEM_PROMPT

    def test_no_duplicate_system_prompt_across_turns(self):
        # Compaction is applied between turns but must never double the system msg.
        messages = [
            {"role": "system", "content": ROSIE_SYSTEM_PROMPT},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ]
        compacted_once = compact_history(messages, max_turns=5, max_chars=100_000)
        # compact again -> still exactly one system turn
        compacted_twice = compact_history(compacted_once, max_turns=5, max_chars=100_000)
        system_msgs = [m for m in compacted_twice if m["role"] == "system"]
        assert len(system_msgs) == 1


class TestSystemPromptInToolLoop:
    def test_tool_loop_receives_system_prompt(self, tmp_path, monkeypatch, capsys):
        """The completion call inside the tool loop sees the system prompt."""
        root = tmp_path.resolve()
        set_workspace_root(root)
        monkeypatch.setattr("wrapper.tools._workspace_root", root)

        seen_system = {}

        def fake_completion(models, messages, temperature):
            seen_system["system"] = any(m.get("role") == "system" for m in messages)
            return _make_response(_make_message(content="final"))

        with patch("wrapper.cli._configure_peep_executor", return_value="peep=attached"), \
             patch("wrapper.cli._completion", side_effect=fake_completion):
            main([str(root), "inspect files"])

        assert seen_system.get("system") is True
