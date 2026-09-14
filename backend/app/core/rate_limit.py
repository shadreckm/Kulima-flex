"""Small in-process IP rate limiter for a single Render instance."""

from collections import defaultdict
import os
from threading import Lock
import time

from fastapi.responses import JSONResponse


def check_rate_limit(user_id: str, endpoint: str) -> None:
    """Compatibility hook; enforcement is performed by RateLimitMiddleware."""
    return


class RateLimitMiddleware:
    protected_prefixes = (
        "/api/v1/ask",
        "/api/v1/documents",
        "/api/v1/intelligence",
        "/api/v1/signals",
    )

    def __init__(self, app):
        self.app = app
        self.limit = max(1, int(os.environ.get("KULIMA_RATE_LIMIT_REQUESTS", "60")))
        self.window_seconds = max(1, int(os.environ.get("KULIMA_RATE_LIMIT_WINDOW_SECONDS", "60")))
        self.requests = defaultdict(list)
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith(self.protected_prefixes):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self.lock:
            recent = [timestamp for timestamp in self.requests[client_ip] if timestamp > cutoff]
            if len(recent) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - recent[0])))
                self.requests[client_ip] = recent
                response = JSONResponse(
                    status_code=429,
                    content={"error": True, "message": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return
            recent.append(now)
            self.requests[client_ip] = recent

        await self.app(scope, receive, send)
