from wrapper.ratter_async import AsyncRatterSink


def test_closed_sink_rejects_empty_event_batch():
    sink = AsyncRatterSink(auto_start=True)
    sink.close(timeout=2.0)
    assert sink.send_peep_events([]) is False
