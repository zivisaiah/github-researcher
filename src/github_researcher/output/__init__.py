"""Output handlers for GitHub Researcher."""

from github_researcher.output.json_writer import write_json_report
from github_researcher.output.console import Console

__all__ = [
    "write_json_report",
    "Console",
]
