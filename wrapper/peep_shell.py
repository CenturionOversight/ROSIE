"""PEEP-backed shell executor for local ROSIE execution.

This module bridges PEEP's PowerShell execution into the ARCHESTRATOR tool layer
for local CLI use. It is NOT a Cloud Run / HACKASS dependency — PEEP is imported
lazily here so that environments without PEEP installed continue to work via the
default executor.

One command per PEEP session is used for this demo integration. This avoids
solving persistent multi-command correlation at this stage.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from peep.command import COMMAND_STATE_CREATED, PeepCommand
from peep.events import (
    COMMAND_COMPLETED,
    COMMAND_OBSERVED,
    OUTPUT_STDERR,
    OUTPUT_STDOUT,
    PROCESS_EXITED,
    SESSION_ENDED,
    SESSION_STARTED,
    PeepEvent,
)
from peep.factory import EventFactory
from peep.powershell import PowerShellAdapter
from peep.session import SESSION_STATE_ACTIVE, PeepSession

__all__ = ["PeepShellExecutor"]


def _get_ratter_sink():
    """Lazily import and instantiate the asynchronous RatterSink.

    Returns None if the module or RATTER is unavailable, so that
    PEEP execution is never blocked by RATTER presence.  The returned sink
    forwards events on a background worker thread so HTTP telemetry latency
    never sits on the command-execution path.
    """
    try:
        from wrapper.ratter_async import AsyncRatterSink
        return AsyncRatterSink()
    except Exception:
        return None


class PeepShellExecutor:
    """Shell executor that runs commands through PEEP's PowerShell adapter.

    Creates a single PEEP session per execute() call. Events are polled
    from the adapter and translated into ROSIE's existing shell result format.
    """

    def __init__(self, cwd: str | Path | None = None) -> None:
        self._cwd = str(Path(cwd).resolve()) if cwd is not None else None
        self._ratter_sink = _get_ratter_sink()

    def __call__(self, command: str, timeout: Optional[int] = 30) -> str:
        """Execute a shell command through PEEP PowerShell.

        Allows PeepShellExecutor to be used as the shell executor callable
        expected by :func:`wrapper.tools.run_shell`.
        """
        return self.execute(command, timeout)

    def execute(self, command: str, timeout: Optional[int] = 30) -> str:
        """Execute a shell command through PEEP PowerShell and return ROSIE format.

        Args:
            command: The shell command to execute.
            timeout: Maximum execution time in seconds (default 30).

        Returns:
            A formatted block with $ command, STDOUT, STDERR, and EXIT_CODE.
        """
        from wrapper.output_bounds import format_shell_result
        from wrapper.rt_context import get_current_task_id

        task_id = get_current_task_id()

        session_id = f"rosie-{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        session = PeepSession(
            session_id=session_id,
            created_at=now,
            last_activity_at=now,
            state=SESSION_STATE_ACTIVE,
        )
        event_factory = EventFactory(
            session_id=session_id,
            source_type="rosie",
            source_id="rosie-cli",
        )
        adapter = PowerShellAdapter(
            session=session,
            event_factory=event_factory,
            cwd=self._cwd,
        )

        command_id = uuid4().hex[:12]
        command_obj = PeepCommand(
            command_id=command_id,
            session_id=session_id,
            command_text=command,
            created_at=now,
            state=COMMAND_STATE_CREATED,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        exit_code: Optional[int] = None
        completed = False
        timed_out = False
        command_id_for_ratter: Optional[str] = None

        def _forward_to_ratter(events: list[PeepEvent]) -> None:
            """Forward PEEP events to RATTER (async, never blocking). Never raises."""
            if self._ratter_sink is None or not events:
                return
            nonlocal command_id_for_ratter
            for e in events:
                if e.event_type == COMMAND_OBSERVED:
                    command_id_for_ratter = e.payload.get("command_id")
                elif e.event_type == COMMAND_COMPLETED:
                    if command_id_for_ratter is None:
                        command_id_for_ratter = e.payload.get("command_id")
            try:
                self._ratter_sink.send_peep_events(
                    events,
                    command_id=command_id_for_ratter,
                    task_id=task_id,
                )
            except Exception:
                pass

        try:
            adapter.start()
            adapter.submit(command_obj)

            deadline = time.monotonic() + (timeout or 30)

            while not completed:
                events = adapter.poll()
                _forward_to_ratter(events)
                for event in events:
                    stdout_lines.extend(self._collect_stdout(event))
                    stderr_lines.extend(self._collect_stderr(event))
                    if event.event_type == COMMAND_COMPLETED:
                        exit_code = event.payload.get("exit_code")
                        completed = True
                    elif event.event_type == PROCESS_EXITED:
                        if exit_code is None:
                            exit_code = event.payload.get("exit_code")
                        completed = True
                    elif event.event_type == SESSION_ENDED:
                        pass

                if not completed:
                    if time.monotonic() >= deadline:
                        timed_out = True
                        break
                    time.sleep(0.05)

            if timed_out:
                exit_code = -1
            elif exit_code is None:
                exit_code = 0 if completed else -1

            # Drain any remaining output after completion.
            remaining = adapter.poll()
            _forward_to_ratter(remaining)
            for event in remaining:
                stdout_lines.extend(self._collect_stdout(event))
                stderr_lines.extend(self._collect_stderr(event))
        finally:
            adapter.stop()

        return format_shell_result(
            command,
            stdout="\n".join(stdout_lines).rstrip(),
            stderr="\n".join(stderr_lines).rstrip(),
            exit_code=exit_code if exit_code is not None else -1,
            timed_out=timed_out,
            timeout_seconds=timeout or 30,
        )

    def _collect_stdout(self, event: PeepEvent) -> list[str]:
        if event.event_type == OUTPUT_STDOUT:
            return [event.payload.get("text", "")]
        return []

    def _collect_stderr(self, event: PeepEvent) -> list[str]:
        if event.event_type == OUTPUT_STDERR:
            return [event.payload.get("text", "")]
        return []
