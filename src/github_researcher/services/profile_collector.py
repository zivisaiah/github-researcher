"""Profile and social data collector service."""

import asyncio
from typing import Optional

from rich.console import Console

from github_researcher.models.user import (
    FullUserData,
    Organization,
    SocialData,
    UserProfile,
)
from github_researcher.services.github_graphql_client import GitHubGraphQLClient
from github_researcher.services.github_rest_client import (
    GitHubNotFoundError,
    GitHubRestClient,
)

console = Console()


class ProfileCollector:
    """Collects user profile and social data."""

    def __init__(
        self,
        rest_client: GitHubRestClient,
        graphql_client: Optional[GitHubGraphQLClient] = None,
    ):
        self.rest_client = rest_client
        self.graphql_client = graphql_client

    async def collect_profile(self, username: str) -> UserProfile:
        """Collect user profile data.

        Args:
            username: GitHub username

        Returns:
            UserProfile with all available data
        """
        console.print(f"[dim]Fetching profile for {username}...[/dim]")

        try:
            data = await self.rest_client.get_user(username)
            return UserProfile.from_api(data)
        except GitHubNotFoundError:
            raise ValueError(f"User not found: {username}")

    async def collect_social(
        self,
        username: str,
        include_followers: bool = True,
        include_following: bool = True,
        max_followers: int = 100,
        max_following: int = 100,
    ) -> SocialData:
        """Collect user's social graph data.

        Args:
            username: GitHub username
            include_followers: Whether to fetch followers list
            include_following: Whether to fetch following list
            max_followers: Maximum followers to fetch
            max_following: Maximum following to fetch

        Returns:
            SocialData with followers, following, and organizations
        """
        console.print(f"[dim]Fetching social data for {username}...[/dim]")

        # Fetch orgs always
        orgs = await self.rest_client.get_user_orgs(username)

        # Fetch followers if requested
        followers = []
        if include_followers:
            max_pages = (max_followers + 99) // 100
            followers = await self.rest_client.get_user_followers(
                username, max_pages=max_pages
            )

        # Fetch following if requested
        following = []
        if include_following:
            max_pages = (max_following + 99) // 100
            following = await self.rest_client.get_user_following(
                username, max_pages=max_pages
            )

        return SocialData(
            followers_count=len(followers),
            following_count=len(following),
            followers=[f.get("login", "") for f in followers[:max_followers]],
            following=[f.get("login", "") for f in following[:max_following]],
            organizations=[Organization.from_api(o) for o in orgs],
        )

    async def collect_full(
        self,
        username: str,
        include_followers: bool = True,
        include_following: bool = True,
    ) -> FullUserData:
        """Collect complete user data including profile and social.

        Args:
            username: GitHub username
            include_followers: Whether to fetch followers list
            include_following: Whether to fetch following list

        Returns:
            FullUserData with profile and social data
        """
        # Fetch profile and social concurrently
        profile_task = self.collect_profile(username)
        social_task = self.collect_social(
            username,
            include_followers=include_followers,
            include_following=include_following,
        )

        profile, social = await asyncio.gather(profile_task, social_task)

        # Update social counts from profile (more accurate)
        social.followers_count = profile.followers
        social.following_count = profile.following

        return FullUserData(profile=profile, social=social)
