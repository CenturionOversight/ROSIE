"""Portable HTTP boundary for ROSIE.

A minimal HTTP server using only the Python standard library.
Binds to the PORT environment variable (as Cloud Run and other
container runtimes provide; defaults to 8080 locally).

Current surface:
  GET  /health  ->  {"status": "ok", "rosie_version": "..."}
  POST /execute ->  {"status": "ok", "result": "..."}

The /execute endpoint invokes the HACKASS Google ADK + Gemini 3.5+
execution path (hackass.run_hackass). The workspace and approval
policy are configured server-side; the browser supplies only the
prompt. A threading lock serializes /execute to protect the shared
ARCHESTRATOR workspace/policy state from concurrent mutation.

This layer imports the ROSIE package (wrapper) to verify it is
installed and available, but does not duplicate any agent logic.
HTTP concerns are kept separate from ROSIE's core modules.
"""
from __future__ import annotations

import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

__all__ = ["main"]

# --- Server-side configuration -------------------------------------------------

#: Maximum request body size in bytes (16 KiB).
_MAX_BODY_BYTES = 16 * 1024

#: Workspace used for execution. Configurable via ROSIE_WORKSPACE,
#: defaults to the current working directory (the container's /app).
_WORKSPACE = os.environ.get("ROSIE_WORKSPACE", os.getcwd())

# --- Concurrency safety -------------------------------------------------------
#: ARCHESTRATOR (wrapper.tools) manages workspace root and approval policy
#: through module-level globals. Concurrent /execute requests would race on
#: that shared state, so we serialize them with a lock — the smallest
#: appropriate server-side mechanism that avoids redesigning ARCHESTRATOR.
_EXECUTION_LOCK = threading.Lock()


def _rosie_version() -> str:
    """Return the installed ROSIE wrapper version."""
    try:
        from wrapper import __version__
        return __version__
    except Exception:
        return "unknown"


def _handle_execute(self, body: dict) -> tuple[dict, int]:
    """Validate an /execute request body and run HACKASS.

    Returns (response_dict, http_status).
    """
    prompt = body.get("prompt")

    if not isinstance(prompt, str):
        return ({"status": "error", "error": "invalid_prompt"}, 400)

    if not prompt.strip():
        return ({"status": "error", "error": "invalid_prompt"}, 400)

    try:
        from hackass.agent import run_hackass
    except ImportError as exc:
        self._log(f"HACKASS import error: {exc}")
        return ({"status": "error", "error": "execution_failed"}, 500)

    try:
        with _EXECUTION_LOCK:
            result = run_hackass(
                workspace=_WORKSPACE,
                prompt=prompt,
            )
    except Exception as exc:
        self._log(f"Execution failed: {exc}")
        self._log(traceback.format_exc())
        return ({"status": "error", "error": "execution_failed"}, 500)

    return ({"status": "ok", "result": result}, 200)


class _Handler(BaseHTTPRequestHandler):
    """Request handler for health and ROSIE execution endpoints."""

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json({"status": "ok", "rosie_version": _rosie_version()})
        else:
            self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        if self.path != "/execute":
            self._json({"error": "not found"}, status=404)
            return

        # --- Phase 3: Request validation ---

        # Enforce a request-body size limit before reading.
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._json({"status": "error", "error": "invalid_content_length"}, status=411)
            return

        if content_length <= 0:
            self._json({"status": "error", "error": "invalid_content_length"}, status=411)
            return

        if content_length > _MAX_BODY_BYTES:
            self._json({"status": "error", "error": "payload_too_large"}, status=413)
            return

        raw = self.rfile.read(content_length)

        # Parse JSON.
        try:
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json({"status": "error", "error": "invalid_json"}, status=400)
            return

        if not isinstance(body, dict):
            self._json({"status": "error", "error": "invalid_json"}, status=400)
            return

        # The browser supplies only the prompt; no overrides allowed.
        result, status = _handle_execute(self, body)
        self._json(result, status=status)

    def _json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _log(self, msg: str) -> None:
        print(f"[rosie-server] {msg}")

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.address_string()}] {fmt % args}")


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    print(f"[rosie-server] listening on port {port}")
    print(f"[rosie-server] executing in workspace: {_WORKSPACE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
