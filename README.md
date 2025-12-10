# GitHub Researcher

SDK and CLI tool to track and analyze public GitHub user activity.

## Features

- Collect user profiles and social data
- Analyze public repositories and language statistics
- Fetch contribution calendar data (requires authentication)
- Track activity history: events, commits, PRs, issues, reviews
- Rate limit handling with automatic backoff
- Works with or without authentication (higher limits with token)

## Installation

### From Git (recommended for private use)

```bash
pip install git+https://github.com/zivisaiah/github-researcher.git
```

### From source

```bash
git clone https://github.com/zivisaiah/github-researcher.git
cd github-researcher
pip install -e .
```

## Configuration

Set your GitHub token for higher rate limits (5,000/hour vs 60/hour):

```bash
export GITHUB_RESEARCHER_TOKEN=ghp_your_token_here
```

Create a token at: https://github.com/settings/tokens
No special scopes needed for public data access.

## SDK Usage

```python
import asyncio
from github_researcher import GitHubResearcher

async def main():
    async with GitHubResearcher(token="ghp_xxx") as client:
        # Full analysis
        report = await client.analyze("torvalds")
        print(f"Total commits: {report['activity_summary'].commits}")

        # Or use individual methods
        profile = await client.get_profile("torvalds")
        print(f"Name: {profile.profile.name}")

        repos = await client.get_repos("torvalds")
        print(f"Public repos: {repos.total_count}")

        # Activity (last 90 days from Events API, full history with auth)
        activity = await client.get_activity("torvalds", days=365)
        print(f"PRs opened: {len(activity.pull_requests)}")

        # Contributions (requires authentication)
        contributions = await client.get_contributions("torvalds")
        if contributions:
            print(f"Total contributions: {contributions.total_contributions}")

asyncio.run(main())
```

### SDK Methods

| Method | Description | Auth Required |
|--------|-------------|---------------|
| `analyze(username)` | Full analysis returning all data | No (partial) |
| `get_profile(username)` | User profile and social data | No |
| `get_repos(username)` | Public repositories | No |
| `get_activity(username, days)` | Events, commits, PRs, issues | No (partial) |
| `get_contributions(username)` | Contribution calendar | Yes |
| `get_activity_summary(username)` | Aggregated activity stats | No (partial) |

### Models

All data is returned as Pydantic models:

- `UserProfile`, `SocialData` - User information
- `Repository`, `RepositorySummary` - Repository data
- `ContributionStats`, `ContributionCalendar` - Contribution data
- `ActivityData`, `ActivitySummary` - Activity history
- `GitHubEvent`, `PullRequest`, `Issue`, `Commit` - Individual items

## CLI Usage

```bash
# Basic analysis
github-researcher analyze torvalds

# With date range
github-researcher analyze torvalds --since 2024-01-01 --until 2024-12-31

# Quick mode (events API only, faster)
github-researcher analyze torvalds --quick

# Output to specific file
github-researcher analyze torvalds --output ./reports/torvalds.json

# Summary only (no JSON file)
github-researcher analyze torvalds --summary-only

# Check token configuration
github-researcher check-token
```

## Rate Limits

| Mode | Limit | Notes |
|------|-------|-------|
| Unauthenticated | 60 requests/hour | Limited to Events API |
| Authenticated | 5,000 requests/hour | Full access including Search API |
| Search API | 30 requests/minute | Separate limit for PR/issue queries |

## API Limitations

- **Events API**: Last 90 days, max 300 events
- **Search API**: Requires authentication for `author:` queries
- **Private data**: Only public repositories and activity are accessible
- **Contribution calendar**: Requires authentication (GraphQL API)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/

# Run security scan
bandit -r src/
```

## License

MIT
