/**
 * ROSIE web interface — application shell.
 *
 * Phase purpose:
 *   - verify backend connectivity via GET /health
 *   - display actual backend availability state
 *   - reserve space for future interaction (currently disabled)
 *
 * This script does NOT:
 *   - send model requests
 *   - invent chat API calls
 *   - display fake conversations or tool activity
 */

(function () {
  "use strict";

  const statusEl = document.getElementById("backend-status");
  const form = document.getElementById("input-form");
  const input = document.getElementById("prompt-input");

  /**
   * Fetch the backend health endpoint through Firebase Hosting.
   * Updates the status indicator with the actual response or an error.
   */
  async function checkBackendHealth() {
    try {
      const response = await fetch("/health", {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: AbortSignal.timeout ? AbortSignal.timeout(10000) : undefined,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (data.status === "ok") {
        statusEl.textContent = `Backend: Online (v${data.rosie_version || "unknown"})`;
        statusEl.className = "status-indicator online";
      } else {
        throw new Error("Unexpected health response");
      }
    } catch (err) {
      statusEl.textContent = `Backend: Unavailable`;
      statusEl.className = "status-indicator offline";
    }
  }

  // Run once on load and retry every 10 seconds.
  checkBackendHealth();
  setInterval(checkBackendHealth, 10000);
})();
