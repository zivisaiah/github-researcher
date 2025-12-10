"""Contribution calendar collector service."""

import logging
from datetime import date

from github_researcher.exceptions import GitHubGraphQLError
from github_researcher.models.contribution import ContributionStats
from github_researcher.services.github_graphql_client import GitHubGraphQLClient

logger = logging.getLogger(__name__)


class ContributionCollector:
    """Collects contribution calendar and statistics via GraphQL."""

    def __init__(self, graphql_client: GitHubGraphQLClient):
        self.graphql_client = graphql_client

    async def collect_contributions(
        self,
        username: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> ContributionStats:
        """Collect contribution statistics for a user.

        Args:
            username: GitHub username
            from_date: Start date (defaults to 1 year ago)
            to_date: End date (defaults to today)

        Returns:
            ContributionStats with calendar and totals
        """
        logger.debug("Fetching contribution calendar for %s", username)

        try:
            data = await self.graphql_client.get_contributions(username, from_date, to_date)
            stats = ContributionStats.from_graphql(data)

            logger.debug("Found %d contributions", stats.total_contributions)

            return stats
        except GitHubGraphQLError as e:
            logger.error("Failed to fetch contributions: %s", e)
            raise

    async def collect_yearly_contributions(
        self,
        username: str,
        years: list[int] | None = None,
    ) -> dict[int, ContributionStats]:
        """Collect contributions for multiple years.

        Args:
            username: GitHub username
            years: List of years to fetch (defaults to current year)

        Returns:
            Dict mapping year to ContributionStats
        """
        if years is None:
            years = [date.today().year]

        logger.debug("Fetching contributions for years: %s", years)

        results = {}
        for year in years:
            try:
                from_date = date(year, 1, 1)
                to_date = date(year, 12, 31)

                # Don't go into the future
                today = date.today()
                if to_date > today:
                    to_date = today

                if from_date <= today:
                    data = await self.graphql_client.get_contributions(username, from_date, to_date)
                    results[year] = ContributionStats.from_graphql(data)
            except GitHubGraphQLError as e:
                logger.warning("Failed to fetch contributions for %d: %s", year, e)

        return results

    async def get_contribution_summary(
        self,
        username: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        """Get a summary of contribution statistics.

        Args:
            username: GitHub username
            from_date: Start date
            to_date: End date

        Returns:
            Dictionary with contribution summary
        """
        stats = await self.collect_contributions(username, from_date, to_date)

        busiest = stats.busiest_day
        return {
            "total_contributions": stats.total_contributions,
            "commits": stats.total_commits,
            "pull_requests": stats.total_pull_requests,
            "issues": stats.total_issues,
            "reviews": stats.total_reviews,
            "restricted_contributions": stats.restricted_contributions,
            "current_streak": stats.current_streak,
            "longest_streak": stats.longest_streak,
            "busiest_day": busiest.date.isoformat() if busiest else None,
            "busiest_day_count": busiest.count if busiest else 0,
        }
