"""Output handlers for GitHub Researcher."""

from github_researcher.output.console import Console
from github_researcher.output.json_writer import write_json_report

__all__ = [
    "write_json_report",
    "Console",
]
