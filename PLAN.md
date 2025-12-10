# GitHub User Activity Tracker - Implementation Plan

## Project Overview

A CLI tool to track and extract **public activity** of any GitHub user, including users outside your organization who haven't granted you any access. This system aggregates publicly available activity data from GitHub's APIs to reconstruct everything visible on a user's public GitHub profile.

### Important: GitHub API Access Model

**This project can only access PUBLIC data.** GitHub's API is designed so that:

- ✅ Public activity of ANY user is accessible
- ✅ Public repositories, commits, PRs, issues are visible
- ✅ Public contribution calendar (mosaic) is available via GraphQL
- ✅ Public organization memberships are visible
- ❌ Private repositories of external users are NOT accessible
- ❌ Private organization activity is NOT accessible
- ❌ Private contributions (unless user enabled public visibility) appear as counts only, not repo names

**A GitHub token is used only for higher rate limits** (5,000 requests/hour vs 60/hour unauthenticated) and GraphQL access, NOT for accessing private data of other users.

---

## Architecture Overview

**Type:** CLI Tool (stateless, single-user focus, deep analysis)

```text
github-researcher/
├── src/
│   └── github_researcher/
│       ├── __init__.py
│       ├── cli.py                  # CLI entry point (typer)
│       ├── config.py               # Configuration management
│       ├── models/
│       │   ├── __init__.py
│       │   ├── activity.py         # Activity/event data models
│       │   ├── contribution.py     # Contribution calendar models
│       │   ├── repository.py       # Repository models
│       │   └── user.py             # User profile models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── github_rest_client.py   # GitHub REST API client
│       │   ├── github_graphql_client.py # GitHub GraphQL client
│       │   ├── profile_collector.py    # Profile & social data
│       │   ├── repo_collector.py       # Repository & language data
│       │   ├── activity_collector.py   # Events & activity timeline
│       │   ├── contribution_collector.py # Contribution calendar (GraphQL)
│       │   └── profile_scraper.py      # Optional HTML scraper (pinned repos, achievements)
│       ├── output/
│       │   ├── __init__.py
│       │   ├── json_writer.py      # JSON file output
│       │   └── console.py          # Rich console output
│       └── utils/
│           ├── __init__.py
│           ├── rate_limiter.py     # GitHub API rate limit handler
│           └── pagination.py       # API pagination helpers
├── prompts/
│   └── *.txt                       # LLM prompts (per CLAUDE.md rules)
├── output/                         # Generated JSON reports (gitignored)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── cassettes/                  # VCR cassettes for API mocking
│   └── test_*.py
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## Complete Public Data Collection Framework

Based on research, here's everything visible on a user's public GitHub profile and how to collect it:

### 1. Profile Metadata (REST API)

**Source:** `GET /users/{username}`

| Field | Description |
|-------|-------------|
| `login` | Username |
| `name` | Display name |
| `avatar_url` | Profile picture |
| `bio` | Profile bio |
| `company` | Company/organization |
| `location` | Geographic location |
| `email` | Public email (if exposed) |
| `blog` | Website/blog URL |
| `twitter_username` | Twitter handle |
| `public_repos` | Public repository count |
| `public_gists` | Public gist count |
| `followers` | Follower count |
| `following` | Following count |
| `created_at` | Account creation date |

### 2. Social Graph (REST API)

**Endpoints:**

- `GET /users/{username}/followers` - Who follows this user
- `GET /users/{username}/following` - Who this user follows
- `GET /users/{username}/orgs` - Public organization memberships

### 3. Repository Surface (REST API)

**Endpoints:**

- `GET /users/{username}/repos` - All public repos (with stars, forks, language, topics)
- `GET /repos/{owner}/{repo}` - Detailed repo info (default branch, topics, description)
- `GET /repos/{owner}/{repo}/languages` - Language breakdown per repo

**Aggregated data to build:**

- Complete list of public repositories
- Aggregated language profile across all repos
- Topics/tags frequency
- Stars received / Forks created

### 4. Contribution Calendar - The Mosaic (GraphQL)

**The green squares heatmap.** This is the most important visual on a GitHub profile.

**GraphQL Query:**

```graphql
query($username: String!, $from: DateTime, $to: DateTime) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel  # NONE, FIRST_QUARTILE, SECOND_QUARTILE, THIRD_QUARTILE, FOURTH_QUARTILE
          }
        }
      }
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount  # Private contributions (count only, no details)
    }
  }
}
```

**Note:** If user enabled "show private contributions", those appear as counts in `restrictedContributionsCount` but repo names are NOT exposed.

### 5. Activity Timeline (REST API - Events)

**Endpoint:** `GET /users/{username}/events/public`

Events captured (last 90 days, max 300 events):

| Event Type | Description |
|------------|-------------|
| `PushEvent` | Commits pushed |
| `PullRequestEvent` | PR opened/closed/merged |
| `IssuesEvent` | Issue opened/closed |
| `IssueCommentEvent` | Comment on issue |
| `PullRequestReviewEvent` | PR review submitted |
| `PullRequestReviewCommentEvent` | Comment on PR review |
| `CreateEvent` | Branch/tag/repo created |
| `DeleteEvent` | Branch/tag deleted |
| `ForkEvent` | Forked a repo |
| `WatchEvent` | Starred a repo |
| `ReleaseEvent` | Release published |
| `CommitCommentEvent` | Comment on commit |
| `GollumEvent` | Wiki page edited |
| `PublicEvent` | Repo made public |
| `MemberEvent` | Collaborator added |

### 6. Deep Historical Data (REST API - Search & Commits)

To go beyond the 90-day Events API limit:

**Issues & PRs authored:**

```
GET /search/issues?q=author:{username}+type:issue
GET /search/issues?q=author:{username}+type:pr
```

**Commits across repos:**

```
GET /repos/{owner}/{repo}/commits?author={username}
```

**Reviews authored:**

```
GET /search/issues?q=reviewed-by:{username}+type:pr
```

### 7. Optional: HTML Scraping (for data not in API)

Some profile elements have no API:

| Element | API Available? | Alternative |
|---------|----------------|-------------|
| Pinned repositories | ❌ No REST endpoint | GraphQL `pinnedItems` or HTML scrape |
| Achievements/badges | ❌ No API | HTML scrape |
| README profile | ✅ Fetch `{username}/{username}/README.md` | REST API |
| Sponsors info | ❌ Limited | HTML scrape |

---

## Data Collection Strategy

### Job 1: Profile Snapshot

```python
async def collect_profile(username: str) -> ProfileData:
    """Collect all profile metadata and social data."""
    # Parallel requests
    profile = await rest_client.get(f"/users/{username}")
    orgs = await rest_client.get(f"/users/{username}/orgs")
    followers = await rest_client.get_paginated(f"/users/{username}/followers")
    following = await rest_client.get_paginated(f"/users/{username}/following")
    return ProfileData(...)
```

### Job 2: Repository Inventory

```python
async def collect_repositories(username: str) -> List[Repository]:
    """Collect all public repos with language breakdown."""
    repos = await rest_client.get_paginated(f"/users/{username}/repos")
    # Optionally fetch language breakdown per repo
    for repo in repos:
        repo.languages = await rest_client.get(f"/repos/{repo.full_name}/languages")
    return repos
```

### Job 3: Contribution Calendar (GraphQL)

```python
async def collect_contributions(username: str, year: int) -> ContributionData:
    """Fetch contribution calendar and totals via GraphQL."""
    query = CONTRIBUTIONS_QUERY
    variables = {"username": username, "from": f"{year}-01-01", "to": f"{year}-12-31"}
    result = await graphql_client.execute(query, variables)
    return ContributionData.from_graphql(result)
```

### Job 4: Activity Timeline

```python
async def collect_activity(username: str, deep: bool = True) -> ActivityData:
    """Collect activity from Events API and optionally deep search."""
    # Events API (last 90 days, max 300)
    events = await rest_client.get_paginated(f"/users/{username}/events/public", max_pages=10)

    if deep:
        # Search API for full history
        issues = await search_client.search(f"author:{username} type:issue")
        prs = await search_client.search(f"author:{username} type:pr")
        reviews = await search_client.search(f"reviewed-by:{username} type:pr")

        # Commits from user's repos
        commits = await collect_commits_from_repos(username, repos)

    return ActivityData(events=events, issues=issues, prs=prs, ...)
```

---

## API Endpoints Reference

### REST API Endpoints Used

| Endpoint | Purpose | Rate Cost |
|----------|---------|-----------|
| `GET /users/{username}` | Profile metadata | 1 |
| `GET /users/{username}/repos` | Public repositories | 1/page |
| `GET /users/{username}/orgs` | Organization memberships | 1 |
| `GET /users/{username}/followers` | Followers list | 1/page |
| `GET /users/{username}/following` | Following list | 1/page |
| `GET /users/{username}/events/public` | Public events (90 days) | 1/page |
| `GET /repos/{owner}/{repo}` | Repo details | 1 |
| `GET /repos/{owner}/{repo}/languages` | Language breakdown | 1 |
| `GET /repos/{owner}/{repo}/commits?author={user}` | Commits by author | 1/page |
| `GET /search/issues?q=author:{user}` | Issues/PRs search | 30/min limit |

### GraphQL Queries Used

| Query | Purpose | Rate Cost |
|-------|---------|-----------|
| `user.contributionsCollection` | Contribution calendar + totals | 1 point |
| `user.pinnedItems` | Pinned repositories | 1 point |
| `user.repositories` | Repos with more detail | Variable |

---

## Implementation Phases

### Phase 1: Core Infrastructure

1. Set up Python project structure with CLI (typer)
2. Implement GitHub REST API client (httpx-based, async)
3. Implement GitHub GraphQL client
4. Add rate limiting handler with exponential backoff
5. Create base data models (Pydantic)
6. Set up testing framework with VCR cassettes

### Phase 2: Profile & Repository Collection

1. Implement profile metadata collector
2. Implement social graph collector (followers/following/orgs)
3. Build repository inventory collector
4. Aggregate language statistics across repos

### Phase 3: Contribution Calendar (GraphQL)

1. Implement GraphQL client with authentication
2. Build contribution calendar fetcher
3. Parse contribution totals (commits, PRs, issues, reviews)
4. Handle year-by-year historical data

### Phase 4: Activity Timeline

1. Implement Events API collector (90 days)
2. Build Search API integration for deep history
3. Collect commits across user's repos
4. Normalize and deduplicate activity data

### Phase 5: Output & CLI

1. Build JSON file output
2. Implement rich console output with progress bars
3. Create activity summary statistics
4. Add date range filtering
5. Add verbose/quiet modes

### Phase 6: Optional Enhancements

1. HTML scraper for pinned repos and achievements
2. Profile README fetcher
3. Starred repos collector

---

## Technical Considerations

### Rate Limiting Strategy

```python
# GitHub REST API: 5,000 requests/hour (authenticated)
# GitHub Search API: 30 requests/minute (separate limit)
# GitHub GraphQL API: 5,000 points/hour

RATE_LIMITS = {
    "rest": {"limit": 5000, "window": 3600},
    "search": {"limit": 30, "window": 60},
    "graphql": {"limit": 5000, "window": 3600},
}
```

**Strategies:**

- Track remaining quota via response headers (`X-RateLimit-Remaining`)
- Implement separate rate limiters for REST, Search, and GraphQL
- Use conditional requests (ETag/If-None-Match) to save quota
- Exponential backoff on 403/429 responses
- Queue requests with rate awareness

### Data Retention Limits

| Data Source | Retention | Max Results |
|-------------|-----------|-------------|
| Events API | 90 days | 300 events (10 pages × 30) |
| Search API | Full history | 1,000 results per query |
| Commits API | Full history | Unlimited (paginated) |
| GraphQL Contributions | ~1 year default | Can query historical years |

### Pagination Handling

```python
async def fetch_all_pages(url: str, max_pages: int = None) -> List[dict]:
    """Generic paginated fetcher with Link header parsing."""
    results = []
    page = 1
    while url and (max_pages is None or page <= max_pages):
        response = await client.get(url)
        results.extend(response.json())
        url = parse_next_link(response.headers.get("Link"))
        page += 1
    return results
```

### Error Handling

| Error | Cause | Action |
|-------|-------|--------|
| 404 | User/repo doesn't exist | Return empty, log warning |
| 403 | Rate limited or forbidden | Check headers, backoff, retry |
| 422 | Invalid request | Log error, don't retry |
| 5xx | GitHub server error | Retry with backoff (max 3) |

---

## Data Models

### UserProfile Model

```python
class UserProfile(BaseModel):
    username: str
    name: Optional[str]
    avatar_url: str
    bio: Optional[str]
    company: Optional[str]
    location: Optional[str]
    email: Optional[str]
    blog: Optional[str]
    twitter_username: Optional[str]
    public_repos: int
    public_gists: int
    followers: int
    following: int
    created_at: datetime
    updated_at: datetime
```

### Repository Model

```python
class Repository(BaseModel):
    name: str
    full_name: str
    description: Optional[str]
    html_url: str
    language: Optional[str]
    languages: Dict[str, int]  # language -> bytes
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    topics: List[str]
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime
```

### ContributionCalendar Model

```python
class ContributionDay(BaseModel):
    date: date
    count: int
    level: str  # NONE, FIRST_QUARTILE, etc.

class ContributionCalendar(BaseModel):
    total_contributions: int
    weeks: List[List[ContributionDay]]

class ContributionStats(BaseModel):
    total_commits: int
    total_issues: int
    total_pull_requests: int
    total_reviews: int
    restricted_contributions: int  # Private (count only)
    calendar: ContributionCalendar
```

### Activity Models

```python
class GitHubEvent(BaseModel):
    id: str
    type: str  # PushEvent, PullRequestEvent, etc.
    actor: str
    repo: str
    created_at: datetime
    payload: dict

class ActivitySummary(BaseModel):
    username: str
    period_start: datetime
    period_end: datetime
    total_events: int
    commits: int
    pull_requests_opened: int
    pull_requests_merged: int
    issues_opened: int
    issues_closed: int
    reviews: int
    comments: int
    repos_contributed_to: List[str]
    most_active_repos: List[dict]
```

---

## CLI Interface Design

### Commands

```bash
# Basic usage - full analysis
github-researcher analyze <username>

# With date range
github-researcher analyze <username> --since 2024-01-01 --until 2024-12-31

# Output to specific file
github-researcher analyze <username> --output ./reports/user_activity.json

# Quick mode (events API only, faster)
github-researcher analyze <username> --quick

# Deep mode (default - full commit/PR history via Search API)
github-researcher analyze <username> --deep

# Include optional data (pinned repos, achievements via scraping)
github-researcher analyze <username> --include-scrape

# Verbose output
github-researcher analyze <username> -v

# Show only summary (no JSON file)
github-researcher analyze <username> --summary-only
```

### Output Options

- `--output, -o` - Output JSON file path (default: `output/<username>_<timestamp>.json`)
- `--since` - Start date for analysis (ISO format)
- `--until` - End date for analysis (ISO format)
- `--quick` - Fast mode: events API only (last 90 days, max 300 events)
- `--deep` - Deep mode: traverse Search API for full history (default)
- `--include-scrape` - Include HTML scraping for pinned repos/achievements
- `--summary-only` - Print summary to console, don't save JSON
- `-v, --verbose` - Verbose output with progress details
- `-q, --quiet` - Minimal output

### Example Output File

```json
{
  "username": "torvalds",
  "generated_at": "2024-12-08T10:30:00Z",
  "analysis_mode": "deep",
  "period": {
    "from": "2024-01-01",
    "to": "2024-12-08"
  },
  "profile": {
    "name": "Linus Torvalds",
    "bio": "...",
    "company": null,
    "location": "Portland, OR",
    "email": "torvalds@linux-foundation.org",
    "blog": null,
    "twitter_username": null,
    "public_repos": 7,
    "public_gists": 0,
    "followers": 200000,
    "following": 0,
    "created_at": "2011-09-03T15:26:22Z"
  },
  "social": {
    "followers_count": 200000,
    "following_count": 0,
    "organizations": ["linux-foundation"]
  },
  "repositories": {
    "count": 7,
    "total_stars": 180000,
    "total_forks": 55000,
    "languages": {
      "C": 95.2,
      "Shell": 2.1,
      "Makefile": 1.5
    },
    "repos": [...]
  },
  "contributions": {
    "total": 2500,
    "commits": 2103,
    "pull_requests": 12,
    "issues": 0,
    "reviews": 45,
    "restricted": 0,
    "calendar": [...]
  },
  "activity": {
    "events": [...],
    "commits": [...],
    "pull_requests": [...],
    "issues": [...],
    "reviews": [...]
  },
  "summary": {
    "total_commits": 2103,
    "total_prs_opened": 12,
    "total_prs_merged": 8,
    "total_issues_opened": 0,
    "total_reviews": 45,
    "repos_contributed_to": ["torvalds/linux", "git/git", "..."],
    "most_active_repo": "torvalds/linux",
    "contribution_streak": 45,
    "busiest_day": "2024-03-15",
    "busiest_day_count": 23
  }
}
```

---

## Testing Strategy

### Unit Tests

- Test data models and serialization
- Test rate limit calculations
- Test pagination logic
- Test data aggregation and normalization
- Test date range filtering

### Integration Tests (with VCR)

- Record GitHub API responses as cassettes
- Test against real usernames (e.g., "torvalds", "gvanrossum", "antirez")
- Test Events API pagination
- Test Search API pagination
- Test GraphQL queries
- Test rate limit handling
- Test error scenarios (404, 403, 5xx)

### Security Tests

- Run bandit for security scanning
- Verify no credentials in code
- Verify tokens not logged

---

## Dependencies

```txt
# Core
pydantic>=2.5.0
httpx>=0.26.0           # Async HTTP client for REST API

# CLI
typer>=0.9.0            # CLI framework
rich>=13.7.0            # Rich console output & progress bars

# GraphQL
gql>=3.5.0              # GraphQL client
aiohttp>=3.9.0          # Async transport for gql

# Optional: HTML Scraping
beautifulsoup4>=4.12.0  # HTML parsing (optional)
lxml>=5.0.0             # Fast HTML parser (optional)

# Testing
pytest>=7.4.0
pytest-asyncio>=0.23.0
vcrpy>=5.1.0            # HTTP interaction recording
pytest-cov>=4.1.0
bandit>=1.7.0           # Security scanning

# Utils
python-dotenv>=1.0.0
tenacity>=8.2.0         # Retry logic with backoff
```

---

## Security Considerations

1. **Token Security**
   - Token only used for rate limits and GraphQL access
   - Never log or display tokens
   - Use environment variables (`GITHUB_TOKEN`)

2. **Ethical Considerations**
   - Only access publicly available data
   - Respect GitHub's Terms of Service
   - Implement reasonable rate limiting to not abuse GitHub's API
   - Consider privacy implications of aggregating public data
   - Respect robots.txt if scraping HTML

---

## Limitations & Transparency

### What This Tool Cannot Do

1. Access private repositories of any user
2. See activity in private organizations
3. Get details of private contributions (only counts if user enabled public visibility)
4. Access any data the user hasn't made public
5. Get more than 90 days of events via Events API (use Search API for historical)
6. Get more than 1,000 results per Search API query

### Workarounds Implemented

1. **Events limit (300):** Use Search API for full PR/issue history
2. **90-day events window:** Use Commits API per-repo for historical commits
3. **Search API limit (1,000):** Segment queries by date range if needed
4. **No pinned repos API:** Optional HTML scraping or GraphQL `pinnedItems`

---

## Design Decisions (Resolved)

| Question | Decision |
|----------|----------|
| Persistence | Stateless - fetch fresh each time, output to JSON file |
| Multi-user | Single user per run |
| Depth | Deep analysis by default (Search API for full history) |
| Interface | CLI tool (no web dashboard) |
| Alerting | Not needed |
| HTML Scraping | Optional (for pinned repos, achievements) |

---

## References

- [GitHub REST API - Users](https://docs.github.com/en/rest/users/users)
- [GitHub REST API - Events](https://docs.github.com/en/rest/activity/events)
- [GitHub REST API - Search](https://docs.github.com/en/rest/search)
- [GitHub REST API - Repos](https://docs.github.com/en/rest)
- [GitHub GraphQL API](https://docs.github.com/en/graphql)
- [GitHub Rate Limiting](https://docs.github.com/en/rest/rate-limit)
- [Contributions on Your Profile](https://docs.github.com/en/account-and-profile/concepts/contributions-on-your-profile)
- [About Your Profile](https://docs.github.com/articles/about-your-profile)
- [Viewing Contributions](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/viewing-contributions-on-your-profile)

---

# SDK Migration Plan

## Goal
Transform `github-researcher` from a CLI tool into a distributable Python SDK that can be used programmatically by backend services, while maintaining CLI functionality.

---

## 1. Package Distribution Strategy (Private Domain)

### Recommended: GitHub Packages (PyPI-compatible)
Since this is a private project on GitHub, use **GitHub Packages** as your private PyPI registry:

- **Pros**: Integrated with GitHub, uses existing authentication, free for private repos
- **Installation**: `pip install github-researcher --index-url https://pypi.pkg.github.com/zivisaiah`
- **Authentication**: Uses GitHub token (same as repo access)

### Alternative Options:
| Option | Pros | Cons |
|--------|------|------|
| **AWS CodeArtifact** | Enterprise-grade, IAM integration | Extra AWS setup |
| **Google Artifact Registry** | If already on GCP | Extra GCP setup |
| **Self-hosted PyPI (pypiserver)** | Full control | Infrastructure overhead |
| **Direct Git install** | Simplest | No versioning, slower installs |

---

## 2. SDK Interface Design

### Create a High-Level API (`GitHubResearcher` class)

```python
from github_researcher import GitHubResearcher

# Simple usage
async with GitHubResearcher(token="ghp_xxx") as client:
    report = await client.analyze("torvalds")

    # Or use individual methods
    profile = await client.get_profile("torvalds")
    repos = await client.get_repos("torvalds")
    activity = await client.get_activity("torvalds", days=90)
    contributions = await client.get_contributions("torvalds")
```

### Export Structure (`__init__.py`)
```python
from github_researcher.sdk import GitHubResearcher
from github_researcher.models import (
    UserProfile, Repository, ActivityData, ContributionStats, ...
)
from github_researcher.config import Config
from github_researcher.exceptions import (
    GitHubResearcherError, RateLimitExceededError, ...
)

__all__ = ["GitHubResearcher", "Config", ...]
```

---

## 3. Code Changes Required

### 3.1 Remove Console Dependencies from Services
Currently, services like `ActivityCollector` and `ProfileCollector` have `console.print()` calls. These need to be:
- Replaced with proper logging (`logging` module)
- Or removed entirely (SDK should be silent by default)

Files to modify:
- `services/activity_collector.py` - Remove `rich.console` usage
- `services/profile_collector.py` - Remove `rich.console` usage
- `services/repo_collector.py` - Remove `rich.console` usage
- `services/contribution_collector.py` - Remove `rich.console` usage

### 3.2 Create SDK Entry Point
New file: `src/github_researcher/sdk.py`
- `GitHubResearcher` class that wraps all collectors
- Clean async context manager interface
- Proper resource cleanup

### 3.3 Create Exceptions Module
New file: `src/github_researcher/exceptions.py`
- Consolidate all exceptions
- `GitHubResearcherError` (base)
- `RateLimitExceededError`
- `UserNotFoundError`
- `AuthenticationError`

### 3.4 Update `__init__.py`
Export all public API components cleanly.

---

## 4. CI/CD Pipeline

### GitHub Actions Workflow (`.github/workflows/ci.yml`)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest
      - run: bandit -r src/
```

### GitHub Actions Workflow (`.github/workflows/publish.yml`)

```yaml
name: Publish

on:
  push:
    branches: [main]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # For setuptools-scm
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install build twine
      - run: python -m build
      - name: Publish to GitHub Packages
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.GITHUB_TOKEN }}
        run: |
          twine upload --repository-url https://upload.pypi.pkg.github.com/zivisaiah dist/*
```

### Versioning Strategy
Use **git tags with setuptools-scm** for automatic versioning:

```toml
[build-system]
requires = ["setuptools>=61.0", "setuptools-scm>=8.0"]

[project]
dynamic = ["version"]

[tool.setuptools_scm]
```

Version is derived from git tags:
- `git tag v0.2.0` → version `0.2.0`
- Commits after tag → version `0.2.1.dev3+g1234abc`

---

## 5. Installation Methods for Consumers

### From GitHub Packages (recommended for private)
```bash
# One-time setup: configure pip
pip config set global.extra-index-url https://pypi.pkg.github.com/zivisaiah

# Or in pip.conf / requirements.txt header
--extra-index-url https://__token__:${GITHUB_TOKEN}@pypi.pkg.github.com/zivisaiah

# Install
pip install github-researcher
```

### From Git directly (alternative)
```bash
pip install git+https://github.com/zivisaiah/github-researcher.git@v0.2.0
```

### In requirements.txt
```
github-researcher @ git+https://github.com/zivisaiah/github-researcher.git@v0.2.0
```

---

## 6. Implementation Tasks

### Phase 1: SDK Core
1. Create `src/github_researcher/exceptions.py` - Consolidate exceptions
2. Create `src/github_researcher/sdk.py` - Main SDK entry point
3. Replace `console.print()` with `logging` in all services
4. Update `src/github_researcher/__init__.py` - Clean exports

### Phase 2: CI/CD Setup
5. Create `.github/workflows/ci.yml` - Test on PR and push
6. Create `.github/workflows/publish.yml` - Publish to GitHub Packages
7. Update `pyproject.toml` with setuptools-scm for automatic versioning
8. Enable GitHub Packages for the repository

### Phase 3: Documentation
9. Update README with SDK usage examples
10. Add docstrings to all public API methods

---

## 7. File Structure After Migration

```
github-researcher/
├── .github/
│   └── workflows/
│       ├── ci.yml          # Test on every PR/push
│       └── publish.yml     # Publish on main
├── src/github_researcher/
│   ├── __init__.py         # Clean public exports
│   ├── sdk.py              # NEW: GitHubResearcher class
│   ├── exceptions.py       # NEW: All exceptions
│   ├── config.py
│   ├── cli.py              # Unchanged (uses SDK internally)
│   ├── models/
│   ├── services/           # Modified: logging instead of console
│   ├── output/
│   └── utils/
├── pyproject.toml          # Updated with setuptools-scm
└── README.md               # Updated with SDK examples
```

---

## Decision Points

1. **Package Registry**: GitHub Packages (recommended) vs AWS CodeArtifact vs other?
2. **Versioning**: Manual vs git-tag-based (setuptools-scm)?
3. **Logging**: Use Python `logging` module, or allow passing a custom logger?
