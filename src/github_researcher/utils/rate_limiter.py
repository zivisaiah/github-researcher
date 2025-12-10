"""Rate limiter for GitHub API requests."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console

console = Console()


def format_time_remaining(seconds: float) -> str:
    """Format seconds into a human-friendly string."""
    if seconds <= 0:
        return "now"

    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        if secs > 0:
            return f"{minutes} min {secs} sec"
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours} hr {minutes} min"
        return f"{hours} hour{'s' if hours != 1 else ''}"


def format_reset_time(reset_timestamp: float) -> str:
    """Format reset timestamp to a human-readable local time."""
    reset_dt = datetime.fromtimestamp(reset_timestamp)
    return reset_dt.strftime("%H:%M:%S")


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded and we don't want to wait."""

    pass


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
                    human_time = format_time_remaining(wait_time)
                    reset_at = format_reset_time(state.reset_time)
                    console.print(
                        f"\n[red]Rate limit exceeded[/red] for {api_name} API."
                    )
                    console.print(
                        f"[yellow]  Resets in: {human_time} (at {reset_at})[/yellow]"
                    )
                    console.print(
                        f"[dim]  Tip: Set GITHUB_RESEARCHER_TOKEN for 5,000 requests/hour instead of 60[/dim]\n"
                    )
                    raise RateLimitExceededError(
                        f"Rate limit exceeded. Resets in {human_time} (at {reset_at})"
                    )

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


async def check_rate_limit_from_api(
    api_url: str = "https://api.github.com",
    token: Optional[str] = None,
) -> dict:
    """Check current rate limit status from GitHub API.

    Args:
        api_url: GitHub API base URL
        token: Optional GitHub token for authentication

    Returns:
        Dict with rate limit info including remaining and reset time
    """
    import httpx

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-researcher/0.1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/rate_limit", headers=headers)

            if response.status_code == 200:
                data = response.json()
                core = data.get("resources", {}).get("core", {})
                search = data.get("resources", {}).get("search", {})

                return {
                    "core": {
                        "limit": core.get("limit", 60),
                        "remaining": core.get("remaining", 0),
                        "reset": core.get("reset", time.time() + 3600),
                    },
                    "search": {
                        "limit": search.get("limit", 10),
                        "remaining": search.get("remaining", 0),
                        "reset": search.get("reset", time.time() + 60),
                    },
                }
    except Exception as e:
        console.print(f"[dim]Could not check rate limit: {e}[/dim]")

    # Return defaults if we can't check
    return {
        "core": {"limit": 60, "remaining": 60, "reset": time.time() + 3600},
        "search": {"limit": 10, "remaining": 10, "reset": time.time() + 60},
    }


def check_and_report_rate_limit(rate_info: dict, is_authenticated: bool) -> bool:
    """Check rate limit and report status to user.

    Args:
        rate_info: Rate limit info from check_rate_limit_from_api()
        is_authenticated: Whether using authenticated access

    Returns:
        True if OK to proceed, False if rate limit exhausted
    """
    core = rate_info["core"]
    remaining = core["remaining"]
    limit = core["limit"]
    reset_time = core["reset"]

    if remaining == 0:
        human_time = format_time_remaining(reset_time - time.time())
        reset_at = format_reset_time(reset_time)

        console.print(f"\n[red]Rate limit exhausted[/red] (0/{limit} requests remaining)")
        console.print(f"[yellow]  Resets in: {human_time} (at {reset_at})[/yellow]")

        if not is_authenticated:
            console.print(
                f"[dim]  Tip: Set GITHUB_RESEARCHER_TOKEN for 5,000 requests/hour instead of 60[/dim]"
            )

        console.print()
        return False

    # Show warning if running low
    if remaining < 10:
        console.print(
            f"[yellow]Warning: Only {remaining}/{limit} API requests remaining[/yellow]"
        )

    return True
