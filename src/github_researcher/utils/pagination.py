"""Pagination utilities for GitHub API."""

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse


def parse_link_header(link_header: Optional[str]) -> dict[str, str]:
    """Parse GitHub's Link header into a dictionary of rel -> url.

    Example Link header:
    <https://api.github.com/users/torvalds/repos?page=2>; rel="next",
    <https://api.github.com/users/torvalds/repos?page=5>; rel="last"

    Returns:
        dict: {"next": "url", "last": "url", "prev": "url", "first": "url"}
    """
    if not link_header:
        return {}

    links = {}
    # Pattern to match <url>; rel="name"
    pattern = r'<([^>]+)>;\s*rel="([^"]+)"'

    for match in re.finditer(pattern, link_header):
        url, rel = match.groups()
        links[rel] = url

    return links


def get_next_page_url(link_header: Optional[str]) -> Optional[str]:
    """Extract the 'next' page URL from a Link header."""
    links = parse_link_header(link_header)
    return links.get("next")


def get_total_pages(link_header: Optional[str]) -> Optional[int]:
    """Extract total pages from the 'last' link in a Link header."""
    links = parse_link_header(link_header)
    last_url = links.get("last")

    if not last_url:
        return None

    # Parse the page number from the URL
    parsed = urlparse(last_url)
    query_params = parse_qs(parsed.query)
    page_values = query_params.get("page", [])

    if page_values:
        try:
            return int(page_values[0])
        except ValueError:
            return None

    return None


def build_paginated_url(base_url: str, page: int, per_page: int = 100) -> str:
    """Build a URL with pagination parameters.

    Args:
        base_url: The base URL (may already have query parameters)
        page: Page number (1-indexed)
        per_page: Items per page (max 100 for most GitHub APIs)

    Returns:
        URL with page and per_page query parameters
    """
    parsed = urlparse(base_url)
    existing_params = parse_qs(parsed.query)

    # Update with pagination params
    existing_params["page"] = [str(page)]
    existing_params["per_page"] = [str(per_page)]

    # Rebuild query string
    query_parts = []
    for key, values in existing_params.items():
        for value in values:
            query_parts.append(f"{key}={value}")

    new_query = "&".join(query_parts)

    # Rebuild URL
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
