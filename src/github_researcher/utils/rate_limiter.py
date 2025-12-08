"""Rate limiter for GitHub API requests."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console

console = Console()


@dataclass
class RateLimitState:
    """Track rate limit state for an API."""

    limit: int
    remaining: int
    reset_time: float  # Unix timestamp
    window_seconds: int = 3600  # Default 1 hour

    @property
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining <= 0

    @property
    def seconds_until_reset(self) -> float:
        """Get seconds until rate limit resets."""
        return max(0, self.reset_time - time.time())

    def update_from_headers(self, headers: dict) -> None:
        """Update state from GitHub API response headers."""
        if "x-ratelimit-limit" in headers:
            self.limit = int(headers["x-ratelimit-limit"])
        if "x-ratelimit-remaining" in headers:
            self.remaining = int(headers["x-ratelimit-remaining"])
        if "x-ratelimit-reset" in headers:
            self.reset_time = float(headers["x-ratelimit-reset"])


@dataclass
class RateLimiter:
    """Rate limiter supporting REST, Search, and GraphQL APIs."""

    # REST API: 5000/hour authenticated, 60/hour unauthenticated
    rest: RateLimitState = field(
        default_factory=lambda: RateLimitState(
            limit=5000, remaining=5000, reset_time=time.time() + 3600
        )
    )

    # Search API: 30/minute (separate from REST)
    search: RateLimitState = field(
        default_factory=lambda: RateLimitState(
            limit=30, remaining=30, reset_time=time.time() + 60, window_seconds=60
        )
    )

    # GraphQL API: 5000 points/hour
    graphql: RateLimitState = field(
        default_factory=lambda: RateLimitState(
            limit=5000, remaining=5000, reset_time=time.time() + 3600
        )
    )

    # Lock for thread safety
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire_rest(self, cost: int = 1) -> None:
        """Acquire permission for a REST API request."""
        await self._acquire(self.rest, cost, "REST")

    async def acquire_search(self, cost: int = 1) -> None:
        """Acquire permission for a Search API request."""
        await self._acquire(self.search, cost, "Search")

    async def acquire_graphql(self, cost: int = 1) -> None:
        """Acquire permission for a GraphQL API request."""
        await self._acquire(self.graphql, cost, "GraphQL")

    async def _acquire(self, state: RateLimitState, cost: int, api_name: str) -> None:
        """Acquire permission for an API request, waiting if necessary."""
        async with self._lock:
            # Check if we need to wait for reset
            if state.remaining < cost:
                wait_time = state.seconds_until_reset
                if wait_time > 0:
                    console.print(
                        f"[yellow]Rate limit reached for {api_name} API. "
                        f"Waiting {wait_time:.1f}s until reset...[/yellow]"
                    )
                    await asyncio.sleep(wait_time + 1)  # Add 1s buffer
                    # Reset the state after waiting
                    state.remaining = state.limit
                    state.reset_time = time.time() + state.window_seconds

            # Deduct the cost
            state.remaining -= cost

    def update_rest_from_headers(self, headers: dict) -> None:
        """Update REST rate limit state from response headers."""
        self.rest.update_from_headers(headers)

    def update_search_from_headers(self, headers: dict) -> None:
        """Update Search rate limit state from response headers."""
        self.search.update_from_headers(headers)

    def update_graphql_from_headers(self, headers: dict) -> None:
        """Update GraphQL rate limit state from response headers."""
        self.graphql.update_from_headers(headers)

    def get_status(self) -> dict:
        """Get current rate limit status for all APIs."""
        return {
            "rest": {
                "remaining": self.rest.remaining,
                "limit": self.rest.limit,
                "reset_in": self.rest.seconds_until_reset,
            },
            "search": {
                "remaining": self.search.remaining,
                "limit": self.search.limit,
                "reset_in": self.search.seconds_until_reset,
            },
            "graphql": {
                "remaining": self.graphql.remaining,
                "limit": self.graphql.limit,
                "reset_in": self.graphql.seconds_until_reset,
            },
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (useful for testing)."""
    global _rate_limiter
    _rate_limiter = None
