"""Portable HTTP boundary for ROSIE.

A minimal HTTP server using only the Python standard library.
Binds to the PORT environment variable (as Cloud Run and other
container runtimes provide; defaults to 8080 locally).

Current surface:
  GET /health  ->  {"status": "ok", "rosie_version": "..."}

This layer imports the ROSIE package (wrapper) to verify it is
installed and available, but does not duplicate any agent logic.
HTTP concerns are kept separate from ROSIE's core modules.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

__all__ = ["main"]


class _Handler(BaseHTTPRequestHandler):
    """Request handler for health and future ROSIE endpoints."""

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json({"status": "ok", "rosie_version": _rosie_version()})
        else:
            self._json({"error": "not found"}, status=404)

    def _json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.address_string()}] {fmt % args}")


def _rosie_version() -> str:
    """Return the installed ROSIE wrapper version."""
    try:
        from wrapper import __version__
        return __version__
    except Exception:
        return "unknown"


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    print(f"[rosie-server] listening on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
