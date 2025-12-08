"""Activity and events collector service."""

import asyncio
from datetime import datetime
from typing import Optional

from rich.console import Console

from github_researcher.models.activity import (
    ActivityData,
    ActivitySummary,
    Commit,
    GitHubEvent,
    Issue,
    PullRequest,
)
from github_researcher.services.github_rest_client import GitHubRestClient

console = Console()


class ActivityCollector:
    """Collects activity data from Events API and Search API."""

    def __init__(self, rest_client: GitHubRestClient):
        self.rest_client = rest_client

    async def collect_events(
        self,
        username: str,
        max_pages: int = 10,
    ) -> list[GitHubEvent]:
        """Collect user's public events (last 90 days, max 300).

        Args:
            username: GitHub username
            max_pages: Maximum pages to fetch (10 pages = 300 events max)

        Returns:
            List of GitHubEvent objects
        """
        console.print(f"[dim]Fetching public events for {username}...[/dim]")

        events_data = await self.rest_client.get_user_events(username, max_pages)
        events = [GitHubEvent.from_api(e) for e in events_data]

        console.print(f"[dim]Found {len(events)} events[/dim]")

        return events

    async def collect_prs(
        self,
        username: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        max_results: int = 1000,
    ) -> list[PullRequest]:
        """Collect pull requests authored by user via Search API.

        Args:
            username: GitHub username
            since: Only PRs created after this date
            until: Only PRs created before this date
            max_results: Maximum results to fetch

        Returns:
            List of PullRequest objects
        """
        console.print(f"[dim]Searching for pull requests by {username}...[/dim]")

        # Build search query
        query = f"author:{username} type:pr"
        if since:
            query += f" created:>={since.strftime('%Y-%m-%d')}"
        if until:
            query += f" created:<={until.strftime('%Y-%m-%d')}"

        try:
            pr_data = await self.rest_client.search_issues(
                query, max_pages=(max_results + 99) // 100
            )

            prs = [PullRequest.from_api(p) for p in pr_data[:max_results]]
            console.print(f"[dim]Found {len(prs)} pull requests[/dim]")

            return prs
        except Exception as e:
            console.print(f"[yellow]Failed to search PRs: {e}[/yellow]")
            return []

    async def collect_issues(
        self,
        username: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        max_results: int = 1000,
    ) -> list[Issue]:
        """Collect issues authored by user via Search API.

        Args:
            username: GitHub username
            since: Only issues created after this date
            until: Only issues created before this date
            max_results: Maximum results to fetch

        Returns:
            List of Issue objects
        """
        console.print(f"[dim]Searching for issues by {username}...[/dim]")

        # Build search query
        query = f"author:{username} type:issue"
        if since:
            query += f" created:>={since.strftime('%Y-%m-%d')}"
        if until:
            query += f" created:<={until.strftime('%Y-%m-%d')}"

        try:
            issue_data = await self.rest_client.search_issues(
                query, max_pages=(max_results + 99) // 100
            )

            issues = [Issue.from_api(i) for i in issue_data[:max_results]]
            console.print(f"[dim]Found {len(issues)} issues[/dim]")

            return issues
        except Exception as e:
            console.print(f"[yellow]Failed to search issues: {e}[/yellow]")
            return []

    async def collect_reviews(
        self,
        username: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        max_results: int = 500,
    ) -> list[PullRequest]:
        """Collect PRs reviewed by user via Search API.

        Args:
            username: GitHub username
            since: Only reviews after this date
            until: Only reviews before this date
            max_results: Maximum results to fetch

        Returns:
            List of PullRequest objects (PRs that were reviewed)
        """
        console.print(f"[dim]Searching for reviews by {username}...[/dim]")

        # Build search query
        query = f"reviewed-by:{username} type:pr"
        if since:
            query += f" created:>={since.strftime('%Y-%m-%d')}"
        if until:
            query += f" created:<={until.strftime('%Y-%m-%d')}"

        try:
            pr_data = await self.rest_client.search_issues(
                query, max_pages=(max_results + 99) // 100
            )

            prs = [PullRequest.from_api(p) for p in pr_data[:max_results]]
            console.print(f"[dim]Found {len(prs)} reviewed PRs[/dim]")

            return prs
        except Exception as e:
            console.print(f"[yellow]Failed to search reviews: {e}[/yellow]")
            return []

    async def collect_commits_from_repos(
        self,
        username: str,
        repos: list[str],
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        max_commits_per_repo: int = 100,
    ) -> list[Commit]:
        """Collect commits by user from specific repositories.

        Args:
            username: GitHub username
            repos: List of repository full names (owner/repo)
            since: Only commits after this date
            until: Only commits before this date
            max_commits_per_repo: Maximum commits per repository

        Returns:
            List of Commit objects
        """
        console.print(
            f"[dim]Fetching commits from {len(repos)} repositories...[/dim]"
        )

        all_commits = []
        max_pages = (max_commits_per_repo + 99) // 100

        # Process repos in batches
        batch_size = 5
        for i in range(0, len(repos), batch_size):
            batch = repos[i : i + batch_size]
            tasks = []

            for repo in batch:
                parts = repo.split("/")
                if len(parts) == 2:
                    owner, repo_name = parts
                    tasks.append(
                        self._fetch_repo_commits(
                            owner,
                            repo_name,
                            username,
                            since,
                            until,
                            max_pages,
                        )
                    )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for repo, result in zip(batch, results):
                if isinstance(result, list):
                    all_commits.extend(result)

        console.print(f"[dim]Found {len(all_commits)} commits[/dim]")

        return all_commits

    async def _fetch_repo_commits(
        self,
        owner: str,
        repo: str,
        author: str,
        since: Optional[datetime],
        until: Optional[datetime],
        max_pages: int,
    ) -> list[Commit]:
        """Fetch commits from a single repository."""
        try:
            commits_data = await self.rest_client.get_repo_commits(
                owner,
                repo,
                author=author,
                since=since.isoformat() if since else None,
                until=until.isoformat() if until else None,
                max_pages=max_pages,
            )
            return [
                Commit.from_api(c, f"{owner}/{repo}")
                for c in commits_data
            ]
        except Exception:
            return []

    def extract_commits_from_events(
        self, events: list[GitHubEvent]
    ) -> list[Commit]:
        """Extract commits from PushEvents.

        Args:
            events: List of GitHubEvent objects

        Returns:
            List of Commit objects extracted from push events
        """
        commits = []
        for event in events:
            if event.type == "PushEvent":
                payload_commits = event.payload.get("commits", [])
                for commit_data in payload_commits:
                    commits.append(Commit.from_push_event(event, commit_data))
        return commits

    async def collect_activity(
        self,
        username: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        deep: bool = True,
        user_repos: Optional[list[str]] = None,
    ) -> ActivityData:
        """Collect comprehensive activity data.

        Args:
            username: GitHub username
            since: Start date for activity
            until: End date for activity
            deep: Whether to do deep search (Search API for full history)
            user_repos: List of user's repos to search commits in

        Returns:
            ActivityData with all collected activity
        """
        # Always fetch events (quick, last 90 days)
        events = await self.collect_events(username)
        commits_from_events = self.extract_commits_from_events(events)

        if not deep:
            # Quick mode - only use events
            return ActivityData(
                events=events,
                commits=commits_from_events,
            )

        # Deep mode - use Search API for full history
        prs_task = self.collect_prs(username, since, until)
        issues_task = self.collect_issues(username, since, until)
        reviews_task = self.collect_reviews(username, since, until)

        prs, issues, reviews = await asyncio.gather(
            prs_task, issues_task, reviews_task
        )

        # Collect commits from user's repos if provided
        commits = commits_from_events
        if user_repos:
            repo_commits = await self.collect_commits_from_repos(
                username, user_repos, since, until
            )
            # Merge and deduplicate
            seen_shas = {c.sha for c in commits}
            for commit in repo_commits:
                if commit.sha not in seen_shas:
                    commits.append(commit)
                    seen_shas.add(commit.sha)

        return ActivityData(
            events=events,
            commits=commits,
            pull_requests=prs,
            issues=issues,
            reviews=reviews,
        )

    def summarize_activity(
        self,
        username: str,
        activity: ActivityData,
        period_start: datetime,
        period_end: datetime,
    ) -> ActivitySummary:
        """Create summary from activity data.

        Args:
            username: GitHub username
            activity: Collected activity data
            period_start: Analysis period start
            period_end: Analysis period end

        Returns:
            ActivitySummary with statistics
        """
        return ActivitySummary.from_activity(
            username, activity, period_start, period_end
        )
