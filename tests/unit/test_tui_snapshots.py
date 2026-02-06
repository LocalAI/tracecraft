"""
Snapshot tests for TUI widgets using pytest-textual-snapshot.

These tests capture SVG screenshots of widgets to verify visual appearance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container

    from tracecraft.core.models import AgentRun, Step, StepType
    from tracecraft.tui.widgets.filter_bar import FilterBar

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


def create_sample_trace() -> AgentRun:
    """Create a sample trace for testing."""
    now = datetime.now(UTC)
    return AgentRun(
        id=uuid4(),
        name="Test Agent",
        start_time=now,
        end_time=now,
        duration_ms=1500,
        total_tokens=1000,
        total_cost_usd=0.05,
        steps=[
            Step(
                id=uuid4(),
                name="llm_call",
                type=StepType.LLM,
                start_time=now,
                duration_ms=500,
            ),
            Step(
                id=uuid4(),
                name="tool_use",
                type=StepType.TOOL,
                start_time=now,
                duration_ms=200,
            ),
        ],
    )


class FilterBarTestApp(App):
    """Test app that displays just the FilterBar for snapshot testing."""

    CSS = """
    Screen {
        background: #0d0d0d;
    }

    Container {
        width: 100%;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield FilterBar(id="filter-bar")


@pytest.mark.skipif(not TEXTUAL_AVAILABLE, reason="textual not installed")
class TestFilterBarSnapshots:
    """Snapshot tests for the FilterBar widget."""

    def test_filter_bar_alignment(self, snap_compare):
        """
        Test that the Projects dropdown and filter input are properly aligned.

        The top of the Projects dropdown should align with the top of the
        filter input text box. Both should have proper visual height.
        """
        assert snap_compare(FilterBarTestApp(), terminal_size=(120, 15))

    def test_filter_bar_with_text(self, snap_compare):
        """Test filter bar after typing in the input."""

        async def type_filter(pilot):
            # Click on the input and type
            await pilot.press("tab")  # Focus input
            await pilot.press(*list("test filter"))

        assert snap_compare(
            FilterBarTestApp(),
            terminal_size=(120, 15),
            run_before=type_filter,
        )

    def test_filter_bar_focused_select(self, snap_compare):
        """Test filter bar with Projects dropdown focused."""

        async def focus_select(pilot):
            # The Select should be first focusable widget
            pass  # Default focus should be on Select

        assert snap_compare(
            FilterBarTestApp(),
            terminal_size=(120, 15),
            run_before=focus_select,
        )
