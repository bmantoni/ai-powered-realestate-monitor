"""Utility functions for retries and circuit breaker pattern."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")


class CircuitBreakerOpen(Exception):
    """Raised when a circuit breaker is open and a call is attempted."""

    pass


class CircuitBreaker:
    """Simple circuit breaker for protecting external service calls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "closed"  # closed, open, half_open

    def can_call(self) -> bool:
        """Return True if the circuit allows a call."""
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.last_failure_time is not None:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = "half_open"
                    return True
            return False
        # half_open
        return True

    def record_success(self) -> None:
        """Record a successful call."""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def call_or_raise(self, fn: Callable[[], T]) -> T:
        """Execute *fn* if the circuit is closed, otherwise raise."""
        if not self.can_call():
            raise CircuitBreakerOpen(f"Circuit is {self.state}")
        try:
            result = fn()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def async_wrap(
        self, fn: Callable[..., Coroutine[Any, Any, T]]
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        """Wrap an async function with circuit breaker logic."""
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if not self.can_call():
                raise CircuitBreakerOpen(f"Circuit is {self.state}")
            try:
                result = await fn(*args, **kwargs)
                self.record_success()
                return result
            except Exception:
                self.record_failure()
                raise

        return wrapper

    def __str__(self) -> str:
        return f"CircuitBreaker(state={self.state}, failures={self.failure_count}/{self.failure_threshold})"


async def retry_with_backoff(
    fn: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    _sleep: Callable[[float], Coroutine[Any, Any, None]] | None = None,
    **kwargs: Any,
) -> T:
    """Call an async function with exponential backoff retry logic."""
    sleep_fn = _sleep or asyncio.sleep
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exception = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                await sleep_fn(delay)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Unexpected end of retry_with_backoff")
