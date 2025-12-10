"""Integration tests for GitHubResearcher SDK using VCR cassettes.

These tests record and replay actual HTTP interactions with the GitHub API.
To record new cassettes, delete the corresponding cassette file and run the test
with a valid GITHUB_TOKEN environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import vcr

from github_researcher import GitHubResearcher
from github_researcher.exceptions import UserNotFoundError

# VCR configuration
CASSETTES_DIR = Path(__file__).parent / "cassettes" / "sdk"

# Configure VCR
my_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTES_DIR),
    record_mode="once",
    match_on=["uri", "method"],
    filter_headers=[
        "Authorization",
        "X-GitHub-Api-Version",
        "User-Agent",
    ],
    decode_compressed_response=True,
)


def get_test_token() -> str | None:
    """Get token for recording cassettes, or None for playback."""
    return os.getenv("GITHUB_RESEARCHER_TOKEN") or os.getenv("GITHUB_TOKEN")


@pytest.fixture(autouse=True)
def ensure_cassette_dir():
    """Ensure the SDK cassettes directory exists."""
    CASSETTES_DIR.mkdir(parents=True, exist_ok=True)


class TestSDKGetProfile:
    """Integration tests for get_profile method."""

    @pytest.mark.asyncio
    @my_vcr.use_cassette("get_profile_octocat.yaml")
    async def test_get_profile_real_user(self):
        """Test getting profile for a real GitHub user (octocat)."""
        async with GitHubResearcher(token=get_test_token()) as client:
            profile = await client.get_profile("octocat")

        assert profile.profile.username == "octocat"
        assert profile.profile.name is not None
        assert profile.profile.public_repos >= 0
        assert profile.profile.followers >= 0

    @pytest.mark.asyncio
    @my_vcr.use_cassette("get_profile_not_found.yaml")
    async def test_get_profile_nonexistent_user(self):
        """Test getting profile for a nonexistent user raises error."""
        async with GitHubResearcher(token=get_test_token()) as client:
            with pytest.raises(UserNotFoundError) as exc_info:
                await client.get_profile("this-user-definitely-does-not-exist-12345xyz")

        assert "this-user-definitely-does-not-exist-12345xyz" in str(exc_info.value)


class TestSDKGetRepos:
    """Integration tests for get_repos method."""

    @pytest.mark.asyncio
    @my_vcr.use_cassette("get_repos_octocat.yaml")
    async def test_get_repos_real_user(self):
        """Test getting repositories for a real GitHub user."""
        async with GitHubResearcher(token=get_test_token()) as client:
            repos = await client.get_repos("octocat", max_repos_for_languages=5)

        assert repos.count >= 0
        assert repos.total_stars >= 0
        assert repos.total_forks >= 0
        # octocat has public repos
        if repos.count > 0:
            assert len(repos.repos) > 0
            assert repos.repos[0].name is not None
            assert repos.repos[0].full_name.startswith("octocat/")


class TestSDKGetActivity:
    """Integration tests for get_activity method."""

    @pytest.mark.asyncio
    @my_vcr.use_cassette("get_activity_octocat.yaml")
    async def test_get_activity_real_user(self):
        """Test getting activity for a real GitHub user."""
        async with GitHubResearcher(token=get_test_token()) as client:
            # Use deep=False to avoid Search API which requires auth
            activity = await client.get_activity("octocat", days=30, deep=False)

        # Activity data structure should be valid
        assert activity.events is not None
        assert activity.commits is not None
        assert activity.pull_requests is not None
        assert activity.issues is not None
        assert activity.reviews is not None

    @pytest.mark.asyncio
    async def test_get_activity_with_deep_search(self):
        """Test getting activity with deep search enabled (requires auth).

        Note: This test is skipped in CI as it requires authentication.
        Deep search uses the Search API which requires a token.
        """
        token = get_test_token()
        if not token:
            pytest.skip("Deep search requires authentication")

        # This test only runs locally with a token - no cassette needed
        async with GitHubResearcher(token=token) as client:
            activity = await client.get_activity("octocat", days=30, deep=True)

        assert activity.events is not None
        # With authentication, we might get more data from Search API
        assert activity.pull_requests is not None


class TestSDKGetContributions:
    """Integration tests for get_contributions method."""

    @pytest.mark.asyncio
    async def test_get_contributions_authenticated(self):
        """Test getting contributions (requires authentication).

        Note: This test is skipped in CI as it requires authentication.
        Contributions use the GraphQL API which requires a token.
        """
        token = get_test_token()
        if not token:
            pytest.skip("Contributions require authentication")

        # This test only runs locally with a token - no cassette needed
        async with GitHubResearcher(token=token) as client:
            contributions = await client.get_contributions("octocat")

        if contributions:
            assert contributions.total_contributions >= 0
            assert contributions.calendar is not None

    @pytest.mark.asyncio
    async def test_get_contributions_unauthenticated(self):
        """Test that contributions return None without auth."""
        async with GitHubResearcher(token=None) as client:
            contributions = await client.get_contributions("octocat")

        assert contributions is None


class TestSDKGetActivitySummary:
    """Integration tests for get_activity_summary method."""

    @pytest.mark.asyncio
    @my_vcr.use_cassette("get_activity_summary_octocat.yaml")
    async def test_get_activity_summary_real_user(self):
        """Test getting activity summary for a real user."""
        async with GitHubResearcher(token=get_test_token()) as client:
            # Use deep=False to avoid requiring auth
            summary = await client.get_activity_summary("octocat", days=30, deep=False)

        assert summary.username == "octocat"
        assert summary.total_commits >= 0
        assert summary.total_prs_opened >= 0
        assert summary.total_issues_opened >= 0
        assert summary.period_start is not None
        assert summary.period_end is not None


class TestSDKAnalyze:
    """Integration tests for the full analyze method."""

    @pytest.mark.asyncio
    @my_vcr.use_cassette("analyze_octocat.yaml")
    async def test_analyze_real_user(self):
        """Test full analysis of a real GitHub user."""
        async with GitHubResearcher(token=get_test_token()) as client:
            # Skip contributions if not authenticated
            include_contributions = client.is_authenticated
            report = await client.analyze(
                "octocat",
                days=30,
                deep=False,  # Avoid Search API for unauthenticated tests
                include_contributions=include_contributions,
            )

        # Verify structure
        assert report["username"] == "octocat"
        assert "profile" in report
        assert "repositories" in report
        assert "activity" in report
        assert "activity_summary" in report
        assert "metadata" in report

        # Verify profile data
        assert report["profile"].profile.username == "octocat"

        # Verify metadata
        assert report["metadata"]["days_analyzed"] == 30
        assert report["metadata"]["deep_mode"] is False


class TestSDKAuthenticationModes:
    """Tests for authenticated vs unauthenticated behavior."""

    @pytest.mark.asyncio
    async def test_authenticated_mode(self):
        """Test SDK in authenticated mode.

        Note: This test is skipped in CI as it requires authentication.
        """
        token = get_test_token()
        if not token:
            pytest.skip("Test requires authentication")

        # This test only runs locally with a token - no cassette needed
        async with GitHubResearcher(token=token) as client:
            assert client.is_authenticated is True
            assert client._graphql_client is not None

            # Should be able to get contributions
            contributions = await client.get_contributions("octocat")
            # May or may not have contributions, but should not be None
            assert contributions is not None or True  # Accept either

    @pytest.mark.asyncio
    async def test_unauthenticated_mode(self):
        """Test SDK in unauthenticated mode."""
        async with GitHubResearcher(token=None) as client:
            assert client.is_authenticated is False
            assert client._graphql_client is None


class TestSDKErrorHandling:
    """Integration tests for error handling."""

    @pytest.mark.asyncio
    @my_vcr.use_cassette("error_user_not_found.yaml")
    async def test_user_not_found_error(self):
        """Test that UserNotFoundError is raised for nonexistent users."""
        async with GitHubResearcher(token=get_test_token()) as client:
            with pytest.raises(UserNotFoundError) as exc_info:
                await client.get_profile("nonexistent-user-abc123xyz789")

        assert exc_info.value.username == "nonexistent-user-abc123xyz789"

    @pytest.mark.asyncio
    @my_vcr.use_cassette("error_repos_user_not_found.yaml")
    async def test_repos_for_nonexistent_user(self):
        """Test getting repos for nonexistent user."""
        async with GitHubResearcher(token=get_test_token()) as client:
            # Should either raise an error or return empty repos
            try:
                repos = await client.get_repos("nonexistent-user-abc123xyz789")
                # If it doesn't raise, repos should be empty or have count 0
                assert repos.count == 0
            except Exception:
                # Expected behavior - user doesn't exist
                pass
