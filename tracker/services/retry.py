"""Shared retry policy for third-party HTTP / SDK calls (rate limits, transient errors)."""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from django.conf import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def call_with_retries(
    fn: Callable[[], T],
    *,
    operation: str,
    retry_on: tuple[type[BaseException], ...],
) -> T:
    """
    Exponential backoff with jitter. Retries on any exception in ``retry_on``
    up to ``settings.API_MAX_RETRIES`` attempts.
    """
    max_attempts = max(1, settings.API_MAX_RETRIES)
    base = max(0.1, settings.API_RETRY_BASE_SECONDS)
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except retry_on as exc:
            last_exc = exc
            if attempt >= max_attempts:
                logger.warning("%s failed after %s attempts: %s", operation, attempt, exc)
                raise
            delay = base * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            logger.info(
                "%s attempt %s/%s error (%s); retrying in %.2fs",
                operation,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
