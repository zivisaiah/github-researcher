"""Activity and event data models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """GitHub event types."""

    PUSH = "PushEvent"
    PULL_REQUEST = "PullRequestEvent"
    PULL_REQUEST_REVIEW = "PullRequestReviewEvent"
    PULL_REQUEST_REVIEW_COMMENT = "PullRequestReviewCommentEvent"
    ISSUES = "IssuesEvent"
    ISSUE_COMMENT = "IssueCommentEvent"
    CREATE = "CreateEvent"
    DELETE = "DeleteEvent"
    FORK = "ForkEvent"
    WATCH = "WatchEvent"
    RELEASE = "ReleaseEvent"
    COMMIT_COMMENT = "CommitCommentEvent"
    GOLLUM = "GollumEvent"  # Wiki events
    PUBLIC = "PublicEvent"
    MEMBER = "MemberEvent"
    OTHER = "Other"


class GitHubEvent(BaseModel):
    """GitHub event from Events API."""

    id: str
    type: str
    actor: str
    repo: str
    created_at: datetime
    payload: dict = Field(default_factory=dict)
    public: bool = True

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "GitHubEvent":
        """Create from GitHub Events API response."""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            actor=data.get("actor", {}).get("login", ""),
            repo=data.get("repo", {}).get("name", ""),
            created_at=_parse_datetime(data.get("created_at")) or datetime.now(),
            payload=data.get("payload", {}),
            public=data.get("public", True),
        )

    @property
    def event_type(self) -> EventType:
        """Get typed event type."""
        try:
            return EventType(self.type)
        except ValueError:
            return EventType.OTHER


class Commit(BaseModel):
    """Git commit data."""

    sha: str
    message: str
    author: str
    author_email: str | None = None
    date: datetime
    repo: str
    url: str = ""
    additions: int = 0
    deletions: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any], repo: str = "") -> "Commit":
        """Create from GitHub Commits API response."""
        commit_data = data.get("commit", {})
        author_data = commit_data.get("author", {})
        return cls(
            sha=data.get("sha", ""),
            message=commit_data.get("message", "").split("\n")[0],  # First line only
            author=data.get("author", {}).get("login", author_data.get("name", "")),
            author_email=author_data.get("email"),
            date=_parse_datetime(author_data.get("date")) or datetime.now(),
            repo=repo or "",
            url=data.get("html_url", ""),
        )

    @classmethod
    def from_push_event(cls, event: GitHubEvent, commit_data: dict) -> "Commit":
        """Create from PushEvent payload commit."""
        return cls(
            sha=commit_data.get("sha", ""),
            message=commit_data.get("message", "").split("\n")[0],
            author=commit_data.get("author", {}).get("name", event.actor),
            author_email=commit_data.get("author", {}).get("email"),
            date=event.created_at,
            repo=event.repo,
            url=f"https://github.com/{event.repo}/commit/{commit_data.get('sha', '')}",
        )


class PullRequest(BaseModel):
    """Pull request data."""

    number: int
    title: str
    state: str  # open, closed, merged
    author: str
    repo: str
    created_at: datetime
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    url: str = ""
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    is_merged: bool = False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PullRequest":
        """Create from GitHub Pull Requests API or Search API response."""
        # Handle both PR API and Search API formats
        repo_url = data.get("repository_url", "")
        if repo_url:
            # Extract owner/repo from URL
            parts = repo_url.split("/")
            repo = f"{parts[-2]}/{parts[-1]}" if len(parts) >= 2 else ""
        else:
            repo = data.get("base", {}).get("repo", {}).get("full_name", "")

        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            state=data.get("state", ""),
            author=data.get("user", {}).get("login", ""),
            repo=repo,
            created_at=_parse_datetime(data.get("created_at")) or datetime.now(),
            updated_at=_parse_datetime(data.get("updated_at")),
            closed_at=_parse_datetime(data.get("closed_at")),
            merged_at=_parse_datetime(data.get("merged_at")),
            url=data.get("html_url", ""),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
            is_merged=data.get("merged", False) or data.get("merged_at") is not None,
        )


class Issue(BaseModel):
    """Issue data."""

    number: int
    title: str
    state: str  # open, closed
    author: str
    repo: str
    created_at: datetime
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    url: str = ""
    labels: list[str] = Field(default_factory=list)
    comments: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Issue":
        """Create from GitHub Issues API or Search API response."""
        # Extract repo from repository_url or html_url
        repo_url = data.get("repository_url", "")
        if repo_url:
            parts = repo_url.split("/")
            repo = f"{parts[-2]}/{parts[-1]}" if len(parts) >= 2 else ""
        else:
            html_url = data.get("html_url", "")
            # Parse from https://github.com/owner/repo/issues/123
            parts = html_url.split("/")
            if len(parts) >= 5:
                repo = f"{parts[3]}/{parts[4]}"
            else:
                repo = ""

        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            state=data.get("state", ""),
            author=data.get("user", {}).get("login", ""),
            repo=repo,
            created_at=_parse_datetime(data.get("created_at")) or datetime.now(),
            updated_at=_parse_datetime(data.get("updated_at")),
            closed_at=_parse_datetime(data.get("closed_at")),
            url=data.get("html_url", ""),
            labels=[label.get("name", "") for label in data.get("labels", [])],
            comments=data.get("comments", 0),
        )


class ActivityData(BaseModel):
    """Aggregated activity data."""

    events: list[GitHubEvent] = Field(default_factory=list)
    commits: list[Commit] = Field(default_factory=list)
    pull_requests: list[PullRequest] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    reviews: list[PullRequest] = Field(default_factory=list)  # PRs reviewed


class ActivitySummary(BaseModel):
    """Summary statistics for activity."""

    username: str
    period_start: datetime
    period_end: datetime
    total_events: int = 0
    total_commits: int = 0
    total_prs_opened: int = 0
    total_prs_merged: int = 0
    total_issues_opened: int = 0
    total_issues_closed: int = 0
    total_reviews: int = 0
    total_comments: int = 0
    repos_contributed_to: list[str] = Field(default_factory=list)
    most_active_repos: list[dict] = Field(default_factory=list)

    @classmethod
    def from_activity(
        cls,
        username: str,
        activity: ActivityData,
        period_start: datetime,
        period_end: datetime,
    ) -> "ActivitySummary":
        """Create summary from activity data."""
        # Count commits
        total_commits = len(activity.commits)

        # Count PRs
        prs_opened = len([pr for pr in activity.pull_requests if pr.author == username])
        prs_merged = len([pr for pr in activity.pull_requests if pr.is_merged])

        # Count issues
        issues_opened = len([i for i in activity.issues if i.author == username])
        issues_closed = len([i for i in activity.issues if i.state == "closed"])

        # Count reviews
        total_reviews = len(activity.reviews)

        # Get repos contributed to
        repos = set()
        for commit in activity.commits:
            repos.add(commit.repo)
        for pr in activity.pull_requests:
            repos.add(pr.repo)
        for issue in activity.issues:
            repos.add(issue.repo)

        # Calculate most active repos
        repo_activity: dict[str, int] = {}
        for commit in activity.commits:
            repo_activity[commit.repo] = repo_activity.get(commit.repo, 0) + 1
        for pr in activity.pull_requests:
            repo_activity[pr.repo] = repo_activity.get(pr.repo, 0) + 1
        for issue in activity.issues:
            repo_activity[issue.repo] = repo_activity.get(issue.repo, 0) + 1

        most_active = sorted(
            [{"repo": k, "activity_count": v} for k, v in repo_activity.items()],
            key=lambda x: x["activity_count"],
            reverse=True,
        )[:10]

        return cls(
            username=username,
            period_start=period_start,
            period_end=period_end,
            total_events=len(activity.events),
            total_commits=total_commits,
            total_prs_opened=prs_opened,
            total_prs_merged=prs_merged,
            total_issues_opened=issues_opened,
            total_issues_closed=issues_closed,
            total_reviews=total_reviews,
            repos_contributed_to=list(repos),
            most_active_repos=most_active,
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
