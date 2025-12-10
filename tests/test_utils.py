"""Tests for utility modules."""

from github_researcher.utils.pagination import (
    build_paginated_url,
    get_next_page_url,
    get_total_pages,
    parse_link_header,
)


class TestParseLinkHeader:
    """Tests for Link header parsing."""

    def test_parse_single_link(self):
        """Test parsing a single link."""
        header = '<https://api.github.com/users?page=2>; rel="next"'
        links = parse_link_header(header)

        assert links["next"] == "https://api.github.com/users?page=2"

    def test_parse_multiple_links(self):
        """Test parsing multiple links."""
        header = (
            '<https://api.github.com/users?page=2>; rel="next", '
            '<https://api.github.com/users?page=5>; rel="last", '
            '<https://api.github.com/users?page=1>; rel="first"'
        )
        links = parse_link_header(header)

        assert links["next"] == "https://api.github.com/users?page=2"
        assert links["last"] == "https://api.github.com/users?page=5"
        assert links["first"] == "https://api.github.com/users?page=1"

    def test_parse_empty_header(self):
        """Test parsing empty header."""
        assert parse_link_header(None) == {}
        assert parse_link_header("") == {}

    def test_get_next_page_url(self):
        """Test extracting next page URL."""
        header = '<https://api.github.com/users?page=2>; rel="next"'
        assert get_next_page_url(header) == "https://api.github.com/users?page=2"

    def test_get_next_page_url_missing(self):
        """Test when no next page exists."""
        header = '<https://api.github.com/users?page=1>; rel="first"'
        assert get_next_page_url(header) is None

    def test_get_total_pages(self):
        """Test extracting total pages from last link."""
        header = '<https://api.github.com/users?page=10>; rel="last"'
        assert get_total_pages(header) == 10

    def test_get_total_pages_missing(self):
        """Test when no last link exists."""
        header = '<https://api.github.com/users?page=2>; rel="next"'
        assert get_total_pages(header) is None


class TestBuildPaginatedUrl:
    """Tests for building paginated URLs."""

    def test_simple_url(self):
        """Test adding pagination to simple URL."""
        url = build_paginated_url("https://api.github.com/users", 2, 100)
        assert "page=2" in url
        assert "per_page=100" in url

    def test_url_with_existing_params(self):
        """Test adding pagination to URL with existing params."""
        url = build_paginated_url("https://api.github.com/users?sort=updated", 3, 50)
        assert "page=3" in url
        assert "per_page=50" in url
        assert "sort=updated" in url
