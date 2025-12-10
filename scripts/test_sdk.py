#!/usr/bin/env python3
"""CLI utility to test the GitHub Researcher SDK locally."""

import argparse
import asyncio
import json
import logging
import os
import sys

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from github_researcher import GitHubResearcher, __version__


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging based on verbosity level."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def test_profile(client: GitHubResearcher, username: str):
    """Test get_profile method."""
    print(f"\n{'='*50}")
    print(f"Testing get_profile('{username}')")
    print("=" * 50)

    profile = await client.get_profile(username)
    print(f"Name: {profile.profile.name}")
    print(f"Bio: {profile.profile.bio}")
    print(f"Location: {profile.profile.location}")
    print(f"Company: {profile.profile.company}")
    print(f"Public repos: {profile.profile.public_repos}")
    print(f"Followers: {profile.profile.followers}")
    print(f"Following: {profile.profile.following}")
    print(f"Organizations: {[o.login for o in profile.social.organizations]}")
    return profile


async def test_repos(client: GitHubResearcher, username: str):
    """Test get_repos method."""
    print(f"\n{'='*50}")
    print(f"Testing get_repos('{username}')")
    print("=" * 50)

    repos = await client.get_repos(username, max_repos_for_languages=10)
    print(f"Total repos: {repos.count}")
    print(f"Total stars: {repos.total_stars}")
    print(f"Total forks: {repos.total_forks}")
    print(f"Top languages: {dict(list(repos.languages.languages.items())[:5])}")
    print(f"Top repos by stars:")
    for repo in sorted(repos.repos, key=lambda r: r.stargazers_count, reverse=True)[:5]:
        print(f"  - {repo.name}: {repo.stargazers_count} stars")
    return repos


async def test_activity(client: GitHubResearcher, username: str, days: int = 90):
    """Test get_activity method."""
    print(f"\n{'='*50}")
    print(f"Testing get_activity('{username}', days={days})")
    print("=" * 50)

    activity = await client.get_activity(username, days=days, deep=True)
    print(f"Events: {len(activity.events)}")
    print(f"Commits: {len(activity.commits)}")
    print(f"PRs: {len(activity.pull_requests)}")
    print(f"Issues: {len(activity.issues)}")
    print(f"Reviews: {len(activity.reviews)}")

    if activity.events:
        print(f"Recent event types: {set(e.type for e in activity.events[:10])}")
    return activity


async def test_contributions(client: GitHubResearcher, username: str):
    """Test get_contributions method."""
    print(f"\n{'='*50}")
    print(f"Testing get_contributions('{username}')")
    print("=" * 50)

    if not client.is_authenticated:
        print("Skipping - requires authentication")
        return None

    contributions = await client.get_contributions(username)
    if contributions:
        print(f"Total contributions: {contributions.total_contributions}")
        print(f"Commits: {contributions.total_commits}")
        print(f"PRs: {contributions.total_pull_requests}")
        print(f"Issues: {contributions.total_issues}")
        print(f"Reviews: {contributions.total_reviews}")
        print(f"Current streak: {contributions.current_streak} days")
        print(f"Longest streak: {contributions.longest_streak} days")
        if contributions.busiest_day:
            print(
                f"Busiest day: {contributions.busiest_day.date} "
                f"({contributions.busiest_day.count} contributions)"
            )
    return contributions


async def test_full_analysis(client: GitHubResearcher, username: str, days: int = 90):
    """Test the full analyze method."""
    print(f"\n{'='*50}")
    print(f"Testing analyze('{username}', days={days})")
    print("=" * 50)

    report = await client.analyze(username, days=days)

    print(f"\nProfile: {report['profile'].profile.name or username}")
    print(f"Repos: {report['repositories'].count}")

    if report["contributions"]:
        print(f"Contributions: {report['contributions'].total_contributions}")

    summary = report["activity_summary"]
    print(f"\nActivity Summary (last {days} days):")
    print(f"  Commits: {summary.total_commits}")
    print(f"  PRs opened: {summary.total_prs_opened}")
    print(f"  PRs merged: {summary.total_prs_merged}")
    print(f"  Issues opened: {summary.total_issues_opened}")
    print(f"  Reviews: {summary.total_reviews}")
    print(f"  Repos contributed to: {len(summary.repos_contributed_to)}")

    return report


async def main():
    parser = argparse.ArgumentParser(
        description="Test the GitHub Researcher SDK locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/test_sdk.py torvalds
  python scripts/test_sdk.py torvalds --all
  python scripts/test_sdk.py torvalds --profile --repos
  python scripts/test_sdk.py torvalds --analyze --days 30
  python scripts/test_sdk.py torvalds --verbose
  python scripts/test_sdk.py torvalds --output report.json
""",
    )
    parser.add_argument("username", help="GitHub username to analyze")
    parser.add_argument(
        "--token",
        help="GitHub token (default: GITHUB_RESEARCHER_TOKEN or GITHUB_TOKEN env var)",
    )
    parser.add_argument("--days", type=int, default=90, help="Days to analyze (default: 90)")
    parser.add_argument("--profile", action="store_true", help="Test get_profile()")
    parser.add_argument("--repos", action="store_true", help="Test get_repos()")
    parser.add_argument("--activity", action="store_true", help="Test get_activity()")
    parser.add_argument("--contributions", action="store_true", help="Test get_contributions()")
    parser.add_argument("--analyze", action="store_true", help="Test full analyze()")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--output", "-o", help="Save full report to JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Debug output")
    parser.add_argument("--version", action="version", version=f"github-researcher {__version__}")

    args = parser.parse_args()

    setup_logging(verbose=args.verbose, debug=args.debug)

    # Get token
    token = args.token or os.getenv("GITHUB_RESEARCHER_TOKEN") or os.getenv("GITHUB_TOKEN")

    print(f"GitHub Researcher SDK v{__version__}")
    print(f"Authenticated: {'Yes' if token else 'No'}")
    print(f"Analyzing: {args.username}")

    # If no specific test selected, default to profile
    if not any([args.profile, args.repos, args.activity, args.contributions, args.analyze, args.all]):
        args.profile = True

    async with GitHubResearcher(token=token) as client:
        try:
            if args.all or args.profile:
                await test_profile(client, args.username)

            if args.all or args.repos:
                await test_repos(client, args.username)

            if args.all or args.activity:
                await test_activity(client, args.username, args.days)

            if args.all or args.contributions:
                await test_contributions(client, args.username)

            if args.all or args.analyze:
                report = await test_full_analysis(client, args.username, args.days)

                if args.output:
                    # Convert to JSON-serializable format
                    output = {
                        "username": args.username,
                        "metadata": report["metadata"],
                        "profile": {
                            "name": report["profile"].profile.name,
                            "bio": report["profile"].profile.bio,
                            "location": report["profile"].profile.location,
                            "company": report["profile"].profile.company,
                            "public_repos": report["profile"].profile.public_repos,
                            "followers": report["profile"].profile.followers,
                            "following": report["profile"].profile.following,
                        },
                        "repositories": {
                            "total": report["repositories"].count,
                            "stars": report["repositories"].total_stars,
                            "forks": report["repositories"].total_forks,
                            "languages": report["repositories"].languages.languages,
                        },
                        "activity_summary": {
                            "commits": report["activity_summary"].total_commits,
                            "prs_opened": report["activity_summary"].total_prs_opened,
                            "prs_merged": report["activity_summary"].total_prs_merged,
                            "issues_opened": report["activity_summary"].total_issues_opened,
                            "reviews": report["activity_summary"].total_reviews,
                            "repos_contributed_to": report["activity_summary"].repos_contributed_to,
                        },
                    }
                    if report["contributions"]:
                        output["contributions"] = {
                            "total": report["contributions"].total_contributions,
                            "commits": report["contributions"].total_commits,
                            "prs": report["contributions"].total_pull_requests,
                            "issues": report["contributions"].total_issues,
                            "reviews": report["contributions"].total_reviews,
                        }

                    with open(args.output, "w") as f:
                        json.dump(output, f, indent=2, default=str)
                    print(f"\nReport saved to: {args.output}")

            print("\n✓ All tests completed successfully!")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
