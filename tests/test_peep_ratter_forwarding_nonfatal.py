"""Regression for RATTER telemetry isolation in the PEEP shell executor."""

from wrapper import peep_shell


class _BadPayload:
    def get(self, _key, _default=None):
        raise RuntimeError("malformed telemetry payload")


class _Event:
    def __init__(self, event_type, payload):
        self.event_type = event_type
        self.payload = payload


class _FakeSink:
    def send_peep_events(self, events, command_id=None, task_id=None):
        return True


class _FakeAdapter:
    def __init__(self, **_kwargs):
        self._polls = [
            [_Event(peep_shell.COMMAND_OBSERVED, _BadPayload())],
            [_Event(peep_shell.COMMAND_COMPLETED, {"exit_code": 0})],
            [],
        ]

    def start(self):
        return None

    def submit(self, _command):
        return None

    def poll(self):
        return self._polls.pop(0) if self._polls else []

    def stop(self):
        return None


def test_malformed_ratter_correlation_does_not_break_command(monkeypatch, tmp_path):
    monkeypatch.setattr(peep_shell, "PowerShellAdapter", _FakeAdapter)
    monkeypatch.setattr(peep_shell, "_get_ratter_sink", lambda: _FakeSink())

    executor = peep_shell.PeepShellExecutor(cwd=tmp_path)
    result = executor.execute("Write-Output ok", timeout=1)

    assert "EXIT_CODE: 0" in result
    assert "TIMED_OUT: false" in result
