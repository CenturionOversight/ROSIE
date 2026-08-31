"""Constructor contract tests for AsyncRatterSink bounds."""

import pytest

from wrapper.ratter_async import AsyncRatterSink


def test_queue_size_must_be_positive():
    with pytest.raises(ValueError, match="queue_size must be at least 1"):
        AsyncRatterSink(queue_size=0, auto_start=False)


def test_batch_size_must_be_positive():
    with pytest.raises(ValueError, match="batch_size must be at least 1"):
        AsyncRatterSink(batch_size=0, auto_start=False)
