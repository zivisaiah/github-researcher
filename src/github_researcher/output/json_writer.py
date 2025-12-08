"""JSON output writer for analysis reports."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from github_researcher.models.activity import ActivityData, ActivitySummary
from github_researcher.models.contribution import ContributionStats
from github_researcher.models.repository import RepositorySummary
from github_researcher.models.user import FullUserData


class AnalysisReport(BaseModel):
    """Complete analysis report for JSON output."""

    username: str
    generated_at: datetime
    analysis_mode: str  # "quick" or "deep"
    period: dict[str, Optional[str]]  # {"from": "...", "to": "..."}
    profile: dict[str, Any]
    social: dict[str, Any]
    repositories: dict[str, Any]
    contributions: dict[str, Any]
    activity: dict[str, Any]
    summary: dict[str, Any]


def serialize_for_json(obj: Any) -> Any:
    """Convert objects to JSON-serializable format."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, BaseModel):
        return obj.model_dump()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif hasattr(obj, "__dict__"):
        return serialize_for_json(obj.__dict__)
    return obj


def build_report(
    username: str,
    user_data: FullUserData,
    repos: RepositorySummary,
    contributions: Optional[ContributionStats],
    activity: ActivityData,
    activity_summary: ActivitySummary,
    mode: str = "deep",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> dict[str, Any]:
    """Build a complete analysis report.

    Args:
        username: GitHub username
        user_data: User profile and social data
        repos: Repository summary
        contributions: Contribution statistics (may be None without token)
        activity: Raw activity data
        activity_summary: Activity statistics summary
        mode: Analysis mode ("quick" or "deep")
        from_date: Analysis start date
        to_date: Analysis end date

    Returns:
        Dictionary ready for JSON serialization
    """
    # Profile section
    profile = serialize_for_json(user_data.profile.model_dump())

    # Social section
    social = {
        "followers_count": user_data.social.followers_count,
        "following_count": user_data.social.following_count,
        "organizations": [
            {"login": org.login, "name": org.name}
            for org in user_data.social.organizations
        ],
    }

    # Repositories section
    repositories = {
        "count": repos.count,
        "total_stars": repos.total_stars,
        "total_forks": repos.total_forks,
        "languages": repos.languages.percentages,
        "top_topics": dict(
            sorted(repos.topics.items(), key=lambda x: x[1], reverse=True)[:10]
        ),
        "repos": [
            {
                "name": r.full_name,
                "description": r.description,
                "stars": r.stargazers_count,
                "forks": r.forks_count,
                "language": r.language,
                "url": r.html_url,
            }
            for r in sorted(
                repos.repos,
                key=lambda x: x.stargazers_count,
                reverse=True,
            )[:20]  # Top 20 by stars
        ],
    }

    # Contributions section
    if contributions:
        busiest = contributions.busiest_day
        contributions_data = {
            "total": contributions.total_contributions,
            "commits": contributions.total_commits,
            "pull_requests": contributions.total_pull_requests,
            "issues": contributions.total_issues,
            "reviews": contributions.total_reviews,
            "restricted": contributions.restricted_contributions,
            "current_streak": contributions.current_streak,
            "longest_streak": contributions.longest_streak,
            "busiest_day": busiest.date.isoformat() if busiest else None,
            "busiest_day_count": busiest.count if busiest else 0,
            "calendar": serialize_for_json(contributions.calendar.model_dump()),
        }
    else:
        contributions_data = {
            "note": "Contribution data requires GitHub token for GraphQL API"
        }

    # Activity section (truncated for JSON size)
    activity_data = {
        "events_count": len(activity.events),
        "commits_count": len(activity.commits),
        "prs_count": len(activity.pull_requests),
        "issues_count": len(activity.issues),
        "reviews_count": len(activity.reviews),
        "recent_events": [
            {
                "type": e.type,
                "repo": e.repo,
                "date": e.created_at.isoformat(),
            }
            for e in activity.events[:50]
        ],
        "recent_commits": [
            {
                "sha": c.sha[:7],
                "message": c.message[:100],
                "repo": c.repo,
                "date": c.date.isoformat(),
            }
            for c in sorted(activity.commits, key=lambda x: x.date, reverse=True)[:50]
        ],
        "pull_requests": [
            {
                "number": pr.number,
                "title": pr.title[:100],
                "repo": pr.repo,
                "state": pr.state,
                "merged": pr.is_merged,
                "url": pr.url,
            }
            for pr in activity.pull_requests[:50]
        ],
        "issues": [
            {
                "number": i.number,
                "title": i.title[:100],
                "repo": i.repo,
                "state": i.state,
                "url": i.url,
            }
            for i in activity.issues[:50]
        ],
    }

    # Summary section
    summary = {
        "total_commits": activity_summary.total_commits,
        "total_prs_opened": activity_summary.total_prs_opened,
        "total_prs_merged": activity_summary.total_prs_merged,
        "total_issues_opened": activity_summary.total_issues_opened,
        "total_reviews": activity_summary.total_reviews,
        "repos_contributed_to": activity_summary.repos_contributed_to[:20],
        "most_active_repos": activity_summary.most_active_repos[:10],
    }

    return {
        "username": username,
        "generated_at": datetime.now().isoformat(),
        "analysis_mode": mode,
        "period": {
            "from": from_date.isoformat() if from_date else None,
            "to": to_date.isoformat() if to_date else None,
        },
        "profile": profile,
        "social": social,
        "repositories": repositories,
        "contributions": contributions_data,
        "activity": activity_data,
        "summary": summary,
    }


def write_json_report(
    report: dict[str, Any],
    output_path: Optional[Path] = None,
    username: Optional[str] = None,
) -> Path:
    """Write analysis report to JSON file.

    Args:
        report: Report dictionary
        output_path: Output file path (optional)
        username: Username for default filename

    Returns:
        Path to written file
    """
    if output_path is None:
        # Generate default path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        username = username or report.get("username", "unknown")
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{username}_{timestamp}.json"

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON with pretty formatting
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    return output_path
