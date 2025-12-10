"""User profile and social data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Organization(BaseModel):
    """GitHub organization."""

    login: str
    name: str | None = None
    avatar_url: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Organization":
        """Create from GitHub API response."""
        return cls(
            login=data.get("login", ""),
            name=data.get("name"),
            avatar_url=data.get("avatar_url") or data.get("avatarUrl"),
        )


class UserProfile(BaseModel):
    """GitHub user profile data."""

    username: str
    name: str | None = None
    avatar_url: str = ""
    bio: str | None = None
    company: str | None = None
    location: str | None = None
    email: str | None = None
    blog: str | None = None
    twitter_username: str | None = None
    public_repos: int = 0
    public_gists: int = 0
    followers: int = 0
    following: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "UserProfile":
        """Create from GitHub REST API response."""
        return cls(
            username=data.get("login", ""),
            name=data.get("name"),
            avatar_url=data.get("avatar_url", ""),
            bio=data.get("bio"),
            company=data.get("company"),
            location=data.get("location"),
            email=data.get("email"),
            blog=data.get("blog"),
            twitter_username=data.get("twitter_username"),
            public_repos=data.get("public_repos", 0),
            public_gists=data.get("public_gists", 0),
            followers=data.get("followers", 0),
            following=data.get("following", 0),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )

    @classmethod
    def from_graphql(cls, data: dict[str, Any]) -> "UserProfile":
        """Create from GitHub GraphQL API response."""
        return cls(
            username=data.get("login", ""),
            name=data.get("name"),
            avatar_url=data.get("avatarUrl", ""),
            bio=data.get("bio"),
            company=data.get("company"),
            location=data.get("location"),
            email=data.get("email"),
            blog=data.get("websiteUrl"),
            twitter_username=data.get("twitterUsername"),
            public_repos=data.get("repositories", {}).get("totalCount", 0),
            public_gists=data.get("gists", {}).get("totalCount", 0),
            followers=data.get("followers", {}).get("totalCount", 0),
            following=data.get("following", {}).get("totalCount", 0),
            created_at=_parse_datetime(data.get("createdAt")),
            updated_at=_parse_datetime(data.get("updatedAt")),
        )


class SocialData(BaseModel):
    """User's social graph data."""

    followers_count: int = 0
    following_count: int = 0
    followers: list[str] = Field(default_factory=list)  # List of usernames
    following: list[str] = Field(default_factory=list)  # List of usernames
    organizations: list[Organization] = Field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        followers: list[dict[str, Any]],
        following: list[dict[str, Any]],
        orgs: list[dict[str, Any]],
    ) -> "SocialData":
        """Create from GitHub API responses."""
        return cls(
            followers_count=len(followers),
            following_count=len(following),
            followers=[f.get("login", "") for f in followers if f.get("login")],
            following=[f.get("login", "") for f in following if f.get("login")],
            organizations=[Organization.from_api(o) for o in orgs],
        )


class FullUserData(BaseModel):
    """Complete user data including profile and social."""

    profile: UserProfile
    social: SocialData


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string."""
    if not value:
        return None
    try:
        # Handle ISO format with or without Z suffix
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
