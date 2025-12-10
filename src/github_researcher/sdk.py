"""GitHub Researcher SDK - High-level API for analyzing GitHub user activity."""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from github_researcher.config import Config
from github_researcher.exceptions import (
    GitHubResearcherError,
    UserNotFoundError,
)
from github_researcher.models.activity import ActivityData, ActivitySummary
from github_researcher.models.contribution import ContributionStats
from github_researcher.models.repository import RepositorySummary
from github_researcher.models.user import FullUserData
from github_researcher.services.activity_collector import ActivityCollector
from github_researcher.services.contribution_collector import ContributionCollector
from github_researcher.services.github_graphql_client import GitHubGraphQLClient
from github_researcher.services.github_rest_client import GitHubRestClient
from github_researcher.services.profile_collector import ProfileCollector
from github_researcher.services.repo_collector import RepoCollector
from github_researcher.utils.rate_limiter import RateLimiter, get_rate_limiter

logger = logging.getLogger(__name__)


class GitHubResearcher:
    """High-level SDK for analyzing GitHub user activity.

    This class provides a clean, async interface for collecting and analyzing
    public GitHub user data including profiles, repositories, contributions,
    and activity history.

    Example usage:
        ```python
        from github_researcher import GitHubResearcher

        async with GitHubResearcher(token="ghp_xxx") as client:
            # Full analysis
            report = await client.analyze("torvalds")

            # Or individual methods
            profile = await client.get_profile("torvalds")
            repos = await client.get_repos("torvalds")
            activity = await client.get_activity("torvalds", days=90)
            contributions = await client.get_contributions("torvalds")
        ```

    Args:
        token: GitHub personal access token (optional but recommended).
            Without a token, rate limits are 60 requests/hour.
            With a token, rate limits are 5,000 requests/hour.
        api_url: GitHub API base URL (default: https://api.github.com)
        graphql_url: GitHub GraphQL API URL (default: https://api.github.com/graphql)
    """

    def __init__(
        self,
        token: str | None = None,
        api_url: str = "https://api.github.com",
        graphql_url: str = "https://api.github.com/graphql",
    ):
        self._config = Config(
            github_token=token,
            github_api_url=api_url,
            github_graphql_url=graphql_url,
        )
        self._rate_limiter: RateLimiter | None = None
        self._rest_client: GitHubRestClient | None = None
        self._graphql_client: GitHubGraphQLClient | None = None
        self._initialized = False

    @property
    def is_authenticated(self) -> bool:
        """Check if a token is configured."""
        return self._config.is_authenticated

    async def __aenter__(self) -> "GitHubResearcher":
        """Async context manager entry."""
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _initialize(self) -> None:
        """Initialize clients."""
        if self._initialized:
            return

        self._rate_limiter = get_rate_limiter()
        self._rest_client = GitHubRestClient(
            config=self._config,
            rate_limiter=self._rate_limiter,
        )

        if self._config.is_authenticated:
            self._graphql_client = GitHubGraphQLClient(
                config=self._config,
                rate_limiter=self._rate_limiter,
            )

        self._initialized = True
        logger.debug(
            "GitHubResearcher initialized (authenticated=%s)",
            self.is_authenticated,
        )

    async def close(self) -> None:
        """Close all HTTP connections."""
        if self._rest_client:
            await self._rest_client.close()
        if self._graphql_client:
            await self._graphql_client.close()
        self._initialized = False
        logger.debug("GitHubResearcher closed")

    def _ensure_initialized(self) -> None:
        """Ensure the client is initialized."""
        if not self._initialized:
            raise GitHubResearcherError(
                "Client not initialized. Use 'async with GitHubResearcher(...) as client:'"
            )

    async def get_profile(self, username: str) -> FullUserData:
        """Get user profile and social data.

        Args:
            username: GitHub username

        Returns:
            FullUserData containing profile and social information

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        self._ensure_initialized()
        logger.info("Fetching profile for %s", username)

        collector = ProfileCollector(self._rest_client, self._graphql_client)

        try:
            return await collector.collect_full(
                username,
                include_followers=False,
                include_following=False,
            )
        except ValueError as e:
            raise UserNotFoundError(username) from e

    async def get_repos(
        self,
        username: str,
        include_languages: bool = True,
        max_repos_for_languages: int = 30,
    ) -> RepositorySummary:
        """Get user's public repositories.

        Args:
            username: GitHub username
            include_languages: Whether to fetch language breakdown per repo
            max_repos_for_languages: Max repos to fetch language details for

        Returns:
            RepositorySummary with repositories and aggregated statistics
        """
        self._ensure_initialized()
        logger.info("Fetching repositories for %s", username)

        collector = RepoCollector(self._rest_client, self._graphql_client)

        return await collector.collect_repos(
            username,
            include_languages=include_languages,
            max_repos_for_languages=max_repos_for_languages,
        )

    async def get_contributions(
        self,
        username: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> ContributionStats | None:
        """Get user's contribution calendar and statistics.

        Requires authentication (token) for GraphQL API access.

        Args:
            username: GitHub username
            from_date: Start date (defaults to 1 year ago)
            to_date: End date (defaults to today)

        Returns:
            ContributionStats with calendar and totals, or None if unauthenticated

        Raises:
            AuthenticationError: If token is required but not provided
        """
        self._ensure_initialized()

        if not self._graphql_client:
            logger.warning(
                "Contributions require authentication. Skipping for %s", username
            )
            return None

        logger.info("Fetching contributions for %s", username)

        collector = ContributionCollector(self._graphql_client)
        return await collector.collect_contributions(username, from_date, to_date)

    async def get_activity(
        self,
        username: str,
        days: int = 365,
        deep: bool = True,
        user_repos: list[str] | None = None,
    ) -> ActivityData:
        """Get user's activity data (events, commits, PRs, issues, reviews).

        Args:
            username: GitHub username
            days: Number of days to look back (default: 365)
            deep: Whether to do deep search via Search API (requires auth)
            user_repos: List of repos to search commits in (optional)

        Returns:
            ActivityData with events, commits, PRs, issues, and reviews
        """
        self._ensure_initialized()
        logger.info("Fetching activity for %s (days=%d, deep=%s)", username, days, deep)

        collector = ActivityCollector(
            self._rest_client,
            is_authenticated=self.is_authenticated,
        )

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        return await collector.collect_activity(
            username,
            since=from_date if deep else None,
            until=to_date if deep else None,
            deep=deep,
            user_repos=user_repos,
        )

    async def get_activity_summary(
        self,
        username: str,
        days: int = 365,
        deep: bool = True,
    ) -> ActivitySummary:
        """Get a summary of user's activity.

        Args:
            username: GitHub username
            days: Number of days to look back (default: 365)
            deep: Whether to do deep search via Search API

        Returns:
            ActivitySummary with aggregated statistics
        """
        self._ensure_initialized()

        # Get repos first for commit search
        repos = await self.get_repos(username, include_languages=False)
        user_repos = [r.full_name for r in repos.repos[:20]]

        activity = await self.get_activity(
            username,
            days=days,
            deep=deep,
            user_repos=user_repos,
        )

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        collector = ActivityCollector(
            self._rest_client,
            is_authenticated=self.is_authenticated,
        )
        return collector.summarize_activity(username, activity, from_date, to_date)

    async def analyze(
        self,
        username: str,
        days: int = 365,
        deep: bool = True,
        include_contributions: bool = True,
    ) -> dict[str, Any]:
        """Perform a full analysis of a GitHub user.

        This is a convenience method that collects all available data
        and returns it as a structured dictionary.

        Args:
            username: GitHub username
            days: Number of days to analyze (default: 365)
            deep: Whether to do deep search via Search API
            include_contributions: Whether to include contribution calendar

        Returns:
            Dictionary with all collected data:
            - profile: User profile and social data
            - repositories: Repository summary
            - contributions: Contribution stats (if authenticated)
            - activity: Activity data
            - activity_summary: Aggregated activity statistics
        """
        self._ensure_initialized()
        logger.info("Starting full analysis for %s", username)

        # Collect profile
        profile = await self.get_profile(username)

        # Collect repos
        repos = await self.get_repos(username)
        user_repos = [r.full_name for r in repos.repos[:20]]

        # Collect contributions (if authenticated)
        contributions = None
        if include_contributions and self._graphql_client:
            to_date = date.today()
            from_date = to_date - timedelta(days=days)
            contributions = await self.get_contributions(username, from_date, to_date)

        # Collect activity
        activity = await self.get_activity(
            username,
            days=days,
            deep=deep,
            user_repos=user_repos,
        )

        # Generate summary
        to_datetime = datetime.now()
        from_datetime = to_datetime - timedelta(days=days)

        collector = ActivityCollector(
            self._rest_client,
            is_authenticated=self.is_authenticated,
        )
        activity_summary = collector.summarize_activity(
            username, activity, from_datetime, to_datetime
        )

        logger.info("Analysis complete for %s", username)

        return {
            "username": username,
            "profile": profile,
            "repositories": repos,
            "contributions": contributions,
            "activity": activity,
            "activity_summary": activity_summary,
            "metadata": {
                "days_analyzed": days,
                "deep_mode": deep,
                "authenticated": self.is_authenticated,
                "analyzed_at": datetime.now().isoformat(),
            },
        }
