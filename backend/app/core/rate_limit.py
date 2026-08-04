from __future__ import annotations

"""Lightweight hooks for future per-user rate limiting.

For pre-beta, this module provides a single `check_rate_limit` function that
is invoked by protected API endpoints. It currently performs no enforcement
but centralises where rate limiting logic will live in the future.
"""

from typing import Final

import logging

logger = logging.getLogger(__name__)


def check_rate_limit(user_id: str, endpoint: str) -> None:
    """Placeholder for per-user, per-endpoint rate limiting.

    In the beta phase this is a no-op. The function exists so that
    rate limiting can be implemented in one place without changing
    the public behaviour of existing endpoints.

    Args:
        user_id: Authenticated user identifier (from JWT `sub`).
        endpoint: Logical endpoint name (e.g. "intelligence:create").
    """

    # NOTE: Intentionally no enforcement yet. We log at debug level so that
    # future tuning has a trace of traffic shape without affecting behaviour.
    logger.debug("rate_limit_check", extra={"user_id": user_id, "endpoint": endpoint})

    # Future implementation may raise HTTPException with 429 status when
    # limits are exceeded.
    return
