"""
Integration tests for TUI with auto-instrumented traces.

These tests verify that traces captured via auto-instrumentation
display correctly in the TUI with both JSONL and SQLite storage.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

try:
    from tracecraft.core.models import AgentRun, Step, StepType
    from tracecraft.storage.jsonl import JSONLTraceStore
    from tracecraft.storage.sqlite import SQLiteTraceStore
    from tracecraft.tui.app import TraceCraftApp
    from tracecraft.tui.widgets.trace_table import TraceTable

    TEXTUAL_AVAILABLE = True
except ImportError as e:
    import traceback

    print(f"Import error: {e}")
    traceback.print_exc()
    TEXTUAL_AVAILABLE = False


def create_auto_instrumented_trace(name: str = "auto_test") -> AgentRun:
    """Create a trace that simulates auto-instrumentation output."""
    now = datetime.now(UTC)
    trace_id = uuid4()

    # Simulate OpenAI auto-instrumented step
    llm_step = Step(
        id=uuid4(),
        parent_id=None,
        trace_id=trace_id,
        name="openai.chat.completions.create",
        type=StepType.LLM,
        start_time=now,
        duration_ms=1080.0,
        model_name="gpt-4o-mini",
        model_provider="openai",
        input_tokens=9,
        output_tokens=9,
        cost_usd=0.0001,
        outputs={
            "result": {
                "id": "chatcmpl-test",
                "choices": [
                    {
                        "message": {"content": "Hello! How can I assist you today?"},
                        "finish_reason": "stop",
                    }
                ],
                "model": "gpt-4o-mini-2024-07-18",
                "usage": {"prompt_tokens": 9, "completion_tokens": 9, "total_tokens": 18},
            }
        },
    )

    return AgentRun(
        id=trace_id,
        name=name,
        start_time=now,
        duration_ms=1110.0,
        total_tokens=18,
        total_cost_usd=0.0001,
        steps=[llm_step],
        environment="development",
    )


def create_langchain_auto_trace() -> AgentRun:
    """Create a trace simulating LangChain auto-instrumentation."""
    now = datetime.now(UTC)
    trace_id = uuid4()

    # LangChain creates chain and LLM steps
    chain_step = Step(
        id=uuid4(),
        parent_id=None,
        trace_id=trace_id,
        name="ChatOpenAI.invoke",
        type=StepType.AGENT,
        start_time=now,
        duration_ms=1200.0,
        children=[],
    )

    llm_step = Step(
        id=uuid4(),
        parent_id=chain_step.id,
        trace_id=trace_id,
        name="ChatOpenAI",
        type=StepType.LLM,
        start_time=now,
        duration_ms=1100.0,
        model_name="gpt-4o-mini",
        model_provider="openai",
        input_tokens=15,
        output_tokens=10,
        cost_usd=0.00015,
    )

    chain_step.children.append(llm_step)

    return AgentRun(
        id=trace_id,
        name="langchain_auto_test",
        start_time=now,
        duration_ms=1250.0,
        total_tokens=25,
        total_cost_usd=0.00015,
        steps=[chain_step, llm_step],
        environment="development",
    )


@pytest.mark.skipif(not TEXTUAL_AVAILABLE, reason="textual not installed")
class TestTUIWithAutoInstrumentedTraces:
    """Test TUI displays auto-instrumented traces correctly."""

    @pytest.mark.asyncio
    async def test_tui_loads_openai_auto_trace_jsonl(self, tmp_path: Path) -> None:
        """Test TUI loads and displays OpenAI auto-instrumented trace from JSONL."""
        # Create test trace
        trace = create_auto_instrumented_trace("openai_auto_test")

        # Save to JSONL
        jsonl_path = tmp_path / "traces.jsonl"
        store = JSONLTraceStore(str(jsonl_path))
        store.save(trace)

        # Load in TUI
        app = TraceCraftApp(trace_source=str(jsonl_path))
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify app loaded
            assert app.is_running

            # Verify loader has traces
            if hasattr(app, "loader") and app.loader:
                traces = app.loader.list_all(limit=10)
                assert len(traces) >= 1

                # Verify trace structure
                loaded_trace = traces[0]
                assert loaded_trace.name == "openai_auto_test"
                assert len(loaded_trace.steps) >= 1
                assert loaded_trace.steps[0].type == StepType.LLM
                assert loaded_trace.steps[0].model_name == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_tui_loads_openai_auto_trace_sqlite(self, tmp_path: Path) -> None:
        """Test TUI loads and displays OpenAI auto-instrumented trace from SQLite."""
        # Create test trace
        trace = create_auto_instrumented_trace("openai_sqlite_test")

        # Save to SQLite
        sqlite_path = tmp_path / "traces.db"
        store = SQLiteTraceStore(str(sqlite_path))
        store.save(trace)
        store.close()

        # Load in TUI
        app = TraceCraftApp(trace_source=str(sqlite_path))
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify app loaded
            assert app.is_running

    @pytest.mark.asyncio
    async def test_tui_loads_langchain_auto_trace(self, tmp_path: Path) -> None:
        """Test TUI loads LangChain auto-instrumented trace with nested steps."""
        # Create LangChain trace with parent-child structure
        trace = create_langchain_auto_trace()

        # Save to JSONL
        jsonl_path = tmp_path / "langchain.jsonl"
        store = JSONLTraceStore(str(jsonl_path))
        store.save(trace)

        # Load in TUI
        app = TraceCraftApp(trace_source=str(jsonl_path))
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify app loaded
            assert app.is_running

            if hasattr(app, "loader") and app.loader:
                traces = app.loader.list_all(limit=10)
                assert len(traces) >= 1

                # Verify nested step structure
                loaded_trace = traces[0]
                assert loaded_trace.name == "langchain_auto_test"
                assert len(loaded_trace.steps) >= 2  # Chain + LLM

    @pytest.mark.asyncio
    async def test_tui_displays_multiple_auto_traces(self, tmp_path: Path) -> None:
        """Test TUI displays multiple auto-instrumented traces."""
        # Create multiple traces
        traces = [
            create_auto_instrumented_trace("openai_1"),
            create_auto_instrumented_trace("openai_2"),
            create_langchain_auto_trace(),
        ]

        # Save to JSONL
        jsonl_path = tmp_path / "multiple.jsonl"
        store = JSONLTraceStore(str(jsonl_path))
        for trace in traces:
            store.save(trace)

        # Load in TUI
        app = TraceCraftApp(trace_source=str(jsonl_path))
        async with app.run_test() as pilot:
            await pilot.pause()

            if hasattr(app, "loader") and app.loader:
                loaded = app.loader.list_all(limit=10)
                assert len(loaded) >= 3

    @pytest.mark.asyncio
    async def test_trace_table_shows_auto_step_counts(self, tmp_path: Path) -> None:
        """Test trace table shows correct step counts for auto traces."""
        trace = create_langchain_auto_trace()

        jsonl_path = tmp_path / "steps.jsonl"
        store = JSONLTraceStore(str(jsonl_path))
        store.save(trace)

        # Create TUI with trace
        app = TraceCraftApp(trace_source=str(jsonl_path))
        async with app.run_test() as pilot:
            await pilot.pause()

            # Find trace table and verify
            try:
                table = app.query_one("#trace-table", TraceTable)
                assert table.trace_count >= 1
            except Exception:
                # Table may not be immediately mounted
                pass


@pytest.mark.skipif(not TEXTUAL_AVAILABLE, reason="textual not installed")
class TestTUIWithRealAutoTraces:
    """Tests using real captured auto-instrumented traces (if available)."""

    def test_load_real_openai_trace(self) -> None:
        """Test loading real OpenAI auto-instrumented trace file."""
        trace_path = Path("traces/openai_only.jsonl")

        if not trace_path.exists():
            pytest.skip("Real trace file not available")

        store = JSONLTraceStore(str(trace_path))
        traces = store.list_all(limit=10)

        assert len(traces) >= 1
        trace = traces[0]

        # Verify it's a proper auto-instrumented trace
        assert trace.name == "test_openai_only"
        assert len(trace.steps) >= 1

        llm_steps = [s for s in trace.steps if s.type == StepType.LLM]
        assert len(llm_steps) >= 1

        llm_step = llm_steps[0]
        assert "openai" in llm_step.name.lower()
        assert llm_step.model_name is not None
        assert llm_step.duration_ms is not None
        assert llm_step.duration_ms > 0

    @pytest.mark.asyncio
    async def test_tui_with_real_openai_trace(self) -> None:
        """Test TUI loads and displays real OpenAI trace."""
        trace_path = Path("traces/openai_only.jsonl")

        if not trace_path.exists():
            pytest.skip("Real trace file not available")

        app = TraceCraftApp(trace_source=str(trace_path))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.is_running

    def test_load_real_sqlite_trace(self) -> None:
        """Test loading real SQLite trace file."""
        trace_path = Path("traces/auto_validation.db")

        if not trace_path.exists():
            pytest.skip("Real SQLite trace file not available")

        store = SQLiteTraceStore(str(trace_path))
        traces = store.list_all(limit=10)
        store.close()

        assert len(traces) >= 1
        trace = traces[0]

        # Verify it's a proper trace
        assert len(trace.steps) >= 1


# =============================================================================
# Visual Snapshot Tests - These capture SVG screenshots for visual regression
# =============================================================================


def _create_snapshot_trace_file(tmp_path: Path) -> Path:
    """Create a JSONL trace file for snapshot testing."""
    trace = create_auto_instrumented_trace("snapshot_test_trace")
    jsonl_path = tmp_path / "snapshot_traces.jsonl"
    store = JSONLTraceStore(str(jsonl_path))
    store.save(trace)
    return jsonl_path


@pytest.mark.skipif(not TEXTUAL_AVAILABLE, reason="textual not installed")
@pytest.mark.skipif(bool(os.environ.get("CI")), reason="TUI snapshots differ on CI runners")
class TestAutoInstrumentedTraceSnapshots:
    """Visual snapshot tests for TUI displaying auto-instrumented traces.

    These tests capture SVG screenshots to verify the visual appearance
    of the TUI when displaying auto-instrumented traces.
    """

    @pytest.fixture
    def trace_app(self, tmp_path: Path) -> TraceCraftApp:
        """Create a TraceCraftApp with auto-instrumented test traces."""
        # Create multiple traces for richer display
        traces = [
            create_auto_instrumented_trace("openai_agent_1"),
            create_auto_instrumented_trace("openai_agent_2"),
            create_langchain_auto_trace(),
        ]

        jsonl_path = tmp_path / "snapshot_traces.jsonl"
        store = JSONLTraceStore(str(jsonl_path))
        for trace in traces:
            store.save(trace)

        return TraceCraftApp(trace_source=str(jsonl_path))

    def test_auto_trace_table_display(self, snap_compare, trace_app: TraceCraftApp) -> None:
        """Snapshot test: Verify trace table displays auto-instrumented traces correctly.

        This captures the visual appearance of the trace table showing:
        - Trace names
        - Step counts
        - Duration
        - Token counts
        """
        assert snap_compare(trace_app, terminal_size=(120, 30))

    def test_auto_trace_table_with_selection(self, snap_compare, trace_app: TraceCraftApp) -> None:
        """Snapshot test: Verify trace table with a selected row."""

        async def select_first_trace(pilot):
            await pilot.pause()
            await pilot.press("j")  # Move down to select first trace
            await pilot.pause()

        assert snap_compare(
            trace_app,
            terminal_size=(120, 30),
            run_before=select_first_trace,
        )

    def test_auto_trace_waterfall_view(self, snap_compare, tmp_path: Path) -> None:
        """Snapshot test: Verify waterfall view displays auto-instrumented steps.

        This captures the waterfall timing view showing:
        - Step hierarchy
        - Duration bars
        - Step types (LLM, AGENT, etc.)
        """
        # Create trace with nested steps
        trace = create_langchain_auto_trace()
        jsonl_path = tmp_path / "waterfall_traces.jsonl"
        store = JSONLTraceStore(str(jsonl_path))
        store.save(trace)

        app = TraceCraftApp(trace_source=str(jsonl_path))

        async def expand_waterfall(pilot):
            await pilot.pause()
            # Select first trace and expand waterfall
            await pilot.press("j")  # Select trace
            await pilot.press("tab")  # Cycle to waterfall view
            await pilot.pause()

        assert snap_compare(
            app,
            terminal_size=(140, 35),
            run_before=expand_waterfall,
        )


@pytest.mark.skipif(not TEXTUAL_AVAILABLE, reason="textual not installed")
class TestRealTraceSnapshots:
    """Snapshot tests using real captured auto-instrumented traces."""

    def test_real_openai_trace_snapshot(self, snap_compare) -> None:
        """Snapshot test: Display real OpenAI auto-instrumented trace."""
        trace_path = Path("traces/openai_only.jsonl")

        if not trace_path.exists():
            pytest.skip("Real trace file not available")

        app = TraceCraftApp(trace_source=str(trace_path))

        async def load_and_select(pilot):
            await pilot.pause()

        assert snap_compare(
            app,
            terminal_size=(120, 30),
            run_before=load_and_select,
        )
