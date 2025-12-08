"""GitHub GraphQL API client for contribution data."""

from datetime import date, datetime
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from github_researcher.config import Config, get_config
from github_researcher.utils.rate_limiter import RateLimiter, get_rate_limiter


class GitHubGraphQLError(Exception):
    """Exception for GraphQL API errors."""

    def __init__(self, message: str, errors: Optional[list] = None):
        super().__init__(message)
        self.errors = errors or []


# GraphQL query for contribution calendar and totals
CONTRIBUTIONS_QUERY = """
query($username: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
          }
        }
      }
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
    }
  }
}
"""

# Query for user's pinned repositories
PINNED_REPOS_QUERY = """
query($username: String!) {
  user(login: $username) {
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name
          nameWithOwner
          description
          url
          stargazerCount
          forkCount
          primaryLanguage {
            name
            color
          }
        }
      }
    }
  }
}
"""

# Query for detailed user profile
USER_PROFILE_QUERY = """
query($username: String!) {
  user(login: $username) {
    login
    name
    bio
    company
    location
    email
    websiteUrl
    twitterUsername
    avatarUrl
    createdAt
    updatedAt
    followers {
      totalCount
    }
    following {
      totalCount
    }
    repositories(privacy: PUBLIC) {
      totalCount
    }
    gists(privacy: PUBLIC) {
      totalCount
    }
    organizations(first: 100) {
      nodes {
        login
        name
        avatarUrl
      }
    }
  }
}
"""


class GitHubGraphQLClient:
    """Async client for GitHub GraphQL API."""

    def __init__(
        self,
        config: Optional[Config] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.config = config or get_config()
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        if not self.config.github_token:
            raise GitHubGraphQLError(
                "GitHub token is required for GraphQL API. "
                "Set GITHUB_TOKEN environment variable."
            )

        return {
            "Authorization": f"Bearer {self.config.github_token}",
            "Content-Type": "application/json",
            "User-Agent": "github-researcher/0.1.0",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.github_graphql_url,
                headers=self._get_headers(),
                timeout=self.config.request_timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "GitHubGraphQLClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def execute(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Query result data

        Raises:
            GitHubGraphQLError: If the query fails
        """
        # Acquire rate limit permission
        await self.rate_limiter.acquire_graphql()

        client = await self._get_client()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await client.post("", json=payload)

        # Update rate limit from response
        self.rate_limiter.update_graphql_from_headers(dict(response.headers))

        if response.status_code != 200:
            raise GitHubGraphQLError(
                f"GraphQL request failed with status {response.status_code}: {response.text}"
            )

        result = response.json()

        # Check for GraphQL errors
        if "errors" in result:
            error_messages = [e.get("message", "Unknown error") for e in result["errors"]]
            raise GitHubGraphQLError(
                f"GraphQL errors: {'; '.join(error_messages)}",
                errors=result["errors"],
            )

        return result.get("data", {})

    async def get_contributions(
        self,
        username: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """Get user's contribution calendar and statistics.

        Args:
            username: GitHub username
            from_date: Start date (defaults to 1 year ago)
            to_date: End date (defaults to today)

        Returns:
            Contribution data including calendar and totals
        """
        # Default to last year
        if to_date is None:
            to_date = date.today()
        if from_date is None:
            from_date = date(to_date.year - 1, to_date.month, to_date.day)

        # Convert to ISO format with time
        from_datetime = datetime.combine(from_date, datetime.min.time()).isoformat() + "Z"
        to_datetime = datetime.combine(to_date, datetime.max.time()).isoformat() + "Z"

        variables = {
            "username": username,
            "from": from_datetime,
            "to": to_datetime,
        }

        result = await self.execute(CONTRIBUTIONS_QUERY, variables)

        if not result.get("user"):
            raise GitHubGraphQLError(f"User not found: {username}")

        return result["user"]["contributionsCollection"]

    async def get_pinned_repos(self, username: str) -> list[dict[str, Any]]:
        """Get user's pinned repositories.

        Args:
            username: GitHub username

        Returns:
            List of pinned repository data
        """
        variables = {"username": username}
        result = await self.execute(PINNED_REPOS_QUERY, variables)

        if not result.get("user"):
            raise GitHubGraphQLError(f"User not found: {username}")

        return result["user"]["pinnedItems"]["nodes"]

    async def get_user_profile(self, username: str) -> dict[str, Any]:
        """Get detailed user profile via GraphQL.

        Args:
            username: GitHub username

        Returns:
            User profile data including organizations
        """
        variables = {"username": username}
        result = await self.execute(USER_PROFILE_QUERY, variables)

        if not result.get("user"):
            raise GitHubGraphQLError(f"User not found: {username}")

        return result["user"]

    async def get_contribution_years(
        self,
        username: str,
        years: list[int],
    ) -> dict[int, dict[str, Any]]:
        """Get contributions for multiple years.

        Args:
            username: GitHub username
            years: List of years to fetch

        Returns:
            Dict mapping year to contribution data
        """
        results = {}
        for year in years:
            from_date = date(year, 1, 1)
            to_date = date(year, 12, 31)

            # Don't go into the future
            today = date.today()
            if to_date > today:
                to_date = today

            if from_date <= today:
                results[year] = await self.get_contributions(
                    username, from_date, to_date
                )

        return results
