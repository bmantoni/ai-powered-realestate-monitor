"""Tests for retry and circuit breaker utilities."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils import CircuitBreaker, CircuitBreakerOpen, retry_with_backoff


# =============================================================================
# retry_with_backoff tests
# =============================================================================


class TestRetryWithBackoff:
    """Test suite for the retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        """When the function succeeds immediately, no retries occur."""
        mock_fn = AsyncMock(return_value="success")

        result = await retry_with_backoff(mock_fn, max_retries=3)

        assert result == "success"
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        """When the function fails then succeeds, retries should occur."""
        mock_fn = AsyncMock(side_effect=[RuntimeError("fail 1"), RuntimeError("fail 2"), "success"])

        result = await retry_with_backoff(mock_fn, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert mock_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_exhausted(self):
        """When all retries fail, the last exception should be raised."""
        mock_fn = AsyncMock(side_effect=RuntimeError("persistent failure"))

        with pytest.raises(RuntimeError, match="persistent failure"):
            await retry_with_backoff(mock_fn, max_retries=2, base_delay=0.01)

        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_for_non_retryable_exception(self):
        """When a non-retryable exception is raised, it should not retry."""
        mock_fn = AsyncMock(side_effect=ValueError("bad input"))

        with pytest.raises(ValueError, match="bad input"):
            await retry_with_backoff(mock_fn, max_retries=3, retryable_exceptions=(RuntimeError,))

        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        """The wrapped function should receive all positional and keyword args."""
        mock_fn = AsyncMock(return_value=42)

        result = await retry_with_backoff(mock_fn, "pos", key="val", max_retries=1)

        assert result == 42
        mock_fn.assert_called_once_with("pos", key="val")

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Delays should follow exponential backoff pattern."""
        mock_fn = AsyncMock(side_effect=[RuntimeError("fail"), "success"])
        delays: list[float] = []

        async def tracking_sleep(delay: float) -> None:
            delays.append(delay)

        result = await retry_with_backoff(
            mock_fn, max_retries=3, base_delay=0.1, _sleep=tracking_sleep
        )

        assert result == "success"
        assert len(delays) == 1
        assert delays[0] == pytest.approx(0.1, rel=1e-3)

    @pytest.mark.asyncio
    async def test_second_retry_has_longer_delay(self):
        """The second retry should have double the base delay."""
        mock_fn = AsyncMock(side_effect=[RuntimeError("1"), RuntimeError("2"), "success"])
        delays: list[float] = []

        async def tracking_sleep(delay: float) -> None:
            delays.append(delay)

        await retry_with_backoff(mock_fn, max_retries=3, base_delay=0.05, _sleep=tracking_sleep)

        assert len(delays) == 2
        assert delays[0] == pytest.approx(0.05, rel=1e-3)
        assert delays[1] == pytest.approx(0.10, rel=1e-3)


# =============================================================================
# CircuitBreaker tests
# =============================================================================


class TestCircuitBreaker:
    """Test suite for the CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """A fresh circuit breaker should be closed (allowing calls)."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "closed"
        assert cb.can_call() is True

    def test_records_success(self):
        """A successful call should not affect the failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_records_failure(self):
        """Recording a failure should increment the failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == "closed"

    def test_opens_after_threshold_failures(self):
        """After N failures, the circuit should open."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_call() is False

    def test_open_circuit_raises_on_call(self):
        """Calling an open circuit should raise CircuitBreakerOpen."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()

        with pytest.raises(CircuitBreakerOpen):
            cb.call_or_raise(lambda: "result")

    def test_closed_circuit_allows_call(self):
        """A closed circuit should execute the callable and return its result."""
        cb = CircuitBreaker(failure_threshold=3)
        result = cb.call_or_raise(lambda: 42)
        assert result == 42

    def test_success_resets_failure_count(self):
        """A success after failures should reset the failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_half_open_after_timeout(self):
        """After the recovery timeout, the circuit should transition to half-open."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        assert cb.state == "open"
        # After timeout, should be half-open
        assert cb.can_call() is True
        assert cb.state == "half_open"

    def test_half_open_success_closes_circuit(self):
        """A success in half-open state should close the circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        # Transition to half-open
        assert cb.can_call() is True
        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_failure_reopens_circuit(self):
        """A failure in half-open state should reopen the circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        # Transition to half-open
        assert cb.can_call() is True
        cb.record_failure()
        assert cb.state == "open"

    def test_async_wrap(self):
        """The async_wrap method should create an async wrapper."""
        cb = CircuitBreaker(failure_threshold=3)
        async def my_func():
            return "async result"

        wrapped = cb.async_wrap(my_func)
        assert asyncio.iscoroutinefunction(wrapped)

    @pytest.mark.asyncio
    async def test_async_wrap_allows_call_when_closed(self):
        """Async wrapper should execute when circuit is closed."""
        cb = CircuitBreaker(failure_threshold=3)
        async def my_func():
            return "async result"

        wrapped = cb.async_wrap(my_func)
        result = await wrapped()
        assert result == "async result"

    @pytest.mark.asyncio
    async def test_async_wrap_raises_when_open(self):
        """Async wrapper should raise when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()

        async def my_func():
            return "async result"

        wrapped = cb.async_wrap(my_func)
        with pytest.raises(CircuitBreakerOpen):
            await wrapped()

    def test_str_representation(self):
        """String representation should include state and failure count."""
        cb = CircuitBreaker(failure_threshold=5)
        assert "closed" in str(cb)
        assert "0/5" in str(cb)

        cb.record_failure()
        assert "1/5" in str(cb)
