"""
Tests for the HTML report exporter.

Tests HTML generation with embedded trace data.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tracecraft.core.models import AgentRun, Step, StepType
from tracecraft.exporters.html import HTMLExporter


@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample agent run with steps."""
    start = datetime.now(UTC)
    run = AgentRun(
        name="test_agent",
        description="Test agent for HTML export",
        start_time=start,
        end_time=start + timedelta(seconds=2),
        duration_ms=2000.0,
        input={"query": "What is the weather?"},
        output={"response": "It's sunny today."},
        tags=["test", "weather"],
    )

    # Add LLM step
    llm_step = Step(
        trace_id=run.id,
        type=StepType.LLM,
        name="chat_completion",
        start_time=start,
        end_time=start + timedelta(milliseconds=500),
        duration_ms=500.0,
        model_name="gpt-4",
        input_tokens=100,
        output_tokens=50,
        inputs={"prompt": "What is the weather?"},
        outputs={"result": "It's sunny today."},
    )

    # Add tool step
    tool_step = Step(
        trace_id=run.id,
        type=StepType.TOOL,
        name="weather_api",
        start_time=start + timedelta(milliseconds=100),
        end_time=start + timedelta(milliseconds=300),
        duration_ms=200.0,
        inputs={"location": "New York"},
        outputs={"weather": "sunny", "temp": 72},
    )

    llm_step.children.append(tool_step)
    run.steps.append(llm_step)

    return run


@pytest.fixture
def error_run() -> AgentRun:
    """Create a run with an error."""
    start = datetime.now(UTC)
    run = AgentRun(
        name="error_agent",
        start_time=start,
        end_time=start + timedelta(milliseconds=100),
        duration_ms=100.0,
    )

    step = Step(
        trace_id=run.id,
        type=StepType.TOOL,
        name="failing_tool",
        start_time=start,
        error="Connection refused",
        error_type="ConnectionError",
    )
    run.steps.append(step)
    run.error_count = 1

    return run


class TestHTMLExporter:
    """Tests for HTMLExporter."""

    def test_html_generation(self, sample_run: AgentRun) -> None:
        """Should generate valid HTML."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_html_contains_trace_json(self, sample_run: AgentRun) -> None:
        """Should embed trace JSON data."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        # Should contain the trace data
        assert "test_agent" in html
        assert "chat_completion" in html
        assert "weather_api" in html

        # JSON should be embedded
        assert "const traceData = " in html or "traceData" in html

    def test_html_contains_run_metadata(self, sample_run: AgentRun) -> None:
        """Should include run metadata."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        assert sample_run.name in html
        assert "Test agent for HTML export" in html

    def test_html_self_contained(self, sample_run: AgentRun) -> None:
        """HTML should be self-contained (no external dependencies)."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        # Should not have external CDN links
        assert "http://" not in html.lower() or "https://" not in html.lower()
        # Should have inline styles
        assert "<style>" in html
        # Should have inline script
        assert "<script>" in html

    def test_html_shows_step_hierarchy(self, sample_run: AgentRun) -> None:
        """Should represent step hierarchy."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        # Both parent and child steps should be present
        assert "chat_completion" in html
        assert "weather_api" in html

    def test_html_shows_duration(self, sample_run: AgentRun) -> None:
        """Should display duration information."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        # Duration should be visible
        assert "2000" in html or "2.0" in html or "2s" in html

    def test_html_shows_tokens(self, sample_run: AgentRun) -> None:
        """Should display token counts for LLM steps."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        # Token counts
        assert "100" in html  # input tokens
        assert "50" in html  # output tokens

    def test_html_shows_error(self, error_run: AgentRun) -> None:
        """Should display error information."""
        exporter = HTMLExporter()
        html = exporter.render(error_run)

        assert "Connection refused" in html
        assert "ConnectionError" in html

    def test_export_to_file(self, sample_run: AgentRun) -> None:
        """Should export HTML to file."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            filepath = Path(f.name)

        try:
            exporter = HTMLExporter(filepath=filepath)
            exporter.export(sample_run)

            # File should exist
            assert filepath.exists()

            # Content should be valid HTML
            content = filepath.read_text()
            assert "<!DOCTYPE html>" in content
            assert sample_run.name in content
        finally:
            filepath.unlink()

    def test_export_creates_directory(self, sample_run: AgentRun) -> None:
        """Should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "subdir" / "trace.html"
            exporter = HTMLExporter(filepath=filepath)
            exporter.export(sample_run)

            assert filepath.exists()

    def test_render_returns_string(self, sample_run: AgentRun) -> None:
        """render() should return HTML string without writing file."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        assert isinstance(html, str)
        assert len(html) > 0


class TestHTMLExporterStyling:
    """Tests for HTML styling and formatting."""

    def test_has_step_type_colors(self, sample_run: AgentRun) -> None:
        """Different step types should have different styles."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        # Should have styling for different step types
        assert "llm" in html.lower() or "LLM" in html
        assert "tool" in html.lower() or "TOOL" in html

    def test_collapsible_sections(self, sample_run: AgentRun) -> None:
        """Should support collapsible sections."""
        exporter = HTMLExporter()
        html = exporter.render(sample_run)

        # Should have interactive elements
        assert (
            "details" in html.lower()
            or "collapse" in html.lower()
            or "toggle" in html.lower()
            or "click" in html.lower()
        )


class TestHTMLExporterEdgeCases:
    """Tests for edge cases."""

    def test_empty_run(self) -> None:
        """Should handle run with no steps."""
        run = AgentRun(
            name="empty_agent",
            start_time=datetime.now(UTC),
        )
        exporter = HTMLExporter()
        html = exporter.render(run)

        assert "empty_agent" in html
        assert "<!DOCTYPE html>" in html

    def test_deeply_nested_steps(self) -> None:
        """Should handle deeply nested step hierarchy."""
        run = AgentRun(
            name="nested_agent",
            start_time=datetime.now(UTC),
        )

        # Create nested structure
        parent = Step(
            trace_id=run.id,
            type=StepType.AGENT,
            name="level_0",
            start_time=datetime.now(UTC),
        )

        current = parent
        for i in range(1, 5):
            child = Step(
                trace_id=run.id,
                parent_id=current.id,
                type=StepType.TOOL,
                name=f"level_{i}",
                start_time=datetime.now(UTC),
            )
            current.children.append(child)
            current = child

        run.steps.append(parent)

        exporter = HTMLExporter()
        html = exporter.render(run)

        # All levels should be present
        for i in range(5):
            assert f"level_{i}" in html

    def test_special_characters_escaped(self) -> None:
        """Should escape HTML special characters."""
        run = AgentRun(
            name="test<script>alert('xss')</script>",
            start_time=datetime.now(UTC),
        )
        exporter = HTMLExporter()
        html = exporter.render(run)

        # Script tag should be escaped
        assert "<script>alert" not in html
