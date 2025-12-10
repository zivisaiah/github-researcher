"""GitHub Researcher - Track and analyze public GitHub user activity.

This SDK provides tools to collect and analyze public GitHub user data including:
- User profiles and social data
- Public repositories and language statistics
- Contribution calendar (requires authentication)
- Activity history (events, commits, PRs, issues, reviews)

Example usage:
    ```python
    from github_researcher import GitHubResearcher

    async with GitHubResearcher(token="ghp_xxx") as client:
        report = await client.analyze("torvalds")
        print(f"Total commits: {report['activity_summary'].commits}")
    ```
"""

from github_researcher.config import Config
from github_researcher.exceptions import (
    AuthenticationError,
    GitHubAPIError,
    GitHubGraphQLError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubResearcherError,
    RateLimitExceededError,
    UserNotFoundError,
)
from github_researcher.models import (
    ActivityData,
    ActivitySummary,
    Commit,
    ContributionCalendar,
    ContributionDay,
    ContributionStats,
    GitHubEvent,
    Issue,
    PullRequest,
    Repository,
    RepositorySummary,
    SocialData,
    UserProfile,
)
from github_researcher.sdk import GitHubResearcher

try:
    from github_researcher._version import version as __version__
except ImportError:
    __version__ = "0.0.0.dev0"

__all__ = [
    # Main SDK class
    "GitHubResearcher",
    # Configuration
    "Config",
    # Exceptions
    "GitHubResearcherError",
    "GitHubAPIError",
    "GitHubRateLimitError",
    "GitHubNotFoundError",
    "GitHubGraphQLError",
    "RateLimitExceededError",
    "UserNotFoundError",
    "AuthenticationError",
    # Models - User
    "UserProfile",
    "SocialData",
    # Models - Repository
    "Repository",
    "RepositorySummary",
    # Models - Contribution
    "ContributionDay",
    "ContributionCalendar",
    "ContributionStats",
    # Models - Activity
    "GitHubEvent",
    "PullRequest",
    "Issue",
    "Commit",
    "ActivityData",
    "ActivitySummary",
]
