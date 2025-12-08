"""Repository collector service."""

import asyncio
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from github_researcher.models.repository import (
    PinnedRepository,
    Repository,
    RepositorySummary,
)
from github_researcher.services.github_graphql_client import GitHubGraphQLClient
from github_researcher.services.github_rest_client import GitHubRestClient

console = Console()


class RepoCollector:
    """Collects repository data and statistics."""

    def __init__(
        self,
        rest_client: GitHubRestClient,
        graphql_client: Optional[GitHubGraphQLClient] = None,
    ):
        self.rest_client = rest_client
        self.graphql_client = graphql_client

    async def collect_repos(
        self,
        username: str,
        include_languages: bool = True,
        max_repos_for_languages: int = 50,
    ) -> RepositorySummary:
        """Collect user's public repositories with optional language breakdown.

        Args:
            username: GitHub username
            include_languages: Whether to fetch language breakdown per repo
            max_repos_for_languages: Max repos to fetch language details for

        Returns:
            RepositorySummary with all repos and aggregated statistics
        """
        console.print(f"[dim]Fetching repositories for {username}...[/dim]")

        # Fetch all public repos
        repos_data = await self.rest_client.get_user_repos(username)
        repos = [Repository.from_api(r) for r in repos_data]

        console.print(f"[dim]Found {len(repos)} public repositories[/dim]")

        # Optionally fetch language breakdown
        repo_languages: dict[str, dict[str, int]] = {}

        if include_languages and repos:
            # Sort by activity (pushed_at) and limit
            sorted_repos = sorted(
                repos,
                key=lambda r: r.pushed_at or r.created_at or r.updated_at,
                reverse=True,
            )
            repos_for_languages = sorted_repos[:max_repos_for_languages]

            console.print(
                f"[dim]Fetching language breakdown for {len(repos_for_languages)} repos...[/dim]"
            )

            # Fetch languages concurrently in batches
            batch_size = 10
            for i in range(0, len(repos_for_languages), batch_size):
                batch = repos_for_languages[i : i + batch_size]
                tasks = []
                for repo in batch:
                    owner, repo_name = repo.full_name.split("/")
                    tasks.append(self._fetch_repo_languages(owner, repo_name))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for repo, result in zip(batch, results):
                    if isinstance(result, dict):
                        repo_languages[repo.full_name] = result
                        repo.languages = result

        return RepositorySummary.from_repos(repos, repo_languages)

    async def _fetch_repo_languages(
        self, owner: str, repo: str
    ) -> dict[str, int]:
        """Fetch language breakdown for a repository."""
        try:
            return await self.rest_client.get_repo_languages(owner, repo)
        except Exception:
            return {}

    async def collect_pinned_repos(self, username: str) -> list[PinnedRepository]:
        """Collect user's pinned repositories via GraphQL.

        Args:
            username: GitHub username

        Returns:
            List of pinned repositories
        """
        if not self.graphql_client:
            console.print(
                "[yellow]GraphQL client not available, skipping pinned repos[/yellow]"
            )
            return []

        console.print(f"[dim]Fetching pinned repositories for {username}...[/dim]")

        try:
            pinned_data = await self.graphql_client.get_pinned_repos(username)
            return [PinnedRepository.from_graphql(r) for r in pinned_data]
        except Exception as e:
            console.print(f"[yellow]Failed to fetch pinned repos: {e}[/yellow]")
            return []

    async def collect_contributed_repos(
        self,
        username: str,
        max_results: int = 100,
    ) -> list[str]:
        """Find public repos the user has contributed to (via PRs).

        This searches for merged PRs by the user to discover repos
        they've contributed to outside their own repositories.

        Args:
            username: GitHub username
            max_results: Maximum results to return

        Returns:
            List of repository full names (owner/repo)
        """
        console.print(f"[dim]Searching for contributed repositories...[/dim]")

        try:
            # Search for merged PRs by user
            prs = await self.rest_client.search_issues(
                f"author:{username} type:pr is:merged",
                max_pages=(max_results + 99) // 100,
            )

            # Extract unique repos
            repos = set()
            for pr in prs[:max_results]:
                repo_url = pr.get("repository_url", "")
                if repo_url:
                    # Extract owner/repo from URL
                    parts = repo_url.split("/")
                    if len(parts) >= 2:
                        repo_name = f"{parts[-2]}/{parts[-1]}"
                        repos.add(repo_name)

            return list(repos)
        except Exception as e:
            console.print(f"[yellow]Failed to search contributed repos: {e}[/yellow]")
            return []
