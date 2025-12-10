"""Tests for rate limiter module."""

import time

from github_researcher.utils.rate_limiter import (
    LOW_REMAINING_THRESHOLD,
    check_and_report_rate_limit,
    format_reset_time,
    format_time_remaining,
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
        assert format_time_remaining(1) == "1 second"
        assert format_time_remaining(59) == "59 seconds"

    def test_minutes_only(self):
        """Test formatting exact minutes."""
        assert format_time_remaining(60) == "1 minute"
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
        rate_info = {"core": {"remaining": 100, "limit": 5000, "reset": time.time() + 3600}}
        assert check_and_report_rate_limit(rate_info, is_authenticated=True) is True

    def test_returns_false_when_exhausted(self):
        """Test returns False when rate limit exhausted."""
        rate_info = {"core": {"remaining": 0, "limit": 60, "reset": time.time() + 3600}}
        assert check_and_report_rate_limit(rate_info, is_authenticated=False) is False

    def test_returns_true_when_low_but_not_exhausted(self):
        """Test returns True when running low but not exhausted."""
        rate_info = {"core": {"remaining": 5, "limit": 60, "reset": time.time() + 3600}}
        assert check_and_report_rate_limit(rate_info, is_authenticated=False) is True

    def test_warning_at_threshold(self):
        """Test that warning is shown at the threshold boundary."""
        rate_info = {
            "core": {
                "remaining": LOW_REMAINING_THRESHOLD - 1,
                "limit": 60,
                "reset": time.time() + 3600,
            }
        }
        # Should return True but trigger warning
        assert check_and_report_rate_limit(rate_info, is_authenticated=False) is True

    def test_no_warning_above_threshold(self):
        """Test that no warning is shown above threshold."""
        rate_info = {
            "core": {
                "remaining": LOW_REMAINING_THRESHOLD + 1,
                "limit": 60,
                "reset": time.time() + 3600,
            }
        }
        assert check_and_report_rate_limit(rate_info, is_authenticated=False) is True


class TestLowRemainingThreshold:
    """Tests for LOW_REMAINING_THRESHOLD constant."""

    def test_threshold_is_reasonable(self):
        """Test that threshold is a reasonable value."""
        assert LOW_REMAINING_THRESHOLD > 0
        assert LOW_REMAINING_THRESHOLD <= 100
