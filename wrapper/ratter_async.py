"""Asynchronous RATTER event forwarding for PEEP telemetry.

The synchronous :class:`~wrapper.ratter_sink.RatterSink` performs a blocking
HTTP POST to RATTER on the calling thread.  Because PEEP events are produced
on the execution-critical path while a shell command runs, that HTTP round
trip adds latency to command execution.

:class:`AsyncRatterSink` removes that latency from the execution path:

- a bounded in-memory queue accepts events from the calling thread;
- a single daemon worker thread drains the queue and forwards batches to
  RATTER in the background;
- enqueue is non-blocking: if the queue is full the oldest events are
  dropped (with a log line) rather than blocking the caller;
- worker failures are caught and logged — never propagated to the caller;
- :meth:`flush` / :meth:`close` drain a bounded number of pending events and
  stop the worker.

The sink is still best-effort telemetry.  Dropping events, a full queue, or
an unreachable RATTER must never break command execution.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Iterable

from peep.events import PeepEvent

from wrapper.ratter_sink import RatterSink

__all__ = ["AsyncRatterSink"]

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 5000
DEFAULT_BATCH_SIZE = 50
_WORKER_JOIN_TIMEOUT_SECONDS = 2.0


class AsyncRatterSink:
    """Background-draining wrapper around a synchronous :class:`RatterSink`.

    Provides the same :meth:`send_peep_events` surface used by the PEEP shell
    executor, but enqueues the work instead of performing the HTTP call inline.
    """

    def __init__(
        self,
        sink: RatterSink | None = None,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        auto_start: bool = True,
    ) -> None:
        self._sink = sink if sink is not None else RatterSink()
        self._queue: "queue.Queue[tuple[list[PeepEvent], str | None, str | None] | None]" = (
            queue.Queue(maxsize=queue_size)
        )
        self._batch_size = batch_size
        self._closed = False
        self._worker: threading.Thread | None = None
        if auto_start:
            self.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background worker thread if it is not already running."""
        if self._worker is not None and self._worker.is_alive():
            return
        self._closed = False
        self._worker = threading.Thread(
            target=self._run_worker,
            name="ratter-async-worker",
            daemon=True,
        )
        self._worker.start()

    def _run_worker(self) -> None:
        """Drain the queue and forward batches until a sentinel is received."""
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                if self._closed:
                    return
                continue

            if item is None:
                # Sentinel: the worker has been asked to stop.
                return

            events, command_id, task_id = item
            # Split oversized batches at the queue-item level.
            for start in range(0, len(events), self._batch_size):
                self._send_batch(
                    events[start : start + self._batch_size],
                    command_id,
                    task_id,
                )

    def _send_batch(
        self,
        events: list[PeepEvent],
        command_id: str | None,
        task_id: str | None,
    ) -> None:
        """Forward a batch to RATTER.  Never raises."""
        try:
            self._sink.send_peep_events(events, command_id=command_id, task_id=task_id)
        except Exception:  # pragma: no cover - defensive; sink already swallows
            logger.exception("RATTER async batch failed; %d events dropped", len(events))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_peep_events(
        self,
        events: Iterable[PeepEvent],
        command_id: str | None = None,
        task_id: str | None = None,
    ) -> bool:
        """Enqueue PEEP events for background forwarding.

        Non-blocking.  Returns ``True`` if the events were accepted onto the
        queue, ``False`` if the queue is full and the events were dropped.
        """
        if self._closed:
            return False

        batch = list(events)
        if not batch:
            return True

        try:
            self._queue.put_nowait((batch, command_id, task_id))
        except queue.Full:
            logger.warning(
                "RATTER async queue full; dropping %d PEEP events", len(batch)
            )
            return False
        return True

    def flush(self, timeout: float = _WORKER_JOIN_TIMEOUT_SECONDS) -> int:
        """Best-effort wait for the worker to drain pending events.

        Returns the number of events still left in the queue after *timeout*.
        Does not block indefinitely; a non-zero return means some events were
        not forwarded before the timeout.
        """
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=timeout)
        return self._queue.qsize()

    def close(self, timeout: float = _WORKER_JOIN_TIMEOUT_SECONDS) -> int:
        """Stop the worker after draining a bounded amount of pending work.

        Returns the number of events that remained on the queue (not
        forwarded) when the worker stopped.  Never raises.
        """
        if self._closed:
            return self._queue.qsize()
        self._closed = True
        try:
            self._queue.put_nowait(None)  # sentinel
        except queue.Full:  # pragma: no cover - defensive
            pass
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=timeout)
        return self._queue.qsize()
