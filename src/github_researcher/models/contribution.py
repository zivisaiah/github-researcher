"""Contribution calendar and statistics models."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ContributionDay(BaseModel):
    """Single day in contribution calendar."""

    date: date
    count: int = 0
    level: str = "NONE"  # NONE, FIRST_QUARTILE, SECOND_QUARTILE, THIRD_QUARTILE, FOURTH_QUARTILE

    @classmethod
    def from_graphql(cls, data: dict[str, Any]) -> "ContributionDay":
        """Create from GraphQL response."""
        date_str = data.get("date", "")
        return cls(
            date=date.fromisoformat(date_str) if date_str else date.today(),
            count=data.get("contributionCount", 0),
            level=data.get("contributionLevel", "NONE"),
        )


class ContributionWeek(BaseModel):
    """Week of contributions."""

    days: list[ContributionDay] = Field(default_factory=list)

    @classmethod
    def from_graphql(cls, data: dict[str, Any]) -> "ContributionWeek":
        """Create from GraphQL response."""
        days = [
            ContributionDay.from_graphql(day)
            for day in data.get("contributionDays", [])
        ]
        return cls(days=days)


class ContributionCalendar(BaseModel):
    """Full contribution calendar (the green squares mosaic)."""

    total_contributions: int = 0
    weeks: list[ContributionWeek] = Field(default_factory=list)

    @classmethod
    def from_graphql(cls, data: dict[str, Any]) -> "ContributionCalendar":
        """Create from GraphQL response."""
        weeks = [
            ContributionWeek.from_graphql(week)
            for week in data.get("weeks", [])
        ]
        return cls(
            total_contributions=data.get("totalContributions", 0),
            weeks=weeks,
        )

    def get_busiest_day(self) -> ContributionDay | None:
        """Find the day with most contributions."""
        busiest = None
        for week in self.weeks:
            for day in week.days:
                if busiest is None or day.count > busiest.count:
                    busiest = day
        return busiest

    def get_streak(self) -> int:
        """Calculate current contribution streak (consecutive days with contributions)."""
        # Flatten days in reverse chronological order
        all_days = []
        for week in reversed(self.weeks):
            for day in reversed(week.days):
                all_days.append(day)

        streak = 0
        for day in all_days:
            if day.count > 0:
                streak += 1
            else:
                # Stop at first day without contributions
                break

        return streak

    def get_longest_streak(self) -> int:
        """Calculate longest contribution streak."""
        # Flatten days chronologically
        all_days = []
        for week in self.weeks:
            for day in week.days:
                all_days.append(day)

        longest = 0
        current = 0
        for day in all_days:
            if day.count > 0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0

        return longest


class ContributionStats(BaseModel):
    """Contribution statistics from GraphQL API."""

    total_commits: int = 0
    total_issues: int = 0
    total_pull_requests: int = 0
    total_reviews: int = 0
    restricted_contributions: int = 0  # Private contributions (count only)
    calendar: ContributionCalendar = Field(default_factory=ContributionCalendar)

    @classmethod
    def from_graphql(cls, data: dict[str, Any]) -> "ContributionStats":
        """Create from GraphQL contributionsCollection response."""
        calendar_data = data.get("contributionCalendar", {})
        return cls(
            total_commits=data.get("totalCommitContributions", 0),
            total_issues=data.get("totalIssueContributions", 0),
            total_pull_requests=data.get("totalPullRequestContributions", 0),
            total_reviews=data.get("totalPullRequestReviewContributions", 0),
            restricted_contributions=data.get("restrictedContributionsCount", 0),
            calendar=ContributionCalendar.from_graphql(calendar_data),
        )

    @property
    def total_contributions(self) -> int:
        """Total public contributions."""
        return self.calendar.total_contributions

    @property
    def current_streak(self) -> int:
        """Current contribution streak."""
        return self.calendar.get_streak()

    @property
    def longest_streak(self) -> int:
        """Longest contribution streak."""
        return self.calendar.get_longest_streak()

    @property
    def busiest_day(self) -> ContributionDay | None:
        """Day with most contributions."""
        return self.calendar.get_busiest_day()
