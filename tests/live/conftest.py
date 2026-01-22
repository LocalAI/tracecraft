"""Shared fixtures and configuration for live tests.

These tests require real API credentials. Set environment variables:
- OPENAI_API_KEY: Required for most tests
- ANTHROPIC_API_KEY: Optional, for Anthropic tests
- OTEL_EXPORTER_OTLP_ENDPOINT: Optional, for OTLP export tests
"""

from __future__ import annotations

import functools
import os
from typing import Any

import pytest


def pytest_addoption(parser: Any) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run live integration tests that require API keys",
    )
    parser.addoption(
        "--max-tokens",
        action="store",
        default=100,
        type=int,
        help="Maximum tokens per API call for cost control",
    )


def pytest_configure(config: Any) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "live: mark test as requiring live API access")
    config.addinivalue_line("markers", "expensive: mark test as using significant API credits")


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Skip live tests unless --live flag is provided."""
    if config.getoption("--live"):
        return

    skip_live = pytest.mark.skip(reason="Need --live option to run live tests")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def max_tokens(request: Any) -> int:
    """Get max tokens from command line option."""
    return request.config.getoption("--max-tokens")


@pytest.fixture
def openai_api_key() -> str | None:
    """Get OpenAI API key from environment."""
    return os.environ.get("OPENAI_API_KEY")


@pytest.fixture
def anthropic_api_key() -> str | None:
    """Get Anthropic API key from environment."""
    return os.environ.get("ANTHROPIC_API_KEY")


@pytest.fixture
def otlp_endpoint() -> str | None:
    """Get OTLP endpoint from environment."""
    return os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")


@pytest.fixture
def live_test_model() -> str:
    """Get the model to use for live tests."""
    return os.environ.get("LIVE_TEST_MODEL", "gpt-4o-mini")


def requires_openai_key(func: Any) -> Any:
    """Decorator to skip test if OpenAI API key is not set."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")
        return func(*args, **kwargs)

    return wrapper


def requires_anthropic_key(func: Any) -> Any:
    """Decorator to skip test if Anthropic API key is not set."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")
        return func(*args, **kwargs)

    return wrapper


def requires_otlp_endpoint(func: Any) -> Any:
    """Decorator to skip test if OTLP endpoint is not set."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            pytest.skip("OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return func(*args, **kwargs)

    return wrapper


@pytest.fixture
def temp_jsonl_path(tmp_path: Any) -> str:
    """Create a temporary JSONL file path."""
    return str(tmp_path / "test_traces.jsonl")


@pytest.fixture
def temp_html_path(tmp_path: Any) -> str:
    """Create a temporary HTML file path."""
    return str(tmp_path / "test_report.html")


@pytest.fixture(autouse=True)
def reset_runtime() -> Any:
    """Reset the global runtime between tests."""
    yield
    # Clean up runtime after each test
    from agenttrace.core.runtime import get_runtime

    runtime = get_runtime()
    if runtime:
        runtime.shutdown()
