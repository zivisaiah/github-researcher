"""Exceptions for GitHub Researcher SDK.

Exception Hierarchy:
    GitHubResearcherError (base)
    ├── GitHubAPIError (HTTP API errors with status codes)
    │   ├── GitHubRateLimitError (403 rate limit from API response)
    │   └── GitHubNotFoundError (404 not found)
    ├── GitHubGraphQLError (GraphQL API errors)
    ├── RateLimitExceededError (local rate limit tracking, before making request)
    ├── UserNotFoundError (high-level user not found)
    └── AuthenticationError (token invalid or required)

Usage:
    - GitHubRateLimitError: Raised when GitHub API returns 403 with rate limit message
    - RateLimitExceededError: Raised by local RateLimiter when limits are exhausted
      (prevents making requests that would fail)
"""

__all__ = [
    "GitHubResearcherError",
    "GitHubAPIError",
    "GitHubRateLimitError",
    "GitHubNotFoundError",
    "GitHubGraphQLError",
    "RateLimitExceededError",
    "UserNotFoundError",
    "AuthenticationError",
]


class GitHubResearcherError(Exception):
    """Base exception for all GitHub Researcher errors."""

    pass


class GitHubAPIError(GitHubResearcherError):
    """Base exception for GitHub API errors (HTTP responses with error status codes)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub API returns a rate limit error (HTTP 403).

    This is raised after receiving a rate limit response from the GitHub API.
    For preemptive rate limiting (before making requests), see RateLimitExceededError.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = 403,
        response_body: dict | None = None,
        reset_time: float | None = None,
    ):
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.reset_time = reset_time


class GitHubNotFoundError(GitHubAPIError):
    """Raised when a GitHub resource is not found (HTTP 404)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = 404,
        response_body: dict | None = None,
    ):
        super().__init__(message, status_code=status_code, response_body=response_body)


class GitHubGraphQLError(GitHubResearcherError):
    """Exception for GraphQL API errors."""

    def __init__(self, message: str, errors: list | None = None):
        super().__init__(message)
        self.errors = errors or []


class RateLimitExceededError(GitHubResearcherError):
    """Raised by local rate limiter when limits are exhausted.

    This is a preemptive exception raised before making a request when the
    local rate limit tracker indicates no remaining requests. This prevents
    making requests that would fail with GitHubRateLimitError.

    Unlike GitHubRateLimitError, this does not involve an actual API call.
    """

    pass


class UserNotFoundError(GitHubResearcherError):
    """Raised when a GitHub user is not found."""

    def __init__(self, username: str):
        super().__init__(f"User not found: {username}")
        self.username = username


class AuthenticationError(GitHubResearcherError):
    """Raised when authentication fails or token is invalid."""

    pass
