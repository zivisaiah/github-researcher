"""GitHub REST API client."""

import asyncio
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from github_researcher.config import Config, get_config
from github_researcher.utils.pagination import get_next_page_url
from github_researcher.utils.rate_limiter import RateLimiter, get_rate_limiter


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: int, response_body: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GitHubRateLimitError(GitHubAPIError):
    """Raised when rate limit is exceeded."""

    pass


class GitHubNotFoundError(GitHubAPIError):
    """Raised when a resource is not found."""

    pass


class GitHubRestClient:
    """Async client for GitHub REST API."""

    def __init__(
        self,
        config: Optional[Config] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.config = config or get_config()
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-researcher/0.1.0",
        }
        if self.config.github_token:
            headers["Authorization"] = f"Bearer {self.config.github_token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.github_api_url,
                headers=self._get_headers(),
                timeout=self.config.request_timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "GitHubRestClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _update_rate_limit(self, headers: httpx.Headers, is_search: bool = False) -> None:
        """Update rate limiter from response headers."""
        header_dict = dict(headers)
        if is_search:
            self.rate_limiter.update_search_from_headers(header_dict)
        else:
            self.rate_limiter.update_rest_from_headers(header_dict)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        is_search: bool = False,
        **kwargs,
    ) -> httpx.Response:
        """Make an API request with rate limiting and retries."""
        # Acquire rate limit permission
        if is_search:
            await self.rate_limiter.acquire_search()
        else:
            await self.rate_limiter.acquire_rest()

        client = await self._get_client()
        response = await client.request(method, endpoint, **kwargs)

        # Update rate limit from response
        self._update_rate_limit(response.headers, is_search)

        # Handle errors
        if response.status_code == 404:
            raise GitHubNotFoundError(
                f"Resource not found: {endpoint}",
                status_code=404,
                response_body=response.json() if response.content else None,
            )
        elif response.status_code == 403:
            # Check if it's a rate limit error
            body = response.json() if response.content else {}
            if "rate limit" in body.get("message", "").lower():
                raise GitHubRateLimitError(
                    "Rate limit exceeded",
                    status_code=403,
                    response_body=body,
                )
            raise GitHubAPIError(
                f"Forbidden: {body.get('message', 'Unknown error')}",
                status_code=403,
                response_body=body,
            )
        elif response.status_code >= 500:
            raise GitHubAPIError(
                f"Server error: {response.status_code}",
                status_code=response.status_code,
            )
        elif response.status_code >= 400:
            body = response.json() if response.content else {}
            raise GitHubAPIError(
                f"API error: {body.get('message', 'Unknown error')}",
                status_code=response.status_code,
                response_body=body,
            )

        return response

    async def get(self, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make a GET request and return JSON response."""
        response = await self._request("GET", endpoint, **kwargs)
        return response.json()

    async def get_paginated(
        self,
        endpoint: str,
        max_pages: Optional[int] = None,
        per_page: int = 100,
        is_search: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated endpoint.

        Args:
            endpoint: API endpoint (will append pagination params)
            max_pages: Maximum number of pages to fetch (None for all)
            per_page: Items per page (max 100)
            is_search: Whether this is a Search API request

        Returns:
            List of all items across all pages
        """
        all_items = []
        page = 1

        # Build initial URL with pagination
        separator = "&" if "?" in endpoint else "?"
        url = f"{endpoint}{separator}per_page={per_page}&page={page}"

        while url and (max_pages is None or page <= max_pages):
            response = await self._request("GET", url, is_search=is_search)
            data = response.json()

            # Handle search results (nested in 'items')
            if is_search and isinstance(data, dict) and "items" in data:
                items = data["items"]
                # Check if we've hit the search limit
                total_count = data.get("total_count", 0)
                if total_count > 1000:
                    # Search API only returns first 1000 results
                    pass  # Continue but be aware of limit
            elif isinstance(data, list):
                items = data
            else:
                # Single item response
                all_items.append(data)
                break

            all_items.extend(items)

            # Check for next page
            link_header = response.headers.get("Link")
            url = get_next_page_url(link_header)
            page += 1

            # Small delay to be nice to the API
            if url:
                await asyncio.sleep(0.1)

        return all_items

    # Convenience methods for common endpoints

    async def get_user(self, username: str) -> dict[str, Any]:
        """Get user profile data."""
        return await self.get(f"/users/{username}")

    async def get_user_repos(
        self,
        username: str,
        max_pages: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Get user's public repositories."""
        return await self.get_paginated(
            f"/users/{username}/repos?sort=updated",
            max_pages=max_pages,
        )

    async def get_user_orgs(self, username: str) -> list[dict[str, Any]]:
        """Get user's public organizations."""
        return await self.get_paginated(f"/users/{username}/orgs")

    async def get_user_events(
        self,
        username: str,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Get user's public events (max 300 events, last 90 days)."""
        return await self.get_paginated(
            f"/users/{username}/events/public",
            max_pages=max_pages,
        )

    async def get_user_followers(
        self,
        username: str,
        max_pages: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Get user's followers."""
        return await self.get_paginated(
            f"/users/{username}/followers",
            max_pages=max_pages,
        )

    async def get_user_following(
        self,
        username: str,
        max_pages: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Get users that this user follows."""
        return await self.get_paginated(
            f"/users/{username}/following",
            max_pages=max_pages,
        )

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository details."""
        return await self.get(f"/repos/{owner}/{repo}")

    async def get_repo_languages(self, owner: str, repo: str) -> dict[str, int]:
        """Get repository language breakdown (language -> bytes)."""
        return await self.get(f"/repos/{owner}/{repo}/languages")

    async def get_repo_commits(
        self,
        owner: str,
        repo: str,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Get repository commits, optionally filtered by author."""
        params = []
        if author:
            params.append(f"author={author}")
        if since:
            params.append(f"since={since}")
        if until:
            params.append(f"until={until}")

        endpoint = f"/repos/{owner}/{repo}/commits"
        if params:
            endpoint += "?" + "&".join(params)

        return await self.get_paginated(endpoint, max_pages=max_pages)

    async def search_issues(
        self,
        query: str,
        max_pages: Optional[int] = 10,
    ) -> list[dict[str, Any]]:
        """Search issues and pull requests.

        Args:
            query: Search query (e.g., "author:username type:pr")
            max_pages: Maximum pages to fetch (each page = 100 results)

        Returns:
            List of matching issues/PRs
        """
        endpoint = f"/search/issues?q={query}&sort=updated&order=desc"
        return await self.get_paginated(endpoint, max_pages=max_pages, is_search=True)

    async def search_commits(
        self,
        query: str,
        max_pages: Optional[int] = 10,
    ) -> list[dict[str, Any]]:
        """Search commits.

        Args:
            query: Search query (e.g., "author:username")
            max_pages: Maximum pages to fetch

        Returns:
            List of matching commits
        """
        endpoint = f"/search/commits?q={query}&sort=author-date&order=desc"
        # Commits search requires special accept header
        return await self.get_paginated(endpoint, max_pages=max_pages, is_search=True)
