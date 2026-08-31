"""Asynchronous RATTER event forwarding for PEEP telemetry.

The synchronous :class:`~wrapper.ratter_sink.RatterSink` performs a blocking
HTTP POST to RATTER on the calling thread.  Because PEEP events are produced
on the execution-critical path while a shell command runs, that HTTP round
trip adds latency to command execution.

:class:`AsyncRatterSink` removes that latency from the execution path:

- a bounded in-memory queue accepts events from the calling thread;
- a single daemon worker thread drains the queue and forwards batches to
  RATTER in the background;
- enqueue is non-blocking: if the queue is full the events are dropped (with a
  log line) rather than blocking the caller;
- worker failures are caught and logged — never propagated to the caller;
- :meth:`flush` waits (bounded) for the worker to actually drain the pending
  events and returns a ``bool`` reporting whether it drained in time, leaving
  the worker alive for future events;
- :meth:`close` performs a bounded graceful shutdown — stop accepting new
  telemetry, best-effort flush, then stop the worker — logging anything that
  cannot be sent before returning without blocking indefinitely.  It is
  idempotent and never raises.

The sink is still best-effort telemetry.  Dropping events, a full queue, or
an unreachable RATTER must never break command execution.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Iterable

from peep.events import PeepEvent

from wrapper.ratter_sink import RatterSink

__all__ = ["AsyncRatterSink"]

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 5000
DEFAULT_BATCH_SIZE = 50
_WORKER_JOIN_TIMEOUT_SECONDS = 2.0

# Sentinel pushed onto the queue to ask the worker to stop.  It is deliberately
# *not* counted against outstanding pending telemetry.
_SENTINEL: Any = None


class AsyncRatterSink:
    """Background-draining wrapper around a synchronous :class:`RatterSink`.

    Provides the same :meth:`send_peep_events` surface used by the PEEP shell
    executor, but enqueues the work instead of performing the HTTP call inline.

    Drain accounting: every accepted item increments an internal
    ``outstanding`` counter which the worker decrements only after that item's
    batches have all been sent.  :meth:`flush` and :meth:`close` watch this
    counter (via a condition), so they truly wait for background sends to finish
    rather than merely joining an eternally-alive worker thread.
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

        self._lock = threading.Lock()
        self._drain_cond = threading.Condition(self._lock)
        self._outstanding = 0

        if auto_start:
            self.start()

    # ------------------------------------------------------------------
    # Internal drain accounting
    # ------------------------------------------------------------------

    def _note_processed(self) -> None:
        """Record one fully-processed item and wake any flusher."""
        with self._drain_cond:
            self._outstanding -= 1
            self._drain_cond.notify_all()

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
        """Drain the queue and forward batches until a sentinel is received.

        Every dequeued telemetry item is counted as accepted on the way in and
        counted as processed once its batches have all been forwarded, so
        :meth:`flush` can wait on a true drain rather than a thread join.
        """
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

            try:
                events, command_id, task_id = item
                # Split oversized batches at the queue-item level.
                for start in range(0, len(events), self._batch_size):
                    self._send_batch(
                        events[start : start + self._batch_size],
                        command_id,
                        task_id,
                    )
            finally:
                self._note_processed()

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
        queue, ``False`` if the sink is closed or the queue is full and the
        events were dropped.

        Outstanding accounting is atomic with respect to enqueue: the counter
        is incremented *before* the queue put, and rolled back if the put
        fails, so the worker can never observe negative outstanding state.
        """
        batch = list(events)
        if not batch:
            return True

        with self._drain_cond:
            if self._closed:
                return False

            self._outstanding += 1
            try:
                self._queue.put_nowait((batch, command_id, task_id))
            except queue.Full:
                self._outstanding -= 1
                self._drain_cond.notify_all()
                logger.warning(
                    "RATTER async queue full; dropping %d PEEP events", len(batch)
                )
                return False

        return True

    def flush(self, timeout: float = _WORKER_JOIN_TIMEOUT_SECONDS) -> bool:
        """Wait (bounded) for the worker to drain all pending events.

        Unlike a plain thread join, this actually waits for each accepted item
        to be *processed* by the worker, then returns promptly once drained.
        It never blocks indefinitely and leaves the worker alive for future
        events.

        Returns:
            ``True`` if the queue drained within *timeout*, ``False`` if
            pending events remained when the deadline elapsed.
        """
        deadline = time.monotonic() + timeout
        with self._drain_cond:
            while self._outstanding > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._drain_cond.wait(timeout=remaining)
            return True

    def close(self, timeout: float = _WORKER_JOIN_TIMEOUT_SECONDS) -> bool:
        """Stop the worker after a bounded, graceful shutdown.

        Uses a single monotonic deadline for the entire shutdown sequence:
        stop accepting, flush pending work, signal worker, join worker.
        All stages share one time budget so the total wall time is bounded
        by *timeout* (plus a negligible scheduling overhead), never ~2x.

        Never blocks indefinitely and never raises.  Idempotent: repeated
        calls are safe and return the same drained status.

        Returns:
            ``True`` if all accepted telemetry was forwarded before shutdown,
            ``False`` if some pending events could not be sent (these are
            logged explicitly).
        """
        deadline = time.monotonic() + max(0, timeout)

        if self._closed:
            return self._outstanding == 0

        with self._lock:
            self._closed = True

        # Best-effort flush with remaining time.
        remaining = max(0, deadline - time.monotonic())
        drained = self.flush(timeout=remaining)

        # Signal worker shutdown.
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:  # pragma: no cover - defensive
            pass

        # Join worker with remaining time.
        if self._worker is not None and self._worker.is_alive():
            remaining = max(0, deadline - time.monotonic())
            self._worker.join(timeout=remaining)

        pending = self._queue.qsize()
        if self._outstanding > 0 or pending > 0:
            logger.warning(
                "RATTER async close: %d queued item(s) and %d outstanding "
                "event item(s) not forwarded during shutdown",
                pending,
                self._outstanding,
            )
            return False
        return True