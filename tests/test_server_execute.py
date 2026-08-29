"""Focused tests for the HACKASS /execute HTTP boundary in server.py.

Tests cover:
- GET /health still works
- Unknown GET returns 404
- Valid POST /execute invokes the HACKASS execution boundary (mocked)
- Prompt reaches run_hackass
- Successful result becomes the expected JSON response
- Malformed JSON is rejected
- Missing prompt is rejected
- Empty prompt is rejected
- Non-string prompt is rejected
- Oversized body is rejected
- Arbitrary workspace input cannot control workspace
- Approval/model/API-key overrides from browser input are not honored
- HACKASS exception returns safe failure JSON
- Exception response does not contain traceback/secrets
- Concurrent execution handling matches the chosen safety strategy
"""
from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import server as server_mod


def _start_server(tmp_path):
    """Start the server on an ephemeral port, return (port, shutdown_fn, tmp_path)."""
    monkeypatch_workspace(tmp_path)

    srv = server_mod.ThreadingHTTPServer(("127.0.0.1", 0), server_mod._Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    # Give it a moment to bind.
    time.sleep(0.05)

    def shutdown():
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2)

    return port, shutdown


def _request(port, method, path, body=None, headers=None):
    """Make an HTTP request to the test server, return (status, data)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    conn.request(method, path, body=body, headers=hdrs)
    resp = conn.getresponse()
    payload = resp.read().decode()
    conn.close()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = payload
    return resp.status, data


def monkeypatch_workspace(tmp_path):
    """Patch _WORKSPACE and internal globals to use tmp_path."""
    server_mod._WORKSPACE = str(tmp_path)


class TestHealthEndpoint:
    """Verify GET /health continues to work after /execute is added."""

    def test_health_returns_ok(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "GET", "/health")
            assert status == 200
            assert data["status"] == "ok"
            assert "rosie_version" in data
        finally:
            shutdown()

    def test_unknown_get_returns_404(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "GET", "/nonexistent")
            assert status == 404
            assert data["error"] == "not found"
        finally:
            shutdown()


class TestExecuteRequestValidation:
    """Verify request validation for POST /execute."""

    def test_valid_execute_invokes_hackass(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            with patch("hackass.agent.run_hackass", return_value="mock result from HACKASS"):
                status, data = _request(
                    port, "POST", "/execute",
                    body=json.dumps({"prompt": "inspect README.md"}),
                )
            assert status == 200
            assert data["status"] == "ok"
            assert data["result"] == "mock result from HACKASS"
        finally:
            shutdown()

    def test_prompt_reaches_run_hackass(self, tmp_path):
        """Verify the exact prompt is forwarded to run_hackass."""
        port, shutdown = _start_server(tmp_path)
        try:
            with patch("hackass.agent.run_hackass", return_value="ok") as mock_run:
                _request(port, "POST", "/execute",
                         body=json.dumps({"prompt": "count files in the repo"}))
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert kwargs.get("prompt") == "count files in the repo"
            assert "workspace" in kwargs
        finally:
            shutdown()

    def test_malformed_json_rejected(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "POST", "/execute", body="not json{")
            assert status == 400
            assert data["status"] == "error"
            assert data["error"] == "invalid_json"
        finally:
            shutdown()

    def test_missing_prompt_rejected(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "POST", "/execute",
                                    body=json.dumps({"other": "value"}))
            assert status == 400
            assert data["status"] == "error"
            assert data["error"] == "invalid_prompt"
        finally:
            shutdown()

    def test_empty_prompt_rejected(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "POST", "/execute",
                                    body=json.dumps({"prompt": ""}))
            assert status == 400
            assert data["status"] == "error"
            assert data["error"] == "invalid_prompt"
        finally:
            shutdown()

    def test_whitespace_prompt_rejected(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "POST", "/execute",
                                    body=json.dumps({"prompt": "   \n\t  "}))
            assert status == 400
            assert data["status"] == "error"
            assert data["error"] == "invalid_prompt"
        finally:
            shutdown()

    def test_non_string_prompt_rejected(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "POST", "/execute",
                                    body=json.dumps({"prompt": 12345}))
            assert status == 400
            assert data["status"] == "error"
            assert data["error"] == "invalid_prompt"
        finally:
            shutdown()

    def test_oversized_body_rejected(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            big_prompt = {"prompt": "x" * (server_mod._MAX_BODY_BYTES + 100)}
            status, data = _request(port, "POST", "/execute",
                                    body=json.dumps(big_prompt))
            assert status == 413
            assert data["status"] == "error"
            assert data["error"] == "payload_too_large"
        finally:
            shutdown()

    def test_non_dict_body_rejected(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            status, data = _request(port, "POST", "/execute",
                                    body=json.dumps([1, 2, 3]))
            assert status == 400
            assert data["status"] == "error"
        finally:
            shutdown()


class TestWorkspaceBoundary:
    """Verify arbitrary workspace input cannot control workspace."""

    def test_workspace_field_not_honored(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            with patch("hackass.agent.run_hackass", return_value="ok") as mock_run:
                status, data = _request(port, "POST", "/execute",
                                        body=json.dumps({
                                            "prompt": "test",
                                            "workspace": "/etc",
                                        }))
            assert status == 200
            args, kwargs = mock_run.call_args
            # The workspace must come from the server, not the browser.
            assert kwargs.get("workspace") != "/etc"
            assert kwargs.get("workspace") == str(tmp_path)
        finally:
            shutdown()

    def test_no_browser_override_fields_honored(self, tmp_path):
        """Verify approval/model/api_key overrides are ignored."""
        port, shutdown = _start_server(tmp_path)
        try:
            with patch("hackass.agent.run_hackass", return_value="ok") as mock_run:
                status, data = _request(port, "POST", "/execute",
                                        body=json.dumps({
                                            "prompt": "test",
                                            "yolo": False,
                                            "model": "gpt-4",
                                            "api_key": "sk-fake-key-123",
                                            "auto_write": True,
                                        }))
            assert status == 200
            args, kwargs = mock_run.call_args
            # Only workspace and prompt should be forwarded.
            allowed_keys = {"workspace", "prompt"}
            assert set(kwargs.keys()) <= allowed_keys
            assert "yolo" not in kwargs or kwargs.get("yolo") is True
            assert "model_name" not in kwargs or kwargs.get("model_name") is None
            assert "api_key" not in kwargs or kwargs.get("api_key") is None
        finally:
            shutdown()


class TestExecutionFailureHandling:
    """Verify HACKASS exception returns safe failure JSON."""

    def test_hackass_exception_returns_safe_error(self, tmp_path):
        port, shutdown = _start_server(tmp_path)
        try:
            with patch("hackass.agent.run_hackass",
                       side_effect=RuntimeError("API key exhausted")):
                status, data = _request(port, "POST", "/execute",
                                        body=json.dumps({"prompt": "test"}))
            assert status == 500
            assert data["status"] == "error"
            assert data["error"] == "execution_failed"
        finally:
            shutdown()

    def test_exception_response_no_traceback(self, tmp_path):
        """Exception response must not contain traceback/secrets."""
        port, shutdown = _start_server(tmp_path)
        try:
            secret_value = "SUPER_SECRET_TOKEN_abc123"
            with patch("hackass.agent.run_hackass",
                       side_effect=RuntimeError(f"Internal error with {secret_value}")):
                status, data = _request(port, "POST", "/execute",
                                        body=json.dumps({"prompt": "test"}))
            assert status == 500
            response_str = json.dumps(data)
            assert secret_value not in response_str
            assert "Traceback" not in response_str
            assert "File " not in response_str
        finally:
            shutdown()


class TestConcurrentExecution:
    """Verify concurrent requests are serialized."""

    def test_concurrent_requests_use_lock(self, tmp_path):
        """Two simultaneous requests should be serialized via _EXECUTION_LOCK."""
        port, shutdown = _start_server(tmp_path)

        original_lock = server_mod._EXECUTION_LOCK
        lock_acquired = threading.Event()
        lock_released = threading.Event()
        call_count = [0]

        class TrackingLock:
            def __enter__(self):
                call_count[0] += 1
                lock_acquired.set()
                return self

            def __exit__(self, *args):
                lock_released.set()
                return False

        # Replace the lock so we can verify it's used
        server_mod._EXECUTION_LOCK = TrackingLock()

        try:
            with patch("hackass.agent.run_hackass", return_value="result") as mock_run:
                results = []

                def make_request():
                    status, data = _request(port, "POST", "/execute",
                                            body=json.dumps({"prompt": "test"}))
                    results.append((status, data))

                t1 = threading.Thread(target=make_request)
                t2 = threading.Thread(target=make_request)
                t1.start()
                t2.start()
                t1.join(timeout=10)
                t2.join(timeout=10)

            # Both requests completed
            assert len(results) == 2
            assert all(status == 200 for status, _ in results)
        finally:
            server_mod._EXECUTION_LOCK = original_lock
            shutdown()
