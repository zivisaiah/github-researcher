"""CLI interface for GitHub Researcher."""

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from github_researcher import __version__
from github_researcher.config import get_config
from github_researcher.output.console import Console as OutputConsole
from github_researcher.output.json_writer import build_report, write_json_report

app = typer.Typer(
    name="github-researcher",
    help="Track and analyze public GitHub user activity",
    add_completion=False,
)

console = Console()


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        console.print(f"github-researcher version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """GitHub Researcher - Track and analyze public GitHub user activity."""
    pass


@app.command()
def analyze(
    username: str = typer.Argument(..., help="GitHub username to analyze"),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSON file path",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Start date for analysis (YYYY-MM-DD)",
    ),
    until: Optional[str] = typer.Option(
        None,
        "--until",
        help="End date for analysis (YYYY-MM-DD)",
    ),
    quick: bool = typer.Option(
        False,
        "--quick",
        help="Quick mode: events API only (last 90 days)",
    ),
    deep: bool = typer.Option(
        True,
        "--deep/--no-deep",
        help="Deep mode: full history via Search API (default)",
    ),
    summary_only: bool = typer.Option(
        False,
        "--summary-only",
        help="Print summary only, don't save JSON",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output",
    ),
):
    """Analyze a GitHub user's public activity.

    Collects and analyzes:
    - Profile information
    - Public repositories
    - Contribution calendar (requires GitHub token)
    - Activity timeline (events, commits, PRs, issues)

    Examples:
        github-researcher analyze torvalds
        github-researcher analyze torvalds --since 2024-01-01
        github-researcher analyze torvalds --quick --summary-only
    """
    # Parse dates
    from_date = None
    to_date = None

    if since:
        try:
            from_date = date.fromisoformat(since)
        except ValueError:
            console.print(f"[red]Invalid date format: {since}. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)

    if until:
        try:
            to_date = date.fromisoformat(until)
        except ValueError:
            console.print(f"[red]Invalid date format: {until}. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)

    # Default to last year if no dates specified
    if to_date is None:
        to_date = date.today()
    if from_date is None:
        from_date = to_date - timedelta(days=365)

    # Quick mode overrides deep
    if quick:
        deep = False

    mode = "quick" if quick else "deep"

    # Run async analysis
    try:
        asyncio.run(
            _run_analysis(
                username=username,
                output_path=output,
                from_date=from_date,
                to_date=to_date,
                deep=deep,
                mode=mode,
                summary_only=summary_only,
                verbose=verbose,
                quiet=quiet,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis cancelled[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


async def _run_analysis(
    username: str,
    output_path: Optional[Path],
    from_date: date,
    to_date: date,
    deep: bool,
    mode: str,
    summary_only: bool,
    verbose: bool,
    quiet: bool,
):
    """Run the analysis asynchronously."""
    from github_researcher.services.github_rest_client import GitHubRestClient
    from github_researcher.services.github_graphql_client import GitHubGraphQLClient
    from github_researcher.services.profile_collector import ProfileCollector
    from github_researcher.services.repo_collector import RepoCollector
    from github_researcher.services.contribution_collector import ContributionCollector
    from github_researcher.services.activity_collector import ActivityCollector
    from github_researcher.models.activity import ActivityData, ActivitySummary
    from github_researcher.models.contribution import ContributionStats
    from github_researcher.utils.rate_limiter import (
        get_rate_limiter,
        check_rate_limit_from_api,
        check_and_report_rate_limit,
    )

    output_console = OutputConsole(verbose=verbose, quiet=quiet)
    config = get_config()

    output_console.print_header(username)

    if not config.is_authenticated:
        output_console.print_warning(
            "No GitHub token found. Using unauthenticated access (60 requests/hour).\n"
            "Set GITHUB_TOKEN environment variable for higher rate limits and contribution data."
        )
        output_console.print()

    # Check rate limit before starting
    rate_info = await check_rate_limit_from_api(
        api_url=config.github_api_url,
        token=config.github_token,
    )
    if not check_and_report_rate_limit(rate_info, config.is_authenticated):
        return  # Exit if rate limit exhausted

    # Initialize clients
    rate_limiter = get_rate_limiter()
    rest_client = GitHubRestClient(config=config, rate_limiter=rate_limiter)

    graphql_client = None
    if config.is_authenticated:
        graphql_client = GitHubGraphQLClient(config=config, rate_limiter=rate_limiter)

    try:
        # Initialize collectors
        profile_collector = ProfileCollector(rest_client, graphql_client)
        repo_collector = RepoCollector(rest_client, graphql_client)
        activity_collector = ActivityCollector(rest_client, is_authenticated=config.is_authenticated)

        contribution_collector = None
        if graphql_client:
            contribution_collector = ContributionCollector(graphql_client)

        # Collect data with progress
        with output_console.create_progress() as progress:
            # Profile task
            profile_task = progress.add_task("Fetching profile...", total=None)
            user_data = await profile_collector.collect_full(
                username,
                include_followers=False,  # Skip full list for speed
                include_following=False,
            )
            progress.update(profile_task, completed=True)

            # Repos task
            repo_task = progress.add_task("Fetching repositories...", total=None)
            repos = await repo_collector.collect_repos(
                username,
                include_languages=True,
                max_repos_for_languages=30,
            )
            progress.update(repo_task, completed=True)

            # Contributions task (GraphQL)
            contributions = None
            if contribution_collector:
                contrib_task = progress.add_task("Fetching contributions...", total=None)
                try:
                    contributions = await contribution_collector.collect_contributions(
                        username, from_date, to_date
                    )
                except Exception as e:
                    output_console.print_warning(f"Failed to fetch contributions: {e}")
                progress.update(contrib_task, completed=True)

            # Activity task
            activity_task = progress.add_task(
                f"Fetching activity ({'deep' if deep else 'quick'} mode)...",
                total=None,
            )

            # Get user's repo names for commit search
            user_repos = [r.full_name for r in repos.repos[:20]] if deep else []

            from_datetime = datetime.combine(from_date, datetime.min.time())
            to_datetime = datetime.combine(to_date, datetime.max.time())

            activity = await activity_collector.collect_activity(
                username,
                since=from_datetime if deep else None,
                until=to_datetime if deep else None,
                deep=deep,
                user_repos=user_repos,
            )
            progress.update(activity_task, completed=True)

        # Create summary
        activity_summary = activity_collector.summarize_activity(
            username, activity, from_datetime, to_datetime
        )

        # Build report
        report = build_report(
            username=username,
            user_data=user_data,
            repos=repos,
            contributions=contributions,
            activity=activity,
            activity_summary=activity_summary,
            mode=mode,
            from_date=from_date,
            to_date=to_date,
        )

        # Output
        output_console.print_full_summary(report)

        if not summary_only:
            output_file = write_json_report(report, output_path, username)
            output_console.print_output_path(str(output_file))

        output_console.print_success("\nAnalysis complete!")

    finally:
        # Cleanup
        await rest_client.close()
        if graphql_client:
            await graphql_client.close()


@app.command()
def check_token():
    """Check GitHub token configuration and rate limits."""
    config = get_config()

    if config.is_authenticated:
        console.print("[green]GitHub token is configured[/green]")
        console.print(f"Rate limit: {config.effective_rate_limit} requests/hour")
        console.print("GraphQL API: Available")
        console.print("Search API: Full access")
    else:
        console.print("[yellow]No GitHub token configured[/yellow]")
        console.print(f"Rate limit: {config.effective_rate_limit} requests/hour")
        console.print("GraphQL API: Not available")
        console.print("Search API: Limited")
        console.print()
        console.print("To configure a token:")
        console.print("  export GITHUB_TOKEN=your_token_here")
        console.print()
        console.print("Create a token at: https://github.com/settings/tokens")
        console.print("No special scopes needed for public data access.")


if __name__ == "__main__":
    app()
