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
  idempotent and terminal: a closed sink cannot be restarted.

The sink is still best-effort telemetry.  Dropping events, a full queue, or
an unreachable RATTER must never break command execution.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Iterable
from typing import Any

from peep.events import PeepEvent

from wrapper.ratter_sink import RatterSink

__all__ = ["AsyncRatterSink"]

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 5000
DEFAULT_BATCH_SIZE = 50
_WORKER_JOIN_TIMEOUT_SECONDS = 2.0

_SENTINEL: Any = None


class AsyncRatterSink:
    """Background-draining wrapper around a synchronous :class:`RatterSink`."""

    def __init__(
        self,
        sink: RatterSink | None = None,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        auto_start: bool = True,
    ) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be at least 1")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        self._sink = sink if sink is not None else RatterSink()
        self._queue: queue.Queue[tuple[list[PeepEvent], str | None, str | None] | None] = (
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

    def _note_processed(self) -> None:
        with self._drain_cond:
            self._outstanding -= 1
            self._drain_cond.notify_all()

    def start(self) -> None:
        """Start the background worker once; closed sinks remain closed."""
        with self._lock:
            if self._closed:
                return
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run_worker,
                name="ratter-async-worker",
                daemon=True,
            )
            self._worker.start()

    def _run_worker(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                if self._closed:
                    return
                continue

            if item is None:
                return

            try:
                events, command_id, task_id = item
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
        try:
            self._sink.send_peep_events(events, command_id=command_id, task_id=task_id)
        except Exception:  # pragma: no cover
            logger.exception("RATTER async batch failed; %d events dropped", len(events))

    def send_peep_events(
        self,
        events: Iterable[PeepEvent],
        command_id: str | None = None,
        task_id: str | None = None,
    ) -> bool:
        batch = list(events)

        with self._drain_cond:
            if self._closed:
                return False
            if not batch:
                return True

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
        deadline = time.monotonic() + timeout
        with self._drain_cond:
            while self._outstanding > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._drain_cond.wait(timeout=remaining)
            return True

    def close(self, timeout: float = _WORKER_JOIN_TIMEOUT_SECONDS) -> bool:
        deadline = time.monotonic() + max(0, timeout)

        if self._closed:
            return self._outstanding == 0

        with self._lock:
            self._closed = True

        remaining = max(0, deadline - time.monotonic())
        self.flush(timeout=remaining)

        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:  # pragma: no cover
            pass

        if self._worker is not None and self._worker.is_alive():
            remaining = max(0, deadline - time.monotonic())
            self._worker.join(timeout=remaining)

        with self._queue.mutex:
            pending = sum(1 for item in self._queue.queue if item is not None)
        if self._outstanding > 0 or pending > 0:
            logger.warning(
                "RATTER async close: %d queued item(s) and %d outstanding "
                "event item(s) not forwarded during shutdown",
                pending,
                self._outstanding,
            )
            return False
        return True
