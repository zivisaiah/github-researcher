"""Repository data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Repository(BaseModel):
    """GitHub repository data."""

    name: str
    full_name: str
    description: str | None = None
    html_url: str = ""
    language: str | None = None
    languages: dict[str, int] = Field(default_factory=dict)  # language -> bytes
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    topics: list[str] = Field(default_factory=list)
    is_fork: bool = False
    is_archived: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None
    size: int = 0  # Size in KB

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Repository":
        """Create from GitHub REST API response."""
        return cls(
            name=data.get("name", ""),
            full_name=data.get("full_name", ""),
            description=data.get("description"),
            html_url=data.get("html_url", ""),
            language=data.get("language"),
            stargazers_count=data.get("stargazers_count", 0),
            forks_count=data.get("forks_count", 0),
            open_issues_count=data.get("open_issues_count", 0),
            topics=data.get("topics", []),
            is_fork=data.get("fork", False),
            is_archived=data.get("archived", False),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            pushed_at=_parse_datetime(data.get("pushed_at")),
            size=data.get("size", 0),
        )


class LanguageStats(BaseModel):
    """Aggregated language statistics."""

    total_bytes: int = 0
    languages: dict[str, int] = Field(default_factory=dict)  # language -> bytes
    percentages: dict[str, float] = Field(default_factory=dict)  # language -> percentage

    def add_repo_languages(self, languages: dict[str, int]) -> None:
        """Add language stats from a repository."""
        for lang, bytes_count in languages.items():
            self.languages[lang] = self.languages.get(lang, 0) + bytes_count
            self.total_bytes += bytes_count

    def calculate_percentages(self) -> None:
        """Calculate percentage for each language."""
        if self.total_bytes == 0:
            return
        self.percentages = {
            lang: round((bytes_count / self.total_bytes) * 100, 2)
            for lang, bytes_count in sorted(
                self.languages.items(), key=lambda x: x[1], reverse=True
            )
        }


class RepositorySummary(BaseModel):
    """Summary of user's repositories."""

    count: int = 0
    total_stars: int = 0
    total_forks: int = 0
    total_open_issues: int = 0
    languages: LanguageStats = Field(default_factory=LanguageStats)
    topics: dict[str, int] = Field(default_factory=dict)  # topic -> count
    repos: list[Repository] = Field(default_factory=list)

    @classmethod
    def from_repos(
        cls,
        repos: list[Repository],
        repo_languages: dict[str, dict[str, int]] | None = None,
    ) -> "RepositorySummary":
        """Create summary from list of repositories.

        Args:
            repos: List of Repository objects
            repo_languages: Optional dict of full_name -> language breakdown
        """
        summary = cls(
            count=len(repos),
            repos=repos,
        )

        for repo in repos:
            summary.total_stars += repo.stargazers_count
            summary.total_forks += repo.forks_count
            summary.total_open_issues += repo.open_issues_count

            # Add topics
            for topic in repo.topics:
                summary.topics[topic] = summary.topics.get(topic, 0) + 1

            # Add language stats
            if repo_languages and repo.full_name in repo_languages:
                summary.languages.add_repo_languages(repo_languages[repo.full_name])
            elif repo.language:
                # Use primary language if detailed breakdown not available
                summary.languages.add_repo_languages({repo.language: repo.size * 1024})

        summary.languages.calculate_percentages()

        return summary


class PinnedRepository(BaseModel):
    """Pinned repository from user profile."""

    name: str
    full_name: str
    description: str | None = None
    url: str = ""
    stars: int = 0
    forks: int = 0
    primary_language: str | None = None
    language_color: str | None = None

    @classmethod
    def from_graphql(cls, data: dict[str, Any]) -> "PinnedRepository":
        """Create from GraphQL response."""
        primary_lang = data.get("primaryLanguage") or {}
        return cls(
            name=data.get("name", ""),
            full_name=data.get("nameWithOwner", ""),
            description=data.get("description"),
            url=data.get("url", ""),
            stars=data.get("stargazerCount", 0),
            forks=data.get("forkCount", 0),
            primary_language=primary_lang.get("name"),
            language_color=primary_lang.get("color"),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
