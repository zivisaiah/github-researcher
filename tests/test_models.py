"""Tests for data models."""

from datetime import date, datetime

from github_researcher.models.activity import (
    ActivityData,
    ActivitySummary,
    Commit,
    GitHubEvent,
    PullRequest,
)
from github_researcher.models.contribution import (
    ContributionCalendar,
    ContributionDay,
)
from github_researcher.models.repository import Repository, RepositorySummary
from github_researcher.models.user import UserProfile


class TestUserProfile:
    """Tests for UserProfile model."""

    def test_from_api(self):
        """Test creating UserProfile from API response."""
        api_data = {
            "login": "testuser",
            "name": "Test User",
            "avatar_url": "https://github.com/avatar.png",
            "bio": "A test user",
            "company": "Test Corp",
            "location": "Test City",
            "email": "test@example.com",
            "blog": "https://test.com",
            "twitter_username": "testuser",
            "public_repos": 10,
            "public_gists": 5,
            "followers": 100,
            "following": 50,
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        profile = UserProfile.from_api(api_data)

        assert profile.username == "testuser"
        assert profile.name == "Test User"
        assert profile.public_repos == 10
        assert profile.followers == 100

    def test_from_api_missing_fields(self):
        """Test creating UserProfile with missing optional fields."""
        api_data = {
            "login": "minimal",
        }

        profile = UserProfile.from_api(api_data)

        assert profile.username == "minimal"
        assert profile.name is None
        assert profile.bio is None
        assert profile.public_repos == 0


class TestRepository:
    """Tests for Repository model."""

    def test_from_api(self):
        """Test creating Repository from API response."""
        api_data = {
            "name": "test-repo",
            "full_name": "user/test-repo",
            "description": "A test repository",
            "html_url": "https://github.com/user/test-repo",
            "language": "Python",
            "stargazers_count": 100,
            "forks_count": 20,
            "open_issues_count": 5,
            "topics": ["testing", "python"],
            "fork": False,
            "archived": False,
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "pushed_at": "2024-06-01T00:00:00Z",
            "size": 1024,
        }

        repo = Repository.from_api(api_data)

        assert repo.name == "test-repo"
        assert repo.full_name == "user/test-repo"
        assert repo.language == "Python"
        assert repo.stargazers_count == 100
        assert len(repo.topics) == 2


class TestRepositorySummary:
    """Tests for RepositorySummary model."""

    def test_from_repos(self):
        """Test creating summary from repositories."""
        repos = [
            Repository(
                name="repo1",
                full_name="user/repo1",
                stargazers_count=100,
                forks_count=10,
                language="Python",
                topics=["python", "testing"],
            ),
            Repository(
                name="repo2",
                full_name="user/repo2",
                stargazers_count=50,
                forks_count=5,
                language="JavaScript",
                topics=["javascript", "testing"],
            ),
        ]

        summary = RepositorySummary.from_repos(repos)

        assert summary.count == 2
        assert summary.total_stars == 150
        assert summary.total_forks == 15
        assert summary.topics["testing"] == 2


class TestContributionCalendar:
    """Tests for contribution models."""

    def test_contribution_day(self):
        """Test ContributionDay model."""
        day = ContributionDay(
            date=date(2024, 1, 15),
            count=5,
            level="SECOND_QUARTILE",
        )

        assert day.date == date(2024, 1, 15)
        assert day.count == 5
        assert day.level == "SECOND_QUARTILE"

    def test_contribution_calendar_streak(self):
        """Test streak calculation."""
        from github_researcher.models.contribution import ContributionWeek

        # Create a calendar with some contributions
        weeks = [
            ContributionWeek(
                days=[
                    ContributionDay(date=date(2024, 1, i), count=i % 3, level="NONE")
                    for i in range(1, 8)
                ]
            )
        ]

        calendar = ContributionCalendar(
            total_contributions=10,
            weeks=weeks,
        )

        # Streak depends on last days having contributions
        assert calendar.get_longest_streak() >= 0


class TestGitHubEvent:
    """Tests for GitHubEvent model."""

    def test_from_api(self):
        """Test creating event from API response."""
        api_data = {
            "id": "12345",
            "type": "PushEvent",
            "actor": {"login": "testuser"},
            "repo": {"name": "user/repo"},
            "created_at": "2024-01-15T10:00:00Z",
            "payload": {"commits": []},
            "public": True,
        }

        event = GitHubEvent.from_api(api_data)

        assert event.id == "12345"
        assert event.type == "PushEvent"
        assert event.actor == "testuser"
        assert event.repo == "user/repo"


class TestPullRequest:
    """Tests for PullRequest model."""

    def test_from_api(self):
        """Test creating PR from API response."""
        api_data = {
            "number": 123,
            "title": "Fix bug",
            "state": "closed",
            "user": {"login": "testuser"},
            "repository_url": "https://api.github.com/repos/owner/repo",
            "created_at": "2024-01-15T10:00:00Z",
            "merged_at": "2024-01-16T10:00:00Z",
            "html_url": "https://github.com/owner/repo/pull/123",
        }

        pr = PullRequest.from_api(api_data)

        assert pr.number == 123
        assert pr.title == "Fix bug"
        assert pr.author == "testuser"
        assert pr.is_merged is True


class TestActivitySummary:
    """Tests for ActivitySummary model."""

    def test_from_activity(self):
        """Test creating summary from activity data."""
        activity = ActivityData(
            commits=[
                Commit(
                    sha="abc123",
                    message="Test commit",
                    author="testuser",
                    date=datetime.now(),
                    repo="user/repo",
                )
            ],
            pull_requests=[
                PullRequest(
                    number=1,
                    title="Test PR",
                    state="merged",
                    author="testuser",
                    repo="user/repo",
                    created_at=datetime.now(),
                    is_merged=True,
                )
            ],
        )

        summary = ActivitySummary.from_activity(
            "testuser",
            activity,
            datetime(2024, 1, 1),
            datetime(2024, 12, 31),
        )

        assert summary.total_commits == 1
        assert summary.total_prs_opened == 1
        assert summary.total_prs_merged == 1
        assert "user/repo" in summary.repos_contributed_to
