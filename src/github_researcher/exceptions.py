"""Exceptions for GitHub Researcher SDK."""


class GitHubResearcherError(Exception):
    """Base exception for all GitHub Researcher errors."""

    pass


class GitHubAPIError(GitHubResearcherError):
    """Base exception for GitHub API errors."""

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
    """Raised when GitHub API rate limit is exceeded."""

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
    """Raised when a GitHub resource is not found."""

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
    """Raised when rate limit is exceeded and we don't want to wait."""

    pass


class UserNotFoundError(GitHubResearcherError):
    """Raised when a GitHub user is not found."""

    def __init__(self, username: str):
        super().__init__(f"User not found: {username}")
        self.username = username


class AuthenticationError(GitHubResearcherError):
    """Raised when authentication fails or token is invalid."""

    pass
