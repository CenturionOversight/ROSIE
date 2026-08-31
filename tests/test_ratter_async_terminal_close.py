"""Focused regression tests for terminal AsyncRatterSink shutdown."""

from wrapper.ratter_async import AsyncRatterSink


class _ImmediateSink:
    def send_peep_events(self, events, command_id=None, task_id=None):
        return True


def _fake_event():
    class FakeEvent:
        pass

    return FakeEvent()


def test_start_after_close_does_not_reopen_sink():
    sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
    assert sink.close(timeout=2.0) is True

    sink.start()

    assert sink.send_peep_events([_fake_event()]) is False
    assert sink._closed is True


def test_start_after_close_does_not_spawn_new_worker():
    sink = AsyncRatterSink(sink=_ImmediateSink(), auto_start=True)
    assert sink.close(timeout=2.0) is True
    old_worker = sink._worker

    sink.start()

    assert sink._worker is old_worker
    assert old_worker is not None and not old_worker.is_alive()
