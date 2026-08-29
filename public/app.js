/**
 * ROSIE web interface — application shell.
 *
 * Responsibilities:
 *   - verify backend connectivity via GET /health
 *   - display actual backend availability state
 *   - submit user tasks via POST /execute
 *   - display actual HACKASS results
 *
 * This script does NOT:
 *   - invent chat API calls
 *   - display fake conversations or tool activity
 *   - fabricate model responses
 */

(function () {
  "use strict";

  const statusEl = document.getElementById("backend-status");
  const form = document.getElementById("input-form");
  const input = document.getElementById("prompt-input");
  const conversationEl = document.getElementById("conversation");
  const submitBtn = form.querySelector('button[type="submit"]');

  /**
   * Append a message to the conversation area.
   */
  function appendMessage(label, text, isError = false) {
    const msg = document.createElement("div");
    msg.className = "message";
    if (isError) {
      msg.classList.add("message-error");
      msg.textContent = text;
    } else {
      const labelEl = document.createElement("span");
      labelEl.className = "message-label";
      labelEl.textContent = label + ":";
      const textEl = document.createElement("span");
      textEl.className = "message-text";
      textEl.textContent = text;
      msg.appendChild(labelEl);
      msg.appendChild(textEl);
    }
    conversationEl.appendChild(msg);
    conversationEl.scrollTop = conversationEl.scrollHeight;
  }

  /**
   * Replace the placeholder and show a working indicator.
   */
  function setWorkingState(show) {
    const placeholder = conversationEl.querySelector(".placeholder");
    if (placeholder) {
      placeholder.style.display = show ? "none" : "block";
    }
    submitBtn.disabled = show;
    input.disabled = show;
    if (show) {
      appendMessage("ROSIE", "is working...");
    }
  }

  function setReadyState() {
    submitBtn.disabled = false;
    input.disabled = false;
  }

  /**
   * Submit the user's prompt to POST /execute.
   */
  async function submitTask(promptText) {
    setWorkingState(true);

    try {
      const response = await fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: promptText }),
        signal: AbortSignal.timeout ? AbortSignal.timeout(120000) : undefined,
      });

      const data = await response.json();

      if (data.status === "ok") {
        appendMessage("Result", data.result || "(empty response)");
      } else {
        appendMessage("Error", data.error || "Execution failed", true);
      }
    } catch (err) {
      appendMessage("Error", "Request failed: " + (err.message || "unknown"), true);
    } finally {
      setWorkingState(false);
      setReadyState();
    }
  }

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

  // Handle form submission.
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const promptText = input.value.trim();
    if (!promptText) {
      return;
    }
    appendMessage("You", promptText);
    input.value = "";
    submitTask(promptText);
  });

  // Run once on load and retry every 10 seconds.
  checkBackendHealth();
  setInterval(checkBackendHealth, 10000);
})();
