"""Tests for conversation history compaction (wrapper/context.py)."""
from wrapper.context import compact_history, count_messages_chars


class TestCountMessagesChars:
    def test_empty_messages(self):
        assert count_messages_chars([]) == 0

    def test_simple_content(self):
        msgs = [{"role": "user", "content": "hello world"}]
        assert count_messages_chars(msgs) == 11

    def test_multiple_messages(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        assert count_messages_chars(msgs) == 10

    def test_tool_call_args_counted(self):
        msgs = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"arguments": '{"cmd": "ls -la"'}}
            ]},
        ]
        assert count_messages_chars(msgs) == len('{"cmd": "ls -la"')

    def test_none_content_skipped(self):
        msgs = [{"role": "user", "content": None}]
        assert count_messages_chars(msgs) == 0


class TestCompactHistoryPreservation:
    def test_short_history_unchanged(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = compact_history(msgs, max_turns=12, max_chars=120000)
        assert result == msgs

    def test_system_message_preserved(self):
        msgs = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = compact_history(msgs, max_turns=0, max_chars=1)
        # System message must survive even with extreme limits.
        assert result[0]["role"] == "system"
        assert "helpful" in result[0]["content"]

    def test_latest_completed_turn_retained(self):
        msgs = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "response1"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "response2"},
        ]
        # Force aggressive compaction: 1 turn, 1 char.
        result = compact_history(msgs, max_turns=1, max_chars=1)
        # Should keep system (none) + at least the last completed turn.
        roles = [m["role"] for m in result]
        assert "user" in roles
        assert "assistant" in roles
        # The latest turn's content must be present.
        joined = " ".join(m.get("content", "") or "" for m in result)
        assert "response2" in joined or "second" in joined


class TestCompactHistoryTurnLimit:
    def test_oldest_turns_removed_first(self):
        msgs = []
        for i in range(10):
            msgs.append({"role": "user", "content": f"turn {i}"})
            msgs.append({"role": "assistant", "content": f"answer {i}"})
        result = compact_history(msgs, max_turns=3, max_chars=120000)
        # 3 turns: 6 messages (3 user + 3 assistant)
        users = [m for m in result if m["role"] == "user"]
        assert len(users) == 3
        # Should be the 3 newest turns.
        assert "turn 7" in users[0]["content"]
        assert "turn 9" in users[-1]["content"]

    def test_turn_limit_with_system_prefix(self):
        msgs = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "turn 1"},
            {"role": "assistant", "content": "answer 1"},
            {"role": "user", "content": "turn 2"},
            {"role": "assistant", "content": "answer 2"},
            {"role": "user", "content": "turn 3"},
            {"role": "assistant", "content": "answer 3"},
        ]
        result = compact_history(msgs, max_turns=1, max_chars=120000)
        # System preserved + 1 turn (2 msgs).
        assert result[0]["role"] == "system"
        remaining_users = [m for m in result if m["role"] == "user"]
        assert len(remaining_users) == 1
        assert "turn 3" in remaining_users[0]["content"]


class TestCompactHistoryCharLimit:
    def test_char_limit_works(self):
        msgs = []
        for i in range(5):
            msgs.append({"role": "user", "content": f"user {i} " + "x" * 10000})
            msgs.append({"role": "assistant", "content": f"asst {i} " + "y" * 10000})
        result = compact_history(msgs, max_turns=12, max_chars=15000)
        assert count_messages_chars(result) <= 15000 + 30000  # allow last turn to exceed

    def test_char_limit_newest_retained(self):
        msgs = []
        for i in range(5):
            msgs.append({"role": "user", "content": f"turn{i}"})
            msgs.append({"role": "assistant", "content": "y" * 10000})
        result = compact_history(msgs, max_turns=12, max_chars=5000)
        # The newest turn must be present.
        joined = " ".join(m.get("content", "") or "" for m in result)
        assert "turn4" in joined

    def test_both_limits_applied(self):
        msgs = []
        for i in range(20):
            msgs.append({"role": "user", "content": f"turn{i}"})
            msgs.append({"role": "assistant", "content": f"answer{i}"})
        result = compact_history(msgs, max_turns=5, max_chars=100)
        users = [m for m in result if m["role"] == "user"]
        assert len(users) <= 5


class TestCompactHistoryCompleteness:
    def test_complete_turns_intact(self):
        """A turn = user + assistant + (tool calls + tool results). Must not be split."""
        msgs = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
            {"role": "assistant", "content": "done"},
            {"role": "user", "content": "next question"},
            {"role": "assistant", "content": "answering next"},
        ]
        # Force compaction: keep only 1 turn.
        result = compact_history(msgs, max_turns=1, max_chars=1)
        # Must keep the latest complete turn (user + assistant).
        assert result[-1]["content"] == "answering next"
        assert result[-2]["content"] == "next question"
        # The first turn must be fully removed (not split).
        assert "do something" not in [m.get("content") for m in result]

    def test_active_turn_not_compacted(self):
        """If the last turn is still active (no final assistant text), it's kept."""
        msgs = [
            {"role": "user", "content": "old question"},
            {"role": "assistant", "content": "old answer"},
            {"role": "user", "content": "new question"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
        ]
        result = compact_history(msgs, max_turns=0, max_chars=1)
        # The active turn (user "new question" + assistant + tool) must be retained.
        joined = " ".join(m.get("content", "") or "" for m in result)
        assert "new question" in joined

    def test_final_assistant_response_retained(self):
        """Verify the final assistant answer is part of the history structure."""
        msgs = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
        ]
        # With generous limits, everything should be kept.
        result = compact_history(msgs, max_turns=12, max_chars=120000)
        assert result == msgs
        # The last assistant response is the final answer.
        assert result[-1]["role"] == "assistant"
        assert result[-1]["content"] == "a2"
