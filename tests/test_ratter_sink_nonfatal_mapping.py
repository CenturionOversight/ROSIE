"""Focused regression for RATTER's never-raise telemetry boundary."""

from wrapper.ratter_sink import RatterSink


class _MalformedEvent:
    """Missing the PeepEvent fields required by the mapper."""


def test_send_peep_events_mapping_failure_is_nonfatal():
    sink = RatterSink(enabled=False)

    assert sink.send_peep_events([_MalformedEvent()]) is False
