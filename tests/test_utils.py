"""Tests for utility modules."""

import time

import pytest

from github_researcher.utils.pagination import (
    parse_link_header,
    get_next_page_url,
    get_total_pages,
    build_paginated_url,
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
        url = build_paginated_url(
            "https://api.github.com/users?sort=updated",
            3,
            50
        )
        assert "page=3" in url
        assert "per_page=50" in url
        assert "sort=updated" in url


from github_researcher.utils.rate_limiter import (
    format_time_remaining,
    format_reset_time,
    check_and_report_rate_limit,
)


class TestFormatTimeRemaining:
    """Tests for format_time_remaining function."""

    def test_zero_seconds(self):
        """Test formatting 0 seconds."""
        assert format_time_remaining(0) == "now"

    def test_negative_seconds(self):
        """Test formatting negative seconds."""
        assert format_time_remaining(-10) == "now"

    def test_seconds_only(self):
        """Test formatting seconds under a minute."""
        assert format_time_remaining(30) == "30 seconds"
        assert format_time_remaining(1) == "1 seconds"
        assert format_time_remaining(59) == "59 seconds"

    def test_minutes_only(self):
        """Test formatting exact minutes."""
        assert format_time_remaining(60) == "1 minutes"
        assert format_time_remaining(120) == "2 minutes"

    def test_minutes_and_seconds(self):
        """Test formatting minutes with remaining seconds."""
        assert format_time_remaining(90) == "1 min 30 sec"
        assert format_time_remaining(150) == "2 min 30 sec"

    def test_hours_only(self):
        """Test formatting exact hours."""
        assert format_time_remaining(3600) == "1 hour"
        assert format_time_remaining(7200) == "2 hours"

    def test_hours_and_minutes(self):
        """Test formatting hours with minutes."""
        assert format_time_remaining(3660) == "1 hr 1 min"
        assert format_time_remaining(5400) == "1 hr 30 min"


class TestFormatResetTime:
    """Tests for format_reset_time function."""

    def test_formats_timestamp(self):
        """Test that timestamp is formatted as HH:MM:SS."""
        # Use a known timestamp
        timestamp = 1700000000  # 2023-11-14 22:13:20 UTC
        result = format_reset_time(timestamp)
        # Result will be in local time, so just check format
        assert len(result.split(":")) == 3


class TestCheckAndReportRateLimit:
    """Tests for check_and_report_rate_limit function."""

    def test_returns_true_when_remaining(self):
        """Test returns True when requests remaining."""
        rate_info = {
            "core": {"remaining": 100, "limit": 5000, "reset": time.time() + 3600}
        }
        assert check_and_report_rate_limit(rate_info, is_authenticated=True) is True

    def test_returns_false_when_exhausted(self):
        """Test returns False when rate limit exhausted."""
        rate_info = {
            "core": {"remaining": 0, "limit": 60, "reset": time.time() + 3600}
        }
        assert check_and_report_rate_limit(rate_info, is_authenticated=False) is False

    def test_returns_true_when_low_but_not_exhausted(self):
        """Test returns True when running low but not exhausted."""
        rate_info = {
            "core": {"remaining": 5, "limit": 60, "reset": time.time() + 3600}
        }
        assert check_and_report_rate_limit(rate_info, is_authenticated=False) is True
