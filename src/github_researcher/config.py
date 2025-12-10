"""Configuration management for GitHub Researcher."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration."""

    github_token: str | None
    github_api_url: str = "https://api.github.com"
    github_graphql_url: str = "https://api.github.com/graphql"

    # Rate limits
    rest_rate_limit: int = 5000  # requests per hour (authenticated)
    rest_rate_limit_unauth: int = 60  # requests per hour (unauthenticated)
    search_rate_limit: int = 30  # requests per minute
    graphql_rate_limit: int = 5000  # points per hour

    # Pagination
    default_per_page: int = 100
    max_events_pages: int = 10  # Events API max is 300 events (10 pages * 30)
    max_search_results: int = 1000  # Search API limit

    # Timeouts
    request_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # override=False ensures environment variables take precedence over .env
        load_dotenv(override=False)

        # Support both GITHUB_RESEARCHER_TOKEN (preferred) and GITHUB_TOKEN (fallback)
        token = os.getenv("GITHUB_RESEARCHER_TOKEN") or os.getenv("GITHUB_TOKEN")

        return cls(
            github_token=token,
            github_api_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
            github_graphql_url=os.getenv(
                "GITHUB_GRAPHQL_URL", "https://api.github.com/graphql"
            ),
        )

    @property
    def is_authenticated(self) -> bool:
        """Check if a GitHub token is configured."""
        return bool(self.github_token)

    @property
    def effective_rate_limit(self) -> int:
        """Get the effective rate limit based on authentication status."""
        return self.rest_rate_limit if self.is_authenticated else self.rest_rate_limit_unauth


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance (useful for testing)."""
    global _config
    _config = config
