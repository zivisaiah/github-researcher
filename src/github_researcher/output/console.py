"""Rich console output for analysis results."""

from typing import Any

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table


class Console:
    """Wrapper for rich console output."""

    def __init__(self, verbose: bool = False, quiet: bool = False):
        self.console = RichConsole()
        self.verbose = verbose
        self.quiet = quiet

    def print(self, *args, **kwargs):
        """Print to console (respects quiet mode)."""
        if not self.quiet:
            self.console.print(*args, **kwargs)

    def print_verbose(self, *args, **kwargs):
        """Print only in verbose mode."""
        if self.verbose and not self.quiet:
            self.console.print(*args, **kwargs)

    def print_error(self, message: str):
        """Print error message."""
        self.console.print(f"[red]Error:[/red] {message}")

    def print_warning(self, message: str):
        """Print warning message."""
        self.console.print(f"[yellow]Warning:[/yellow] {message}")

    def print_success(self, message: str):
        """Print success message."""
        if not self.quiet:
            self.console.print(f"[green]{message}[/green]")

    def create_progress(self) -> Progress:
        """Create a progress bar context."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            disable=self.quiet,
        )

    def print_header(self, username: str):
        """Print analysis header."""
        if self.quiet:
            return

        self.console.print()
        self.console.print(
            Panel(
                f"[bold blue]GitHub Activity Analysis[/bold blue]\n[dim]User: {username}[/dim]",
                expand=False,
            )
        )
        self.console.print()

    def print_profile_summary(self, profile: dict[str, Any]):
        """Print user profile summary."""
        if self.quiet:
            return

        table = Table(title="Profile", show_header=False, expand=False)
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Name", profile.get("name") or profile.get("username", ""))
        table.add_row(
            "Bio",
            (profile.get("bio") or "")[:60] + "..."
            if len(profile.get("bio") or "") > 60
            else profile.get("bio") or "-",
        )
        table.add_row("Location", profile.get("location") or "-")
        table.add_row("Company", profile.get("company") or "-")
        table.add_row("Public Repos", str(profile.get("public_repos", 0)))
        table.add_row("Followers", str(profile.get("followers", 0)))
        table.add_row("Following", str(profile.get("following", 0)))

        self.console.print(table)
        self.console.print()

    def print_repo_summary(self, repos: dict[str, Any]):
        """Print repository summary."""
        if self.quiet:
            return

        table = Table(title="Repositories", show_header=False, expand=False)
        table.add_column("Metric", style="dim")
        table.add_column("Value")

        table.add_row("Total Repos", str(repos.get("count", 0)))
        table.add_row("Total Stars", str(repos.get("total_stars", 0)))
        table.add_row("Total Forks", str(repos.get("total_forks", 0)))

        # Top languages
        languages = repos.get("languages", {})
        top_langs = list(languages.items())[:5]
        if top_langs:
            lang_str = ", ".join([f"{lang} ({pct:.1f}%)" for lang, pct in top_langs])
            table.add_row("Top Languages", lang_str)

        self.console.print(table)
        self.console.print()

    def print_contribution_summary(self, contributions: dict[str, Any]):
        """Print contribution summary."""
        if self.quiet:
            return

        if "note" in contributions:
            self.console.print(f"[yellow]{contributions['note']}[/yellow]")
            return

        table = Table(title="Contributions (Last Year)", show_header=False, expand=False)
        table.add_column("Metric", style="dim")
        table.add_column("Value")

        table.add_row("Total", str(contributions.get("total", 0)))
        table.add_row("Commits", str(contributions.get("commits", 0)))
        table.add_row("Pull Requests", str(contributions.get("pull_requests", 0)))
        table.add_row("Issues", str(contributions.get("issues", 0)))
        table.add_row("Code Reviews", str(contributions.get("reviews", 0)))
        table.add_row("Current Streak", f"{contributions.get('current_streak', 0)} days")
        table.add_row("Longest Streak", f"{contributions.get('longest_streak', 0)} days")

        busiest = contributions.get("busiest_day")
        if busiest:
            table.add_row(
                "Busiest Day",
                f"{busiest} ({contributions.get('busiest_day_count', 0)} contributions)",
            )

        self.console.print(table)
        self.console.print()

    def print_activity_summary(self, summary: dict[str, Any]):
        """Print activity summary."""
        if self.quiet:
            return

        table = Table(title="Activity Summary", show_header=False, expand=False)
        table.add_column("Metric", style="dim")
        table.add_column("Value")

        table.add_row("Commits", str(summary.get("total_commits", 0)))
        table.add_row("PRs Opened", str(summary.get("total_prs_opened", 0)))
        table.add_row("PRs Merged", str(summary.get("total_prs_merged", 0)))
        table.add_row("Issues Opened", str(summary.get("total_issues_opened", 0)))
        table.add_row("Reviews", str(summary.get("total_reviews", 0)))
        table.add_row("Repos Contributed To", str(len(summary.get("repos_contributed_to", []))))

        self.console.print(table)
        self.console.print()

        # Most active repos
        most_active = summary.get("most_active_repos", [])
        if most_active:
            repo_table = Table(title="Most Active Repositories", expand=False)
            repo_table.add_column("Repository")
            repo_table.add_column("Activity", justify="right")

            for repo in most_active[:5]:
                repo_table.add_row(repo.get("repo", ""), str(repo.get("activity_count", 0)))

            self.console.print(repo_table)
            self.console.print()

    def print_full_summary(self, report: dict[str, Any]):
        """Print complete analysis summary."""
        if self.quiet:
            return

        self.print_header(report.get("username", ""))
        self.print_profile_summary(report.get("profile", {}))
        self.print_repo_summary(report.get("repositories", {}))
        self.print_contribution_summary(report.get("contributions", {}))
        self.print_activity_summary(report.get("summary", {}))

        # Footer
        self.console.print(f"[dim]Analysis completed at {report.get('generated_at', '')}[/dim]")
        self.console.print(f"[dim]Mode: {report.get('analysis_mode', 'unknown')}[/dim]")

    def print_output_path(self, path: str):
        """Print output file path."""
        if not self.quiet:
            self.console.print(f"\n[green]Report saved to:[/green] {path}")
