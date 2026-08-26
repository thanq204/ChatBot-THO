"""Small per-account rate limits for expensive dashboard operations.

This is deliberately process-local: the current deployment runs one replica,
and protecting model/network calls before they start is more important than
adding another external dependency. A multi-replica deployment should replace
this adapter with Redis while keeping the route dependencies unchanged.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from backend.models.auth import UserPublic
from backend.services.auth_service import current_user


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, scope: str, identity: str, *, limit: int, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        key = (scope, identity)
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])) + 1)
                return retry_after
            events.append(now)
            # Avoid retaining identities that have been inactive for a long
            # time. This scan is bounded by the number of currently used keys.
            if len(self._events) > 2_000:
                stale = [item for item, values in self._events.items() if not values or values[-1] <= cutoff]
                for item in stale:
                    self._events.pop(item, None)
        return 0


_limiter = SlidingWindowRateLimiter()


def rate_limit(scope: str, *, limit: int, window_seconds: int = 60) -> Callable[..., UserPublic]:
    """Return a FastAPI dependency that authenticates and throttles a user."""

    def dependency(user: UserPublic = Depends(current_user)) -> UserPublic:
        retry_after = _limiter.check(
            scope,
            str(user.user_id),
            limit=limit,
            window_seconds=window_seconds,
        )
        if retry_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Bạn thao tác quá nhanh. Hãy thử lại sau {retry_after} giây.",
                headers={"Retry-After": str(retry_after)},
            )
        return user

    return dependency
