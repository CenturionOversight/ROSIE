"""End-to-end tests for the agent loop with mocked LiteLLM calls."""
import json
from unittest.mock import MagicMock, patch

import litellm.exceptions as litellm_errors

from wrapper.cli import _resolve_tool_calls


def _make_message(content=None, tool_calls=None):
    """Build a mock Message object with content and tool_calls."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    return msg


def _make_choice(message):
    """Build a mock Choice wrapping a Message."""
    choice = MagicMock()
    choice.message = message
    return choice


def _make_response(message):
    """Build a mock ModelResponse wrapping a Choice/Message."""
    resp = MagicMock()
    resp.choices = [_make_choice(message)]
    return resp


def _make_tool_call(name, arguments, tc_id="call_1"):
    tc = MagicMock()
    tc.id = tc_id
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


class TestResolveToolCalls:
    def test_single_text_response(self, tmp_workspace, yolo_policy):
        mock_response = _make_response(_make_message(content="Hello from the model!"))
        with patch("wrapper.cli._completion", return_value=mock_response):
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.2,
                max_iterations=5,
            )
        assert result == "Hello from the model!"

    def test_single_tool_call_then_text(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "list files"}]
        tc = _make_tool_call("inspect_git_status", "{}")
        msg_with_tools = _make_message(tool_calls=[tc])
        msg_final = _make_message(content="Done! Files listed above.")

        mock_resp_1 = _make_response(msg_with_tools)
        mock_resp_2 = _make_response(msg_final)

        with patch("wrapper.cli._completion", side_effect=[mock_resp_1, mock_resp_2]) as mock_completion:
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert result == "Done! Files listed above."
        assert mock_completion.call_count == 2
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1

    def test_multiple_tool_calls(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "show readme and git status"}]
        tc1 = _make_tool_call("inspect_git_status", "{}", tc_id="call_1")
        tc2 = _make_tool_call("run_shell", json.dumps({"command": "echo test"}), tc_id="call_2")
        msg1 = _make_message(content="", tool_calls=[tc1, tc2])
        msg2 = _make_message(content="Both done!")

        mock_resp_1 = _make_response(msg1)
        mock_resp_2 = _make_response(msg2)

        with patch("wrapper.cli._completion", side_effect=[mock_resp_1, mock_resp_2]):
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert result == "Both done!"
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 2

    def test_max_iterations_reached(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "loop forever"}]
        tc = _make_tool_call("inspect_git_status", "{}")
        msg_with_tools = _make_message(tool_calls=[tc])
        mock_response = _make_response(msg_with_tools)

        with patch("wrapper.cli._completion", return_value=mock_response) as mock_completion:
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=3,
            )

        assert "maximum iterations" in result.lower()
        assert mock_completion.call_count == 3

    def test_model_fallback_within_resolve(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "hi"}]
        mock_response = _make_response(_make_message(content="Got it!"))

        auth_error = litellm_errors.AuthenticationError(
            message="Bad key", llm_provider="test", model="fail"
        )

        with patch("wrapper.cli.litellm.completion", side_effect=[auth_error, mock_response]) as mock_completion:
            result = _resolve_tool_calls(
                models=["bad-model", "good-model"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert result == "Got it!"
        assert mock_completion.call_count == 2

    def test_invalid_tool_name_in_dispatch(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "use a bad tool"}]
        tc = _make_tool_call("unknown_tool", "{}")
        msg_with_tools = _make_message(tool_calls=[tc])
        msg_final = _make_message(content="I failed to call that tool.")

        mock_resp_1 = _make_response(msg_with_tools)
        mock_resp_2 = _make_response(msg_final)

        with patch("wrapper.cli._completion", side_effect=[mock_resp_1, mock_resp_2]):
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert result == "I failed to call that tool."

    def test_no_text_content(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "hi"}]
        msg = _make_message(content=None, tool_calls=None)
        mock_response = _make_response(msg)

        with patch("wrapper.cli._completion", return_value=mock_response):
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert "no text response" in result.lower()

    def test_empty_tool_calls_is_treated_as_final(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "hi"}]
        msg = _make_message(content="Just text, no tools", tool_calls=[])
        mock_response = _make_response(msg)

        with patch("wrapper.cli._completion", return_value=mock_response):
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert result == "Just text, no tools"

    def test_assistant_message_appended_to_history(self, tmp_workspace, yolo_policy):
        messages = [{"role": "user", "content": "do something"}]
        tc = _make_tool_call("inspect_file", json.dumps({"relative_path": "f.txt"}))
        msg_with_tools = _make_message(content="Let Me check", tool_calls=[tc])

        with patch("wrapper.cli._completion", return_value=_make_response(msg_with_tools)):
            _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=1,
            )

        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        # With max_iterations=1, the model produces tool calls but never a
        # final text response — so the loop exhausts and appends an error
        # assistant message (which is itself a final assistant answer).
        assert len(assistant_msgs) == 2
        assert "tool_calls" in assistant_msgs[0]
        assert "maximum iterations" in assistant_msgs[1]["content"].lower()

    def test_final_assistant_response_retained_in_history(self, tmp_workspace, yolo_policy):
        """The model's final text response must be appended to messages."""
        messages = [{"role": "user", "content": "hi"}]
        mock_response = _make_response(_make_message(content="Final answer here."))

        with patch("wrapper.cli._completion", return_value=mock_response):
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert result == "Final answer here."
        # The final assistant response must be in the history.
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "Final answer here."
        assert messages[-1] == {"role": "assistant", "content": "Final answer here."}

    def test_final_assistant_response_retained_after_tool_calls(self, tmp_workspace, yolo_policy):
        """After tool calls resolve, the final text must still be in history."""
        messages = [{"role": "user", "content": "list files"}]
        tc = _make_tool_call("inspect_git_status", "{}")
        msg_with_tools = _make_message(tool_calls=[tc])
        msg_final = _make_message(content="Done! Files listed above.")

        mock_resp_1 = _make_response(msg_with_tools)
        mock_resp_2 = _make_response(msg_final)

        with patch("wrapper.cli._completion", side_effect=[mock_resp_1, mock_resp_2]):
            result = _resolve_tool_calls(
                models=["model-a"],
                messages=messages,
                temperature=0.2,
                max_iterations=5,
            )

        assert result == "Done! Files listed above."
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        # One assistant msg with tool_calls, one with final text.
        assert len(assistant_msgs) == 2
        # The last assistant message has the final answer.
        assert assistant_msgs[-1]["content"] == "Done! Files listed above."
        assert "tool_calls" not in assistant_msgs[-1]
