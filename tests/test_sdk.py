"""Tests for GitHubResearcher SDK class."""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_researcher import GitHubResearcher
from github_researcher.exceptions import (
    GitHubResearcherError,
    UserNotFoundError,
)
from github_researcher.models.activity import ActivityData, ActivitySummary, Commit
from github_researcher.models.contribution import ContributionStats
from github_researcher.models.repository import Repository, RepositorySummary
from github_researcher.models.user import FullUserData, SocialData, UserProfile


class TestGitHubResearcherInit:
    """Tests for SDK initialization."""

    def test_init_without_token(self):
        """Test initialization without a token."""
        client = GitHubResearcher()
        assert client.is_authenticated is False

    def test_init_with_token(self):
        """Test initialization with a token."""
        client = GitHubResearcher(token="ghp_test_token")
        assert client.is_authenticated is True

    def test_init_custom_urls(self):
        """Test initialization with custom API URLs."""
        client = GitHubResearcher(
            token="ghp_test",
            api_url="https://api.github.example.com",
            graphql_url="https://api.github.example.com/graphql",
        )
        assert client._config.github_api_url == "https://api.github.example.com"
        assert client._config.github_graphql_url == "https://api.github.example.com/graphql"


class TestGitHubResearcherContextManager:
    """Tests for async context manager behavior."""

    @pytest.mark.asyncio
    async def test_context_manager_initializes(self):
        """Test that context manager initializes clients."""
        async with GitHubResearcher(token="ghp_test") as client:
            assert client._initialized is True
            assert client._rest_client is not None
            assert client._graphql_client is not None

    @pytest.mark.asyncio
    async def test_context_manager_closes(self):
        """Test that context manager closes clients on exit."""
        client = GitHubResearcher(token="ghp_test")
        async with client:
            pass
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_context_manager_unauthenticated(self):
        """Test context manager without authentication."""
        async with GitHubResearcher() as client:
            assert client._initialized is True
            assert client._rest_client is not None
            assert client._graphql_client is None  # No GraphQL without token


class TestGitHubResearcherNotInitialized:
    """Tests for error handling when not initialized."""

    @pytest.mark.asyncio
    async def test_get_profile_without_init_raises(self):
        """Test that calling methods without initialization raises error."""
        client = GitHubResearcher()
        with pytest.raises(GitHubResearcherError, match="Client not initialized"):
            await client.get_profile("testuser")

    @pytest.mark.asyncio
    async def test_get_repos_without_init_raises(self):
        """Test that get_repos without initialization raises error."""
        client = GitHubResearcher()
        with pytest.raises(GitHubResearcherError, match="Client not initialized"):
            await client.get_repos("testuser")

    @pytest.mark.asyncio
    async def test_get_activity_without_init_raises(self):
        """Test that get_activity without initialization raises error."""
        client = GitHubResearcher()
        with pytest.raises(GitHubResearcherError, match="Client not initialized"):
            await client.get_activity("testuser")


class TestGitHubResearcherGetProfile:
    """Tests for get_profile method."""

    @pytest.mark.asyncio
    async def test_get_profile_success(self):
        """Test successful profile retrieval."""
        mock_profile = FullUserData(
            profile=UserProfile(
                username="torvalds",
                name="Linus Torvalds",
                bio="Linux creator",
                public_repos=10,
                followers=1000,
            ),
            social=SocialData(),
        )

        with patch(
            "github_researcher.sdk.ProfileCollector"
        ) as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.collect_full = AsyncMock(return_value=mock_profile)

            async with GitHubResearcher(token="ghp_test") as client:
                result = await client.get_profile("torvalds")

            assert result.profile.username == "torvalds"
            assert result.profile.name == "Linus Torvalds"
            mock_instance.collect_full.assert_called_once_with(
                "torvalds",
                include_followers=False,
                include_following=False,
            )

    @pytest.mark.asyncio
    async def test_get_profile_user_not_found(self):
        """Test that UserNotFoundError is raised for non-existent user."""
        with patch(
            "github_researcher.sdk.ProfileCollector"
        ) as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.collect_full = AsyncMock(
                side_effect=ValueError("User not found")
            )

            async with GitHubResearcher(token="ghp_test") as client:
                with pytest.raises(UserNotFoundError) as exc_info:
                    await client.get_profile("nonexistent_user_12345")

            assert exc_info.value.username == "nonexistent_user_12345"


class TestGitHubResearcherGetRepos:
    """Tests for get_repos method."""

    @pytest.mark.asyncio
    async def test_get_repos_success(self):
        """Test successful repository retrieval."""
        mock_repos = RepositorySummary(
            repos=[
                Repository(
                    name="linux",
                    full_name="torvalds/linux",
                    stargazers_count=150000,
                    forks_count=50000,
                    language="C",
                ),
            ],
            count=1,
            total_stars=150000,
            total_forks=50000,
        )

        with patch(
            "github_researcher.sdk.RepoCollector"
        ) as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.collect_repos = AsyncMock(return_value=mock_repos)

            async with GitHubResearcher(token="ghp_test") as client:
                result = await client.get_repos("torvalds")

            assert result.count == 1
            assert result.repos[0].name == "linux"
            mock_instance.collect_repos.assert_called_once()


class TestGitHubResearcherGetContributions:
    """Tests for get_contributions method."""

    @pytest.mark.asyncio
    async def test_get_contributions_authenticated(self):
        """Test contributions retrieval with authentication."""
        from github_researcher.models.contribution import ContributionCalendar

        mock_contributions = ContributionStats(
            total_commits=1000,
            total_pull_requests=300,
            total_issues=100,
            total_reviews=100,
            calendar=ContributionCalendar(total_contributions=1500),
        )

        with patch(
            "github_researcher.sdk.ContributionCollector"
        ) as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.collect_contributions = AsyncMock(
                return_value=mock_contributions
            )

            async with GitHubResearcher(token="ghp_test") as client:
                result = await client.get_contributions("torvalds")

            assert result is not None
            assert result.total_contributions == 1500

    @pytest.mark.asyncio
    async def test_get_contributions_unauthenticated_returns_none(self):
        """Test that contributions returns None without authentication."""
        async with GitHubResearcher() as client:  # No token
            result = await client.get_contributions("torvalds")
            assert result is None


class TestGitHubResearcherGetActivity:
    """Tests for get_activity method."""

    @pytest.mark.asyncio
    async def test_get_activity_success(self):
        """Test successful activity retrieval."""
        mock_activity = ActivityData(
            commits=[
                Commit(
                    sha="abc123",
                    message="Test commit",
                    author="torvalds",
                    date=datetime.now(),
                    repo="torvalds/linux",
                ),
            ],
        )

        with patch(
            "github_researcher.sdk.ActivityCollector"
        ) as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.collect_activity = AsyncMock(return_value=mock_activity)

            async with GitHubResearcher(token="ghp_test") as client:
                result = await client.get_activity("torvalds", days=30)

            assert len(result.commits) == 1
            assert result.commits[0].author == "torvalds"

    @pytest.mark.asyncio
    async def test_get_activity_passes_auth_flag(self):
        """Test that authentication flag is passed to ActivityCollector."""
        with patch(
            "github_researcher.sdk.ActivityCollector"
        ) as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.collect_activity = AsyncMock(return_value=ActivityData())

            async with GitHubResearcher(token="ghp_test") as client:
                await client.get_activity("torvalds")

            # Verify is_authenticated was passed correctly
            MockCollector.assert_called_once()
            call_kwargs = MockCollector.call_args[1]
            assert call_kwargs["is_authenticated"] is True

    @pytest.mark.asyncio
    async def test_get_activity_unauthenticated(self):
        """Test activity retrieval without authentication."""
        with patch(
            "github_researcher.sdk.ActivityCollector"
        ) as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.collect_activity = AsyncMock(return_value=ActivityData())

            async with GitHubResearcher() as client:  # No token
                await client.get_activity("torvalds")

            call_kwargs = MockCollector.call_args[1]
            assert call_kwargs["is_authenticated"] is False


class TestGitHubResearcherAnalyze:
    """Tests for the full analyze method."""

    @pytest.mark.asyncio
    async def test_analyze_returns_all_data(self):
        """Test that analyze returns complete data structure."""
        mock_profile = FullUserData(
            profile=UserProfile(username="testuser", public_repos=5),
            social=SocialData(),
        )
        mock_repos = RepositorySummary(
            repos=[Repository(name="repo1", full_name="testuser/repo1")],
            count=1,
        )
        mock_contributions = ContributionStats(total_contributions=100)
        mock_activity = ActivityData()
        mock_summary = ActivitySummary(
            username="testuser",
            period_start=datetime.now() - timedelta(days=365),
            period_end=datetime.now(),
        )

        with patch(
            "github_researcher.sdk.ProfileCollector"
        ) as MockProfile, patch(
            "github_researcher.sdk.RepoCollector"
        ) as MockRepo, patch(
            "github_researcher.sdk.ContributionCollector"
        ) as MockContrib, patch(
            "github_researcher.sdk.ActivityCollector"
        ) as MockActivity:
            MockProfile.return_value.collect_full = AsyncMock(return_value=mock_profile)
            MockRepo.return_value.collect_repos = AsyncMock(return_value=mock_repos)
            MockContrib.return_value.collect_contributions = AsyncMock(
                return_value=mock_contributions
            )
            MockActivity.return_value.collect_activity = AsyncMock(
                return_value=mock_activity
            )
            MockActivity.return_value.summarize_activity = MagicMock(
                return_value=mock_summary
            )

            async with GitHubResearcher(token="ghp_test") as client:
                result = await client.analyze("testuser", days=30)

            # Verify structure
            assert "username" in result
            assert result["username"] == "testuser"
            assert "profile" in result
            assert "repositories" in result
            assert "contributions" in result
            assert "activity" in result
            assert "activity_summary" in result
            assert "metadata" in result

            # Verify metadata
            assert result["metadata"]["days_analyzed"] == 30
            assert result["metadata"]["authenticated"] is True

    @pytest.mark.asyncio
    async def test_analyze_without_contributions(self):
        """Test analyze skips contributions when requested."""
        mock_profile = FullUserData(
            profile=UserProfile(username="testuser"),
            social=SocialData(),
        )
        mock_repos = RepositorySummary(repos=[], count=0)
        mock_activity = ActivityData()
        mock_summary = ActivitySummary(
            username="testuser",
            period_start=datetime.now() - timedelta(days=365),
            period_end=datetime.now(),
        )

        with patch(
            "github_researcher.sdk.ProfileCollector"
        ) as MockProfile, patch(
            "github_researcher.sdk.RepoCollector"
        ) as MockRepo, patch(
            "github_researcher.sdk.ContributionCollector"
        ) as MockContrib, patch(
            "github_researcher.sdk.ActivityCollector"
        ) as MockActivity:
            MockProfile.return_value.collect_full = AsyncMock(return_value=mock_profile)
            MockRepo.return_value.collect_repos = AsyncMock(return_value=mock_repos)
            MockActivity.return_value.collect_activity = AsyncMock(
                return_value=mock_activity
            )
            MockActivity.return_value.summarize_activity = MagicMock(
                return_value=mock_summary
            )

            async with GitHubResearcher(token="ghp_test") as client:
                result = await client.analyze(
                    "testuser", include_contributions=False
                )

            # Contributions should not have been fetched
            MockContrib.return_value.collect_contributions.assert_not_called()
            assert result["contributions"] is None


class TestGitHubResearcherClose:
    """Tests for resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(self):
        """Test that close properly cleans up resources."""
        client = GitHubResearcher(token="ghp_test")
        await client._initialize()

        # Mock the close methods
        client._rest_client.close = AsyncMock()
        client._graphql_client.close = AsyncMock()

        await client.close()

        client._rest_client.close.assert_called_once()
        client._graphql_client.close.assert_called_once()
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self):
        """Test that calling close twice doesn't raise errors."""
        client = GitHubResearcher(token="ghp_test")
        await client._initialize()

        # Mock the close methods
        client._rest_client.close = AsyncMock()
        client._graphql_client.close = AsyncMock()

        await client.close()
        # Second close should be safe (clients are None after close)
        await client.close()  # Should not raise
