"""Pytest configuration and fixtures."""

import os
from pathlib import Path

import pytest
import vcr

from github_researcher.config import Config, set_config
from github_researcher.utils.rate_limiter import reset_rate_limiter

# VCR configuration
CASSETTES_DIR = Path(__file__).parent / "cassettes"


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state before each test."""
    reset_rate_limiter()
    yield


@pytest.fixture
def test_config():
    """Create a test configuration."""
    # Support both GITHUB_RESEARCHER_TOKEN (preferred) and GITHUB_TOKEN (fallback)
    token = os.getenv("GITHUB_RESEARCHER_TOKEN") or os.getenv("GITHUB_TOKEN", "test_token")
    config = Config(
        github_token=token,
        github_api_url="https://api.github.com",
        github_graphql_url="https://api.github.com/graphql",
    )
    set_config(config)
    return config


@pytest.fixture
def vcr_config():
    """VCR configuration for recording HTTP interactions."""
    return {
        "cassette_library_dir": str(CASSETTES_DIR),
        "record_mode": "once",
        "match_on": ["uri", "method"],
        "filter_headers": [
            "Authorization",
            "X-GitHub-Api-Version",
            "User-Agent",
        ],
        "filter_query_parameters": [],
        "decode_compressed_response": True,
    }


@pytest.fixture
def vcr_cassette(vcr_config, request):
    """Create a VCR cassette for the current test."""
    cassette_name = f"{request.node.name}.yaml"
    my_vcr = vcr.VCR(**vcr_config)
    with my_vcr.use_cassette(cassette_name):
        yield


def pytest_configure(config):
    """Ensure cassettes directory exists."""
    CASSETTES_DIR.mkdir(parents=True, exist_ok=True)
