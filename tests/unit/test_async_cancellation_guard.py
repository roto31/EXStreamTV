"""
Unit tests for AsyncCancellationGuard and graceful shutdown.

Verifies: protect, safe_lock, cancel_and_wait, shutdown state.
"""

import asyncio

import pytest

from exstreamtv.core.async_guard import AsyncCancellationGuard
from exstreamtv.core.shutdown_state import is_shutting_down, set_shutting_down


@pytest.mark.asyncio
async def test_protect_suppress_returns_none_on_cancel():
    """protect with suppress=True returns None when cancelled."""
    async def slow():
        await asyncio.sleep(60)

    task = asyncio.create_task(
        AsyncCancellationGuard.protect(slow(), name="slow", suppress=True)
    )
    await asyncio.sleep(0.01)
    task.cancel()
    result = await task
    assert result is None


@pytest.mark.asyncio
async def test_protect_no_suppress_reraises_cancel():
    """protect with suppress=False re-raises CancelledError."""
    async def slow():
        await asyncio.sleep(60)

    task = asyncio.create_task(
        AsyncCancellationGuard.protect(slow(), name="slow", suppress=False)
    )
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_safe_lock_logs_on_cancel():
    """safe_lock re-raises CancelledError cleanly (no stack trace)."""
    lock = asyncio.Lock()
    # Acquire from another task first
    async def hold():
        async with lock:
            await asyncio.sleep(10)

    holder = asyncio.create_task(hold())
    await asyncio.sleep(0.01)  # Let holder acquire

    async def acquire_and_wait():
        async with AsyncCancellationGuard.safe_lock(lock, name="test_lock"):
            pass

    waiter = asyncio.create_task(acquire_and_wait())
    await asyncio.sleep(0.01)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    holder.cancel()
    try:
        await holder
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_cancel_and_wait_suppresses():
    """cancel_and_wait suppresses CancelledError."""
    async def run_forever():
        while True:
            await asyncio.sleep(1)

    task = asyncio.create_task(run_forever())
    await AsyncCancellationGuard.cancel_and_wait(task, timeout=2.0, name="forever")
    assert task.cancelled() or task.done()


def test_shutdown_state():
    """Shutdown state can be set and read."""
    set_shutting_down(False)
    assert not is_shutting_down()
    set_shutting_down(True)
    assert is_shutting_down()
    set_shutting_down(False)  # Reset for other tests
