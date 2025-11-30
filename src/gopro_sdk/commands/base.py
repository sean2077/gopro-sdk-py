"""Command base classes and decorators."""

__all__ = ["with_http_retry"]

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from ..exceptions import HttpConnectionError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def with_http_retry(
    max_retries: int = 3, backoff_factor: float = 1.0
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """HTTP command retry decorator.

    Automatically retries failed HTTP commands using exponential backoff strategy.

    Args:
        max_retries: Maximum retry count
        backoff_factor: Backoff factor (seconds)

    Returns:
        Decorated function

    Usage example:
        >>> @with_http_retry(max_retries=3, backoff_factor=2.0)
        ... async def my_http_command(self):
        ...     # HTTP command implementation
        ...     pass
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error: HttpConnectionError | None = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except HttpConnectionError as e:
                    last_error = e
                    # Assume first arg is self with _http_error_count
                    if args and hasattr(args[0], "_http_error_count"):
                        args[0]._http_error_count += 1  # type: ignore[union-attr]

                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2**attempt)
                        logger.warning(f"HTTP command failed (attempt {attempt + 1}/{max_retries}): {e}")
                        logger.info(f"Waiting {wait_time:.1f} seconds before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"HTTP command failed (reached maximum retry count {max_retries})")

            assert last_error is not None  # Type guard: last_error is always set if we reach here
            raise last_error

        return wrapper

    return decorator
