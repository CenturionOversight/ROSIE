"""Tests for the model fallback logic in _completion."""
import pytest

import litellm.exceptions as litellm_errors

from wrapper.cli import _completion


def _make_success_response(content="ok"):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.choices[0].message.tool_calls = None
    return resp


def _make_api_error(status_code):
    return litellm_errors.APIError(
        status_code=status_code,
        message=f"HTTP {status_code}",
        llm_provider="test",
        model="test-model",
    )


def _make_auth_error():
    return litellm_errors.AuthenticationError(
        message="Bad API key",
        llm_provider="test",
        model="test-model",
    )


def _make_rate_limit_error():
    return litellm_errors.RateLimitError(
        message="Rate limited",
        llm_provider="test",
        model="test-model",
    )


def _make_conn_error():
    return litellm_errors.APIConnectionError(
        message="Connection refused",
        llm_provider="test",
        model="test-model",
    )


def _make_not_found_error():
    return litellm_errors.NotFoundError(
        message="Model not found",
        model="test-model",
        llm_provider="test",
    )


def _make_svc_unavailable_error():
    return litellm_errors.ServiceUnavailableError(
        message="Service unavailable",
        llm_provider="test",
        model="test-model",
    )


from unittest.mock import patch, MagicMock


class TestCompletionFallback:
    def test_first_model_succeeds_no_fallback(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion", return_value=mock_response) as mock_completion:
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 1
            assert mock_completion.call_args.kwargs["model"] == "model-a"

    def test_fallback_on_auth_error(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_auth_error(), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_fallback_on_api_error_402(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_api_error(402), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_fallback_on_api_error_401(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_api_error(401), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_fallback_on_api_error_429(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_api_error(429), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_fallback_on_api_connection_error(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_conn_error(), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_fallback_on_rate_limit_error(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_rate_limit_error(), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_fallback_on_service_unavailable(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_svc_unavailable_error(), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_fallback_on_not_found_error(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_not_found_error(), mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_all_models_fail_auth_error(self):
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = _make_auth_error()
            with pytest.raises(litellm_errors.AuthenticationError):
                _completion(["model-a", "model-b"], [], 0.2)
            assert mock_completion.call_count == 2

    def test_api_error_400_does_not_trigger_fallback(self):
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = _make_api_error(400)
            with pytest.raises(litellm_errors.APIError):
                _completion(["model-a", "model-b"], [], 0.2)
            assert mock_completion.call_count == 1

    def test_bad_request_error_does_not_trigger_fallback(self):
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            br_error = litellm_errors.BadRequestError(
                message="Bad request", model="x", llm_provider="test",
                response=None,
            )
            mock_completion.side_effect = br_error
            with pytest.raises(litellm_errors.BadRequestError):
                _completion(["model-a", "model-b"], [], 0.2)
            assert mock_completion.call_count == 1

    def test_single_model_no_fallback(self):
        mock_response = _make_success_response("ok")
        with patch("wrapper.cli.litellm.completion", return_value=mock_response):
            result = _completion(["only-model"], [], 0.2)
            assert result == mock_response

    def test_single_model_failure_raises(self):
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = _make_not_found_error()
            with pytest.raises(litellm_errors.NotFoundError):
                _completion(["only-model"], [], 0.2)
            assert mock_completion.call_count == 1

    def test_second_model_fails_different_error(self):
        mock_response = _make_success_response("success")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            conn_error = _make_conn_error()
            mock_completion.side_effect = [conn_error, mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2
            assert mock_completion.call_args_list[1].kwargs["model"] == "model-b"

    def test_completion_passes_tool_schemas(self):
        mock_response = _make_success_response("ok")
        with patch("wrapper.cli.litellm.completion", return_value=mock_response) as mock_completion:
            _completion(["model-a"], [], 0.2)
            assert "tools" in mock_completion.call_args.kwargs
            assert len(mock_completion.call_args.kwargs["tools"]) == 12

    def test_completion_passes_messages_and_temperature(self):
        mock_response = _make_success_response("ok")
        messages = [{"role": "user", "content": "hello"}]
        with patch("wrapper.cli.litellm.completion", return_value=mock_response) as mock_completion:
            _completion(["model-a"], messages, 0.7)
            assert mock_completion.call_args.kwargs["messages"] == messages
            assert mock_completion.call_args.kwargs["temperature"] == 0.7

    def test_bad_gateway_error_triggers_fallback(self):
        mock_response = _make_success_response("ok")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            bg_error = litellm_errors.BadGatewayError(
                message="Bad gateway", llm_provider="test", model="test-model",
            )
            mock_completion.side_effect = [bg_error, mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_internal_server_error_triggers_fallback(self):
        mock_response = _make_success_response("ok")
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            ise_error = litellm_errors.InternalServerError(
                message="Internal server error", llm_provider="test", model="test-model",
            )
            mock_completion.side_effect = [ise_error, mock_response]
            result = _completion(["model-a", "model-b"], [], 0.2)
            assert result == mock_response
            assert mock_completion.call_count == 2

    def test_second_model_also_fails_propagates_error(self):
        with patch("wrapper.cli.litellm.completion") as mock_completion:
            mock_completion.side_effect = [_make_auth_error(), _make_auth_error()]
            with pytest.raises(litellm_errors.AuthenticationError):
                _completion(["model-a", "model-b"], [], 0.2)
            assert mock_completion.call_count == 2
            assert mock_completion.call_args_list[0].kwargs["model"] == "model-a"
            assert mock_completion.call_args_list[1].kwargs["model"] == "model-b"
